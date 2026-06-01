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
BATCH_SIZE = 20  # DashScope 单次最多 25 条


def _encode(texts: List[str]) -> List[List[float]]:
    """调用 DashScope Embedding API 生成向量，支持批处理"""
    if not texts:
        return []

    all_embeddings = []
    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i:i + BATCH_SIZE]
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
        if i + BATCH_SIZE < len(texts):
            time.sleep(0.3)

    return all_embeddings


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
    ) -> List[dict]:
        """
        搜索知识库

        Args:
            query: 查询文本
            n_results: 返回的最大文档数
            min_similarity: 最小余弦相似度阈值 (0-1)

        Returns:
            匹配的文档列表 [{"content": ..., "score": ..., "metadata": ...}, ...]
        """
        if self.collection.count() == 0:
            return []

        query_embedding = _encode([query])

        results = self.collection.query(
            query_embeddings=query_embedding,
            n_results=n_results,
            include=["documents", "metadatas", "distances"],
        )

        docs = []
        if results.get("documents") and results["documents"][0]:
            for i, doc in enumerate(results["documents"][0]):
                distance = (
                    results.get("distances", [[0]])[0][i]
                    if results.get("distances")
                    else 0
                )
                # cosine distance: 0=完全相同, 2=完全相反 → 转为 0-1 的相似度
                similarity = 1 - (distance / 2)
                if similarity >= min_similarity:
                    metadata = (
                        results.get("metadatas", [[{}]])[0][i]
                        if results.get("metadatas") and results["metadatas"][0]
                        else {}
                    )
                    docs.append({
                        "content": doc,
                        "score": round(similarity, 3),
                        "metadata": metadata,
                    })

        return docs

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
