"""
RAG 知识库管理器
- ChromaDB 作为向量存储
- DashScope Embedding API (text-embedding-v2) 生成向量
- 无需下载模型，直接调用阿里云 API
"""
import os
import uuid
import time
from typing import List, Optional

import chromadb
from dashscope import TextEmbedding
from dashscope import TextReRank as _TextReRank
from dotenv import load_dotenv

from app.common.logger import logger

# 从项目根目录加载 .env（解决不同启动方式下 CWD 不一致的问题）
_ENV_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    ".env",
)

if os.path.exists(_ENV_PATH):
    load_dotenv(_ENV_PATH)
else:
    load_dotenv()  # fallback

# 确保 API key 已设置——显式传给 DashScope SDK
import dashscope
_ds_key = os.getenv("DASHSCOPE_API_KEY")
if not _ds_key:
    raise RuntimeError(
        "DASHSCOPE_API_KEY 未设置！请在 .env 文件中配置或设置环境变量"
    )
dashscope.api_key = _ds_key
logger.info(f"DashScope API key 已配置 ({_ds_key[:10]}...)")

# embedding 模型配置
EMBEDDING_MODEL = "text-embedding-v2"
EMBEDDING_DIM = 1536
EMBEDDING_BATCH_SIZE = 20  # DashScope 单次最多 25 条

# reranker 模型配置
RERANK_MODEL = "qwen3-rerank"
RERANK_BATCH_SIZE = 25  # 单次重排文档上限


def _encode(texts: List[str]) -> List[List[float]]:
    """调用 DashScope Embedding API 生成向量，支持批处理"""
    if not texts:
        return []

    all_embeddings = []
    for i in range(0, len(texts), EMBEDDING_BATCH_SIZE):
        batch = texts[i:i + EMBEDDING_BATCH_SIZE]
        resp = TextEmbedding.call(
            model=EMBEDDING_MODEL,
            input=batch,
        )
        if resp.status_code != 200:
            raise RuntimeError(
                f"Embedding API 调用失败 (HTTP {resp.status_code}): {resp.message}"
            )
        all_embeddings.extend(
            [item["embedding"] for item in resp.output["embeddings"]]
        )
        # 频率控制（DashScope 免费版有限速）
        if i + EMBEDDING_BATCH_SIZE < len(texts):
            time.sleep(0.3)

    return all_embeddings


def _rerank(query: str, documents: List[str], top_n: int) -> List[dict]:
    """
    调用 DashScope Reranker API 对候选文档重新排序

    Args:
        query: 查询文本
        documents: 候选文档列表
        top_n: 返回的最大文档数

    Returns:
        [{"index": 原始索引, "relevance_score": 0-1}, ...]，按相关性降序
    """
    resp = _TextReRank.call(
        model=RERANK_MODEL,
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


class RAGManager:
    """宠物养护 RAG 知识库管理器（DashScope Embedding）"""

    def __init__(
        self,
        persist_dir: str,
        collection_name: str = "pet_knowledge",
    ):
        os.makedirs(persist_dir, exist_ok=True)
        self.persist_dir = persist_dir
        self.collection_name = collection_name

        # 初始化 ChromaDB
        self.client = chromadb.PersistentClient(path=persist_dir)
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

        count = self.collection.count()
        logger.info(
            f"RAG 知识库已就绪 (embedding: {EMBEDDING_MODEL}@{EMBEDDING_DIM}d), "
            f"当前文档数: {count}"
        )

    def add_documents(
        self,
        documents: List[str],
        metadatas: Optional[List[dict]] = None,
        ids: Optional[List[str]] = None,
    ) -> int:
        """添加文档到知识库，返回添加的文档数"""
        if not documents:
            return 0

        if ids is None:
            ids = [str(uuid.uuid4()) for _ in documents]

        logger.info(f"正在为 {len(documents)} 篇文档生成 embedding...")
        embeddings = _encode(documents)

        self.collection.add(
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=ids,
        )

        logger.info(f"已添加 {len(documents)} 篇文档到知识库")
        return len(documents)

    def search(
        self,
        query: str,
        n_results: int = 3,
        min_similarity: float = 0.3,
        use_rerank: bool = True,
        recall_multiplier: int = 5,
    ) -> List[dict]:
        """
        搜索知识库（粗排 + 精排 双阶段检索）

        Args:
            query: 查询文本
            n_results: 最终返回的最大文档数
            min_similarity: 最小相似度阈值 (0-1)
            use_rerank: 是否启用精排（Reranker）。关闭则仅用向量检索
            recall_multiplier: 粗排召回倍数。粗排召回数 = n_results × recall_multiplier

        Returns:
            匹配的文档列表 [{"content": ..., "score": ..., "metadata": ...}, ...]
        """
        if self.collection.count() == 0:
            return []

        # ============ 阶段一：粗排（向量检索，快速召回候选） ============
        recall_n = min(
            n_results * recall_multiplier,
            self.collection.count(),
        )
        query_embedding = _encode([query])

        results = self.collection.query(
            query_embeddings=query_embedding,
            n_results=recall_n,
            include=["documents", "metadatas", "distances"],
        )

        candidates: List[dict] = []
        if results.get("documents") and results["documents"][0]:
            for i, doc in enumerate(results["documents"][0]):
                distance = (
                    results.get("distances", [[0]])[0][i]
                    if results.get("distances")
                    else 0
                )
                similarity = 1 - (distance / 2)
                # 粗排阶段用较低阈值，放更多候选进入精排
                coarse_threshold = min_similarity * 0.5
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
            f"全库={self.collection.count()}  召回上限={recall_n}  阈值={coarse_threshold:.2f}  "
            f"→ 候选 {len(candidates)} 条"
        )
        if candidates:
            # 打印每条候选的粗排分数和来源
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
            skip_reason = "候选不足" if len(candidates) <= n_results else "use_rerank=False"
            logger.info(f"[跳过精排] {skip_reason}，直接返回粗排 Top-{n_results}")
            return candidates[:n_results]

        # ============ 阶段二：精排（Reranker 重新打分） ============
        rerank_docs = [c["content"] for c in candidates]
        logger.info(f"[精排] 送入 {len(rerank_docs)} 条文档 → Reranker({RERANK_MODEL})，请求 Top-{n_results}")

        try:
            reranked = _rerank(
                query=query,
                documents=rerank_docs,
                top_n=n_results,
            )
        except Exception as e:
            logger.warning(f"[精排失败] {e} → 回退到粗排结果")
            return candidates[:n_results]

        # ── 精排日志：逐条对比粗排分 vs 精排分 ──
        logger.info(f"[精排完成] 返回 {len(reranked)} 条 | 分数变化:")
        for rank, r in enumerate(reranked):
            idx = r["index"]
            if idx >= len(candidates):
                continue
            c = candidates[idx]
            old_score = c["score"]
            new_score = round(r.get("relevance_score", old_score), 3)
            source = c["metadata"].get("source", "-")
            direction = "↑" if new_score > old_score else "↓" if new_score < old_score else "="
            logger.info(
                f"  #{rank + 1} | 粗排={old_score:.3f} → 精排={new_score:.3f} {direction}  "
                f"| [{source}]"
            )

        # 用精排分数重建结果列表
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

    def delete_collection(self):
        """清空知识库"""
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
        """获取知识库统计信息"""
        return {
            "document_count": self.collection.count(),
            "collection_name": self.collection_name,
            "persist_dir": self.persist_dir,
            "embedding_model": EMBEDDING_MODEL,
        }
