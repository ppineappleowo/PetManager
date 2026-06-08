"""
RAG 知识库管理器
- ChromaDB 作为向量存储
- DashScope Embedding API 生成向量
- DashScope Reranker API 精排重打分
- 无需下载模型，直接调用阿里云 API

配置通过构造参数注入，无模块级硬编码和全局状态。
"""

import os
import uuid
import time
from typing import List, Optional

import chromadb
from dashscope import TextEmbedding
from dashscope import TextReRank as _TextReRank

from app.common.logger import logger


# ==================== Embedding 工具函数 ====================

def encode_texts(
    texts: List[str],
    model: str = "text-embedding-v2",
    batch_size: int = 20,
    api_key: str | None = None,
) -> List[List[float]]:
    """调用 DashScope Embedding API 批量生成向量。

    Args:
        texts: 待向量化的文本列表。
        model: Embedding 模型名称。
        batch_size: 单次 API 调用的最大文本数（DashScope 上限 25）。
        api_key: DashScope API key。

    Returns:
        向量列表，每个向量为 float 列表。

    Raises:
        RuntimeError: API 调用失败时。
    """
    if not texts:
        return []

    # 按需设置 API key（仅当未全局设置时）
    if api_key:
        import dashscope
        dashscope.api_key = api_key

    all_embeddings: list[list[float]] = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        resp = TextEmbedding.call(model=model, input=batch)
        if resp.status_code != 200:
            raise RuntimeError(
                f"Embedding API 调用失败 (HTTP {resp.status_code}): {resp.message}"
            )
        all_embeddings.extend(
            [item["embedding"] for item in resp.output["embeddings"]]
        )
        # 频率控制（DashScope 免费版有限速）
        if i + batch_size < len(texts):
            time.sleep(0.3)

    return all_embeddings


def rerank_documents(
    query: str,
    documents: List[str],
    top_n: int,
    model: str = "qwen3-rerank",
) -> List[dict]:
    """调用 DashScope Reranker API 对候选文档重新排序。

    Args:
        query: 查询文本。
        documents: 候选文档内容列表。
        top_n: 返回的最大文档数。
        model: Reranker 模型名称。

    Returns:
        [{"index": 原始索引, "relevance_score": 0-1}, ...]，按相关性降序。
    """
    resp = _TextReRank.call(
        model=model,
        query=query,
        documents=documents,
        top_n=min(top_n, len(documents)),
        return_documents=False,
    )
    if resp.status_code != 200:
        raise RuntimeError(
            f"Reranker API 调用失败 (HTTP {resp.status_code}): {resp.message}"
        )
    return resp.output["results"]


# ==================== RAG 管理器 ====================

