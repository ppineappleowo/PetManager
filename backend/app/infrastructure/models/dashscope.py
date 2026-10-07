from typing import List
import time
from dashscope import TextEmbedding, TextReRank as _TextReRank

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
