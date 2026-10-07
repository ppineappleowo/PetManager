"""知识检索评测入口；默认只输出待人工评审清单，不调用模型。"""
import argparse
import json
from pathlib import Path
from time import perf_counter

ROOT=Path(__file__).resolve().parents[1]


def evaluate(cases,results):
    by_id={item['id']:item for item in results}
    scored=[]
    for case in cases:
        result=by_id.get(case['id'])
        sources=result.get('sources',[]) if result else []
        names=[item.get('source','') if isinstance(item,dict) else item for item in sources]
        expected=case['expected_sources']
        scored.append({**case,'recorded':result is not None,'sources':names,
            'source_hit':any(name in names for name in expected) if expected and result else None,
            'answer':result.get('answer','') if result else '',
            'elapsed_ms':result.get('elapsed_ms') if result else None,'review_status':'待人工核实'})
    rated=[item for item in scored if item['source_hit'] is not None]
    return {'cases':scored,'source_hit_rate':sum(item['source_hit'] for item in rated)/len(rated) if rated else None,
        'rated_cases':len(rated),'total_cases':len(cases),'note':'来源命中率不代表回答事实正确性或医疗安全性。'}


def retrieve(cases):
    import dashscope
    from app.core.config import get_settings
    from app.services.ai.retrieval import RAGManager
    settings=get_settings()
    if not settings.dashscope_api_key:raise RuntimeError('DASHSCOPE_API_KEY 未配置')
    dashscope.api_key=settings.dashscope_api_key
    rag=RAGManager(settings.chroma_persist_dir,settings.chroma_collection_name,settings.embedding_model,
        settings.embedding_dim,settings.embedding_batch_size,settings.rerank_model)
    try:
        results=[]
        for case in cases:
            start=perf_counter()
            matches=rag.search(case['question'],n_results=settings.rag_top_n,min_similarity=settings.rag_min_similarity)
            results.append({'id':case['id'],'sources':[item['metadata'] for item in matches],'elapsed_ms':round((perf_counter()-start)*1000,1)})
        return results
    finally:rag.repository.close()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--cases',type=Path,default=ROOT/'resources/evaluations/ai_cases.json')
    mode=parser.add_mutually_exclusive_group()
    mode.add_argument('--results',type=Path,help='人工收集的 id/answer/sources 记录')
    mode.add_argument('--retrieve',action='store_true',help='调用配置的 Embedding/Rerank 服务，仅评测检索')
    parser.add_argument('--output',type=Path,default=ROOT/'resources/reports/ai-evaluation.json')
    args=parser.parse_args()
    cases=json.loads(args.cases.read_text(encoding='utf8'))
    results=retrieve(cases) if args.retrieve else json.loads(args.results.read_text(encoding='utf8')) if args.results else []
    report=evaluate(cases,results)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(f"评测条目 {len(cases)}，已评分 {report['rated_cases']}。报告：{args.output}")


if __name__=='__main__':main()
