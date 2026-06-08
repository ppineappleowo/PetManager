"""
RAG 知识库测试脚本（多查询扩展 + 粗排 + 精排）

用法: python test_rag.py
"""

import os
import sys

# 确保项目根目录在 path 中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.common.logger import setup_logging
setup_logging()

# pydantic-settings 会自动从 .env 加载，无需手动 load_dotenv()
from app.core.config import get_settings
from app.common.rag_manager import RAGManager
from app.agents.demo import _expand_query_impl

# ── 初始化 Settings ──
settings = get_settings()

# ── 配置 DashScope ──
import dashscope
dashscope.api_key = settings.dashscope_api_key

# ── 初始化 LLM（仅用于查询扩展） ──
from langchain.chat_models import init_chat_model

model = init_chat_model(
    model=settings.llm_model,
    model_provider=settings.llm_provider,
    base_url=settings.dashscope_base_url,
    api_key=settings.dashscope_api_key,
)

# ── 初始化 RAG ──
rag = RAGManager(
    persist_dir=settings.chroma_persist_dir,
    collection_name=settings.chroma_collection_name,
    embedding_model=settings.embedding_model,
    embedding_dim=settings.embedding_dim,
    embedding_batch_size=settings.embedding_batch_size,
    rerank_model=settings.rerank_model,
)


# ====================== 多查询搜索 ======================
def multi_search(query: str, n_results: int = 3) -> list[dict]:
    """多查询扩展 + 粗排并行搜索 + 合并去重 + 统一精排"""
    queries = _expand_query_impl(query, model=model, n=3)

    print(f"  查询扩展 ({len(queries)} 个变体):")
    for i, q in enumerate(queries):
        print(f"    [{i + 1}] {q}")

    # 每个变体分别粗排搜索
    all_candidates: list[dict] = []
    seen_fp: set[str] = set()

    for q in queries:
        results = rag.search(q, n_results=3, use_rerank=False)
        for doc in results:
            fp = doc["content"][:80]
            if fp not in seen_fp:
                seen_fp.add(fp)
                all_candidates.append(doc)

    if not all_candidates:
        return []

    # 去重后按粗排分排序
    all_candidates.sort(key=lambda x: x["score"], reverse=True)
    print(f"  粗排召回: {len(all_candidates)} 条（去重后）")

    # 统一精排
    rerank_input = all_candidates[: n_results * 3]
    final = rag.rerank_candidates(
        query=query, candidates=rerank_input, top_n=n_results
    )
    return final


# ====================== 测试用例 ======================
test_queries = [
    "狗狗感冒了怎么办",           # 匹配：犬类常见病.txt
    "猫咪应该怎么喂食",           # 匹配：猫类喂养指南.txt
    "宠物疫苗什么时候打",         # 匹配：宠物疫苗接种.txt
    "比特币价格预测",             # 不匹配：RAG 库无相关内容
    "狗狗得了细小病毒有什么症状",  # 匹配：犬类常见病.txt
]

print("=" * 60)
print("RAG 知识库测试 — 多查询扩展 + 粗排 + 精排")
print(f"知识库文档数: {rag.get_stats()['document_count']}")
print(
    f"Embedding: {settings.embedding_model} | "
    f"Reranker: {settings.rerank_model}"
)
print("=" * 60)

for query in test_queries:
    print(f"\n{'─' * 60}")
    print(f"[查询] \"{query}\"")
    print(f"{'─' * 60}")

    results = multi_search(query, n_results=2)

    if results:
        top = results[0]
        print(f"\n  >> [RAG命中] 相关度: {top['score']}")
        print(f"      来源: {top['metadata'].get('source', '未知')}")
        print(f"      内容预览: {top['content'][:80]}...")
        if len(results) > 1:
            src2 = results[1]["metadata"].get("source", "未知")
            print(f"      次匹配: {src2} (相关度: {results[1]['score']})")
    else:
        print("\n  >> [RAG未命中] -> 应回退到 web_search")
