"""
RAG 知识库测试脚本
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

# 初始化
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_RAG_DIR = os.path.join(_BASE_DIR, "resources", "pet_rag_db")
rag = RAGManager(persist_dir=_RAG_DIR)

# ====================== 测试用例 ======================
test_queries = [
    "狗狗感冒了怎么办",         # 匹配：犬类常见病.txt（犬窝咳等）
    "猫咪应该怎么喂食",         # 匹配：猫类喂养指南.txt
    "宠物疫苗什么时候打",       # 匹配：宠物疫苗接种.txt
    "比特币价格预测",           # 不匹配：RAG 库无相关内容 → 应回退到 web_search
    "狗狗得了细小病毒有什么症状", # 匹配：犬类常见病.txt（细小病毒）
]

print("=" * 60)
print("RAG 知识库测试")
print(f"知识库文档数: {rag.get_stats()['document_count']}")
print("=" * 60)

for query in test_queries:
    print(f"\n[查询] \"{query}\"")
    results = rag.search(query, n_results=2)

    if results:
        top = results[0]
        print(f"  [RAG命中] 相关度: {top['score']}")
        print(f"     来源: {top['metadata'].get('source', '未知')}")
        print(f"     内容预览: {top['content'][:80]}...")
        if len(results) > 1:
            print(f"     次匹配: {results[1]['metadata'].get('source', '未知')} (相关度: {results[1]['score']})")
    else:
        print(f"  [RAG未命中] -> 应回退到 web_search")
