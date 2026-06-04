"""
RAG 知识库测试脚本（多查询扩展 + 粗排 + 精排）
用法: python test_rag.py
"""
import sys
import os

# 确保项目根目录在 path 中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from app.common.rag_manager import RAGManager
from app.common.logger import setup_logging
setup_logging()

# ====================== 初始化 LLM（仅用于查询扩展） ======================
from langchain.chat_models import init_chat_model

model = init_chat_model(
    model="qwen3.5-omni-plus",
    model_provider="openai",
    base_url=os.getenv("DASHSCOPE_BASE_URL"),
    api_key=os.getenv("DASHSCOPE_API_KEY"),
)

# ====================== 初始化 RAG ======================
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_RAG_DIR = os.path.join(_BASE_DIR, "resources", "pet_rag_db")
rag = RAGManager(persist_dir=_RAG_DIR)


# ====================== 查询扩展 ======================
_QUERY_EXPAND_PROMPT = """你是一个搜索查询优化器。将以下用户问题改写为 {n} 个不同角度的搜索查询。

要求：
- 每个查询从不同维度或使用不同措辞表达同一问题
- 用关键词组合，简洁直接，不要完整句子
- 保持原始问题的核心意图
- 每行一个查询，不要编号、不要引号

原始问题: {query}

改写查询:"""


def _expand_query(query: str, n: int = 3) -> list[str]:
    """使用 LLM 将用户查询扩展为多个搜索变体"""
    import re

    prompt = _QUERY_EXPAND_PROMPT.format(query=query, n=n)
    try:
        response = model.invoke(prompt)
        lines = [
            re.sub(r'^[\d]+[\.\、\)\s]+', '', line).strip()
            for line in response.content.strip().split("\n")
            if line.strip()
        ]
    except Exception as e:
        print(f"  [查询扩展失败] {e}，使用原始查询")
        return [query]

    seen = {query}
    variants = [query]
    for line in lines:
        if line not in seen and len(variants) < n:
            seen.add(line)
            variants.append(line)
    return variants


# ====================== 多查询搜索 ======================
def multi_search(query: str, n_results: int = 3) -> list[dict]:
    """多查询扩展 + 粗排并行搜索 + 合并去重 + 统一精排"""
    queries = _expand_query(query, n=3)

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
    rerank_input = all_candidates[:n_results * 3]
    final = rag.rerank_documents(query=query, candidates=rerank_input, top_n=n_results)
    return final


# ====================== 测试用例 ======================
test_queries = [
    "狗狗感冒了怎么办",         # 匹配：犬类常见病.txt（犬窝咳等）
    "猫咪应该怎么喂食",         # 匹配：猫类喂养指南.txt
    "宠物疫苗什么时候打",       # 匹配：宠物疫苗接种.txt
    "比特币价格预测",           # 不匹配：RAG 库无相关内容
    "狗狗得了细小病毒有什么症状", # 匹配：犬类常见病.txt（细小病毒）
]

print("=" * 60)
print("RAG 知识库测试 — 多查询扩展 + 粗排 + 精排")
print(f"知识库文档数: {rag.get_stats()['document_count']}")
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
            print(f"      次匹配: {results[1]['metadata'].get('source', '未知')} (相关度: {results[1]['score']})")
    else:
        print(f"\n  >> [RAG未命中] -> 应回退到 web_search")