class RAGManager:
    """宠物养护 RAG 知识库管理器（DashScope Embedding + ChromaDB）。

    所有配置通过构造参数注入，不依赖模块级全局变量。
    """

    def __init__(
        self,
        persist_dir: str,
        collection_name: str = "pet_knowledge",
        embedding_model: str = "text-embedding-v2",
        embedding_dim: int = 1536,
        embedding_batch_size: int = 20,
        rerank_model: str = "qwen3-rerank",
    ):
        """
        Args:
            persist_dir: ChromaDB 持久化目录路径。
            collection_name: ChromaDB 集合名称。
            embedding_model: DashScope Embedding 模型名。
            embedding_dim: Embedding 向量维度。
            embedding_batch_size: 单次 embedding 调用的批量大小。
            rerank_model: DashScope Reranker 模型名。
        """
        os.makedirs(persist_dir, exist_ok=True)
        self.persist_dir = persist_dir
        self.collection_name = collection_name
        self.embedding_model = embedding_model
        self.embedding_dim = embedding_dim
        self.embedding_batch_size = embedding_batch_size
        self.rerank_model = rerank_model

        # 初始化 ChromaDB
        self.client = chromadb.PersistentClient(path=persist_dir)
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

        count = self.collection.count()
        logger.info(
            f"RAG 知识库已就绪 (embedding: {embedding_model}@{embedding_dim}d), "
            f"当前文档数: {count}"
        )

    # ── 文档管理 ─────────────────────────────────────────────

    def add_documents(
        self,
        documents: List[str],
        metadatas: Optional[List[dict]] = None,
        ids: Optional[List[str]] = None,
    ) -> int:
        """添加文档到知识库。

        Args:
            documents: 文档内容列表。
            metadatas: 每篇文档的元数据（可选）。
            ids: 文档 ID 列表（可选，默认生成 UUID）。

        Returns:
            实际添加的文档数量。
        """
        if not documents:
            return 0

        if ids is None:
            ids = [str(uuid.uuid4()) for _ in documents]

        logger.info(f"正在为 {len(documents)} 篇文档生成 embedding...")
        embeddings = encode_texts(
            texts=documents,
            model=self.embedding_model,
            batch_size=self.embedding_batch_size,
        )

        self.collection.add(
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=ids,
        )

        logger.info(f"已添加 {len(documents)} 篇文档到知识库")
        return len(documents)

    # ── 搜索（粗排 + 精排 双阶段检索） ──────────────────────

    def search(
        self,
        query: str,
        n_results: int = 3,
        min_similarity: float = 0.3,
        use_rerank: bool = True,
        recall_multiplier: int = 5,
    ) -> List[dict]:
        """搜索知识库（粗排 + 精排 双阶段检索）。

        阶段一（粗排）：向量检索快速召回候选集。
        阶段二（精排）：Reranker 对候选重新打分排序。

        Args:
            query: 查询文本。
            n_results: 最终返回的最大文档数。
            min_similarity: 最小相似度阈值 (0-1)。
            use_rerank: 是否启用精排。关闭则仅用向量检索。
            recall_multiplier: 粗排召回倍数 = n_results × recall_multiplier。

        Returns:
            匹配的文档列表 [{"content": ..., "score": ..., "metadata": ...}, ...]。
        """
        if self.collection.count() == 0:
            return []

        # ═══ 阶段一：粗排（向量检索） ═══
        recall_n = min(
            n_results * recall_multiplier,
            self.collection.count(),
        )
        query_embedding = encode_texts(
            texts=[query],
            model=self.embedding_model,
            batch_size=self.embedding_batch_size,
        )

        results = self.collection.query(
            query_embeddings=query_embedding,
            n_results=recall_n,
            include=["documents", "metadatas", "distances"],
        )

        candidates: List[dict] = []
        if results.get("documents") and results["documents"][0]:
            coarse_threshold = min_similarity * 0.5  # 粗排用较低阈值
            for i, doc in enumerate(results["documents"][0]):
                distance = (
                    results.get("distances", [[0]])[0][i]
                    if results.get("distances")
                    else 0
                )
                similarity = 1 - (distance / 2)
                if similarity >= coarse_threshold:
                    metadata = (
                        results.get("metadatas", [[{}]])[0][i]
                        if results.get("metadatas") and results["metadatas"][0]
                        else {}
                    )
                    candidates.append({
                        "content": doc,
                        "score": round(similarity, 3),
                        "metadata": metadata,
                    })

        # ── 粗排日志 ──
        logger.info(
            f"[粗排] query=\"{query[:40]}{'...' if len(query) > 40 else ''}\"  "
            f"全库={self.collection.count()}  召回上限={recall_n}  "
            f"阈值={coarse_threshold:.2f}  → 候选 {len(candidates)} 条"
        )
        if candidates:
            for rank, c in enumerate(candidates, 1):
                source = c["metadata"].get("source", "-")
                preview = c["content"][:50].replace("\n", " ")
                logger.info(
                    f"  #{rank} | 粗排分={c['score']:.3f} | [{source}] | {preview}..."
                )

        if not candidates:
            return []

        # 候选太少，跳过精排
        if len(candidates) <= n_results or not use_rerank:
            reason = "候选不足" if len(candidates) <= n_results else "use_rerank=False"
            logger.info(f"[跳过精排] {reason}，直接返回粗排 Top-{n_results}")
            return candidates[:n_results]

        # ═══ 阶段二：精排（Reranker 重打分） ═══
        return self._apply_rerank(
            query=query,
            candidates=candidates,
            top_n=n_results,
            min_similarity=min_similarity,
        )

    def _apply_rerank(
        self,
        query: str,
        candidates: List[dict],
        top_n: int,
        min_similarity: float,
    ) -> List[dict]:
        """对候选集进行精排并返回最终结果。"""
        rerank_docs = [c["content"] for c in candidates]
        logger.info(
            f"[精排] 送入 {len(rerank_docs)} 条文档 → "
            f"Reranker({self.rerank_model})，请求 Top-{top_n}"
        )

        try:
            reranked = rerank_documents(
                query=query,
                documents=rerank_docs,
                top_n=top_n,
                model=self.rerank_model,
            )
        except Exception as e:
            logger.warning(f"[精排失败] {e} → 回退到粗排结果")
            return candidates[:top_n]

        # ── 精排日志：逐条对比 ──
        logger.info(f"[精排完成] 返回 {len(reranked)} 条 | 分数变化:")
        for rank, r in enumerate(reranked):
            idx = r["index"]
            if idx >= len(candidates):
                continue
            c = candidates[idx]
            old_score = c["score"]
            new_score = round(r.get("relevance_score", old_score), 3)
            source = c["metadata"].get("source", "-")
            direction = (
                "↑" if new_score > old_score
                else "↓" if new_score < old_score
                else "="
            )
            logger.info(
                f"  #{rank + 1} | 粗排={old_score:.3f} → 精排={new_score:.3f} "
                f"{direction}  | [{source}]"
            )

        # 用精排分数重建结果
        final_docs = []
        for r in reranked:
            idx = r["index"]
            if idx >= len(candidates):
                continue
            c = candidates[idx]
            score = r.get("relevance_score", c["score"])
            if score >= min_similarity:
                final_docs.append({
                    "content": c["content"],
                    "score": round(score, 3),
                    "metadata": c["metadata"],
                })

        logger.info(f"[最终输出] {len(final_docs)} 条 (min_similarity={min_similarity})")
        return final_docs

    # ── 对外的精排接口 ─────────────────────────────────────

    def rerank_candidates(
        self,
        query: str,
        candidates: List[dict],
        top_n: int = 3,
    ) -> List[dict]:
        """对候选文档列表进行 Reranker 重排序（对外暴露接口）。

        Args:
            query: 查询文本。
            candidates: 候选列表 [{"content": ..., "score": ..., "metadata": ...}, ...]。
            top_n: 返回的最大文档数。

        Returns:
            重排后的文档列表。
        """
        if len(candidates) <= top_n:
            return candidates

        try:
            reranked = rerank_documents(
                query=query,
                documents=[c["content"] for c in candidates],
                top_n=top_n,
                model=self.rerank_model,
            )
        except Exception as e:
            logger.warning(f"[精排失败] {e} → 保持原顺序")
            return candidates[:top_n]

        final_docs = []
        for r in reranked:
            idx = r["index"]
            if idx >= len(candidates):
                continue
            c = candidates[idx]
            new_score = round(r.get("relevance_score", c["score"]), 3)
            final_docs.append({
                "content": c["content"],
                "score": new_score,
                "metadata": c["metadata"],
            })
        return final_docs

    # ── 管理操作 ──────────────────────────────────────────

    def delete_collection(self):
        """清空知识库集合。"""
        try:
            self.client.delete_collection(self.collection_name)
        except Exception:
            pass
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info("知识库已清空")

    def get_stats(self) -> dict:
        """获取知识库统计信息。"""
        return {
            "document_count": self.collection.count(),
            "collection_name": self.collection_name,
            "persist_dir": self.persist_dir,
            "embedding_model": self.embedding_model,
        }
