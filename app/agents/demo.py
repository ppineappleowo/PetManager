import os
from langchain.chat_models import init_chat_model
from langchain_tavily import TavilySearch
from langchain.agents import create_agent
from langchain.tools import tool
from langchain.messages import HumanMessage, AIMessage, AIMessageChunk
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader, Docx2txtLoader
import sqlite3
from langgraph.checkpoint.sqlite import SqliteSaver
from app.common.logger import logger
from app.common.rag_manager import RAGManager
from dotenv import load_dotenv

load_dotenv()

# ==================== 项目路径 ====================
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ==================== 模型 ====================
model = init_chat_model(
    model="qwen3.5-omni-plus",
    model_provider="openai",
    base_url=os.getenv("DASHSCOPE_BASE_URL"),
    api_key=os.getenv("DASHSCOPE_API_KEY"),
)

# ==================== SQLite 对话存储 ====================
_DB_PATH = os.path.join(_BASE_DIR, "resources", "pet.db")
os.makedirs(os.path.dirname(_DB_PATH), exist_ok=True)

connection = sqlite3.connect(_DB_PATH, check_same_thread=False)
checkpointer = SqliteSaver(connection)
checkpointer.setup()

# ==================== RAG 知识库 ====================
_RAG_DIR = os.path.join(_BASE_DIR, "resources", "pet_rag_db")
rag_manager = RAGManager(persist_dir=_RAG_DIR)


# ==================== RAG 知识库目录 ====================
_RAG_DOCS_DIR = os.path.join(_BASE_DIR, "resources", "rag_docs")
os.makedirs(_RAG_DOCS_DIR, exist_ok=True)


# ==================== 从文件夹加载知识库 ====================
# ==================== 支持的文件格式 ====================
_SUPPORTED_EXTS = {".txt", ".md", ".pdf", ".docx"}


def _get_docs_hash() -> str:
    """计算 rag_docs 目录下所有支持文件的哈希值，用于检测更新"""
    import hashlib
    hasher = hashlib.md5()
    if not os.path.isdir(_RAG_DOCS_DIR):
        return ""
    for fname in sorted(os.listdir(_RAG_DOCS_DIR)):
        ext = os.path.splitext(fname)[1].lower()
        if ext in _SUPPORTED_EXTS:
            fpath = os.path.join(_RAG_DOCS_DIR, fname)
            with open(fpath, "rb") as f:
                hasher.update(fname.encode())
                hasher.update(f.read())
    return hasher.hexdigest()


def _read_text_file(fpath: str) -> str | None:
    """读取纯文本文件，编码回退 UTF-8 → GBK"""
    try:
        with open(fpath, "r", encoding="utf-8") as f:
            return f.read().strip()
    except UnicodeDecodeError:
        with open(fpath, "r", encoding="gbk") as f:
            return f.read().strip()


def _load_file_as_docs(fpath: str, fname: str) -> list[Document]:
    """按扩展名选择合适的 loader 加载单个文件"""
    ext = os.path.splitext(fname)[1].lower()
    source = os.path.splitext(fname)[0]

    # ── 纯文本：使用自己的编码回退方案（比 TextLoader.autodetect_encoding 更可靠） ──
    if ext in (".txt", ".md"):
        content = _read_text_file(fpath)
        if content:
            return [Document(page_content=content, metadata={"source": source})]
        return []

    # ── PDF ──
    if ext == ".pdf":
        loader = PyPDFLoader(fpath)
        docs = loader.load()
        for d in docs:
            d.metadata["source"] = source
        return docs

    # ── Word ──
    if ext == ".docx":
        loader = Docx2txtLoader(fpath)
        docs = loader.load()
        for d in docs:
            d.metadata["source"] = source
        return docs

    return []


def _load_knowledge_base():
    """加载 rag_docs 目录下的文档（支持 txt/md/pdf/docx），分块后同步到 ChromaDB"""
    current_hash = _get_docs_hash()

    # 检查是否需要更新
    existing_count = rag_manager.get_stats()["document_count"]
    try:
        stored_hash = rag_manager.collection.metadata.get("docs_hash", "")
    except Exception:
        stored_hash = ""

    if existing_count > 0 and current_hash == stored_hash:
        logger.info(f"知识库未变化，跳过加载（{existing_count} 个 chunk）")
        return

    # 有变化：清空重建
    if existing_count > 0:
        logger.info("检测到知识库文件变化，重新索引...")
        rag_manager.delete_collection()

    if not os.path.isdir(_RAG_DOCS_DIR):
        logger.warning(f"知识库目录不存在: {_RAG_DOCS_DIR}")
        return

    # === Step 1: 按扩展名分发 loader，统一生成 Document 对象 ===
    raw_docs: list[Document] = []
    stats: dict[str, int] = {}  # 统计各格式数量

    for fname in sorted(os.listdir(_RAG_DOCS_DIR)):
        ext = os.path.splitext(fname)[1].lower()
        if ext not in _SUPPORTED_EXTS:
            continue
        fpath = os.path.join(_RAG_DOCS_DIR, fname)
        try:
            docs = _load_file_as_docs(fpath, fname)
            if docs:
                raw_docs.extend(docs)
                stats[ext] = stats.get(ext, 0) + 1
        except Exception as e:
            logger.warning(f"加载文件失败 {fname}: {e}")

    if not raw_docs:
        logger.warning(f"知识库目录为空，未加载任何文档 ({_RAG_DOCS_DIR})")
        return

    logger.info(f"文档加载完成: {' | '.join(f'{v} {k}' for k, v in sorted(stats.items()))}")

    # === Step 2: LangChain RecursiveCharacterTextSplitter 语义分块 ===
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=100,
        separators=["\n\n", "\n", "。", ".", "！", "？", " ", ""],
    )
    chunks = splitter.split_documents(raw_docs)
    logger.info(f"文档分块完成: {len(raw_docs)} 篇 → {len(chunks)} 个 chunk")

    # === Step 3: 写入 ChromaDB ===
    rag_manager.add_documents(
        documents=[chunk.page_content for chunk in chunks],
        metadatas=[chunk.metadata for chunk in chunks],
    )
    rag_manager.collection.modify(metadata={"docs_hash": current_hash})
    logger.info(f"知识库加载完成: {len(chunks)} 个 chunk (来自 {_RAG_DOCS_DIR})")


# 启动时加载知识库
_load_knowledge_base()

# ==================== 网络搜索 ====================
web_search = TavilySearch(
    max_results=5,
    topic="general",
)


# ==================== 多 Query 扩展 ====================
_QUERY_EXPAND_PROMPT = """你是一个搜索查询优化器。将以下用户问题改写为 {n} 个不同角度的搜索查询。

要求：
- 每个查询从不同维度或使用不同措辞表达同一问题
- 用关键词组合，简洁直接，不要完整句子
- 保持原始问题的核心意图
- 每行一个查询，不要编号、不要引号

原始问题: {query}

改写查询:"""


def _expand_query(query: str, n: int = 3) -> list[str]:
    """使用 LLM 将用户查询扩展为多个搜索变体，提高召回率"""
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
        logger.warning(f"查询扩展失败: {e}，使用原始查询")
        return [query]

    # 去重并保留原始查询 + 扩展查询
    seen = {query}
    variants = [query]
    for line in lines:
        if line not in seen and len(variants) < n:
            seen.add(line)
            variants.append(line)

    if len(variants) > 1:
        logger.info(f"查询扩展: {len(variants)} 个变体 → {variants}")
    return variants


# ==================== RAG + 网络搜索 联合工具 ====================
@tool
def pet_knowledge_search(query: str) -> str:
    """
    搜索宠物养护知识。
    优先从本地RAG宠物知识库查询，若本地查不到或相关性不足则自动从网络搜索。
    用于查找宠物喂养、洗护、训练、疾病、疫苗、驱虫、急救等各类宠物养护信息。
    """
    logger.info(f"[知识搜索]: {query}")

    # Step 0: 扩展查询（生成多个搜索变体）
    queries = _expand_query(query, n=3)

    # Step 1: 多查询并行搜索 RAG（粗排模式，不做精排）
    all_candidates: list[dict] = []
    seen_fingerprint: set[str] = set()

    for q in queries:
        try:
            results = rag_manager.search(q, n_results=3, use_rerank=False)
            for doc in results:
                # 用内容前 80 字符做指纹去重
                fp = doc["content"][:80]
                if fp not in seen_fingerprint:
                    seen_fingerprint.add(fp)
                    all_candidates.append(doc)
        except Exception as e:
            logger.warning(f"子查询 '{q[:30]}...' 搜索异常: {e}")

    if not all_candidates:
        # Step 2: RAG 无结果，回退到网络搜索
        logger.info("多查询搜索无结果，回退到网络搜索")
        try:
            web_result = web_search.invoke({"query": f"宠物养护 {query}"})
            return "【网络搜索结果】\n\n" + str(web_result)
        except Exception as e:
            logger.error(f"网络搜索失败: {e}")
            return "未找到相关信息，请基于自身知识回答用户问题。"

    # 按粗排分排序后取 Top-9 给精排
    all_candidates.sort(key=lambda x: x["score"], reverse=True)
    rerank_input = all_candidates[:9]

    logger.info(
        f"多查询合并: {len(queries)} 子查询 → 去重后 {len(all_candidates)} 条 → "
        f"送精排 {len(rerank_input)} 条"
    )

    # Step 3: 统一精排
    rag_results = rag_manager.rerank_documents(
        query=query,
        candidates=rerank_input,
        top_n=3,
    )

    docs_text = []
    for i, doc in enumerate(rag_results):
        source = doc.get("metadata", {}).get("source", "未知来源")
        docs_text.append(
            f"{i + 1}. [{source}] (相关度: {doc['score']})\n{doc['content']}"
        )
    logger.info(f"RAG命中 {len(rag_results)} 条，最高相关度: {rag_results[0]['score']}")
    return (
        "【本地宠物知识库检索结果】\n\n"
        + "\n\n---\n\n".join(docs_text)
        + "\n\n（以上信息来自本地宠物养护知识库）"
    )


# ==================== Agent ====================
system_prompt = """
你是一名专业的AI宠物管家。收到用户提供的宠物照片、视频或饮食/行为描述后，请按以下流程操作：

1. 宠物识别与评估: 若用户提供照片或视频, 首先辨识宠物的品种、年龄范围、体型特征。基于宠物的外观状态(毛发、眼睛、体态等),
评估其精神状态与健康状态, 整理出一份"宠物基本档案"(品种、预估年龄、体型、精神状态、健康状态)。

2. 智能养护方案定制: 优先调用pet_knowledge_search工具搜索宠物养护知识。本地知识库包含犬猫喂养、洗护、训练、疾病、疫苗
驱虫、急救等专业信息，优先参考。若本地库无相关内容，工具会自动回退到网络搜索。

3. 多维度评估与排序: 从实用性、科学性和可操作性三个维度对检索到的信息进行量化打分, 并根据得分排序, 最实用且科学的建议
排名靠前。

4. 结构化方案输出: 把排序后的建议整理为一份结构清晰的宠物养护报告, 包含宠物档案、养护建议、得分、推荐理由、参考图片,
帮助用户科学养护宠物。

请严格按照流程, 优先调用pet_knowledge_search工具搜索知识, 搜索不到的情况下才能基于自身知识发挥。
"""

agent = create_agent(
    model=model,
    system_prompt=system_prompt,
    tools=[pet_knowledge_search],
    checkpointer=checkpointer,
)


# ==================== 流式对话 ====================
async def pet_consult(prompt: str, image: str, thread_id: str):
    """调用agent进行宠物养护咨询"""
    logger.info(f"[用户咨询]: {prompt}, image: {image}, thread_id: {thread_id}")
    try:
        if not image or image.strip() == "":
            message = HumanMessage(content=prompt)
        else:
            message = HumanMessage(content=[
                {"type": "image", "url": image},
                {"type": "text", "text": prompt},
            ])

        for chunk, metadata in agent.stream(
            {"messages": [message]},
            {"configurable": {"thread_id": thread_id}},
            stream_mode="messages",
        ):
            if isinstance(chunk, AIMessageChunk) and chunk.content:
                yield chunk.content

    except Exception as e:
        logger.error(f"\n[错误]: {str(e)}")
        yield "信息检索失败，试试看手动输入宠物情况？"


# ==================== 会话管理 ====================
def list_threads() -> list[dict]:
    """获取所有会话列表"""
    cursor = connection.cursor()
    try:
        cursor.execute(
            "SELECT DISTINCT thread_id FROM checkpoints ORDER BY thread_id DESC"
        )
        rows = cursor.fetchall()
    except Exception:
        return []

    threads = []
    for row in rows:
        thread_id = row[0]
        title = "新会话"
        messages = get_messages(thread_id)
        for m in messages:
            if m["role"] == "user":
                content = m["content"]
                if isinstance(content, list):
                    text_parts = [
                        c.get("text", "") for c in content
                        if isinstance(c, dict) and c.get("text")
                    ]
                    content = " ".join(text_parts) if text_parts else "[图片]"
                title = str(content)[:50]
                break

        threads.append({
            "thread_id": thread_id,
            "title": title,
            "message_count": len(messages),
        })

    return threads


def clear_messages(thread_id: str):
    """清空会话"""
    logger.info(f"清空历史消息，thread_id: {thread_id}")
    checkpointer.delete_thread(thread_id)


def get_messages(thread_id: str) -> list[dict[str, str]]:
    """获取会话历史"""
    logger.info(f"获取历史消息，thread_id: {thread_id}")

    checkpoint = checkpointer.get({"configurable": {"thread_id": thread_id}})
    if not checkpoint:
        return []

    channel_values = checkpoint.get("channel_values")
    if not channel_values:
        return []

    messages = channel_values.get("messages", [])
    if not messages:
        return []

    result = []
    for msg in messages:
        if not msg.content:
            continue

        if isinstance(msg, HumanMessage):
            content = msg.content
            image_url = None
            if isinstance(content, list):
                text_parts = []
                for part in content:
                    if isinstance(part, dict):
                        if part.get("type") == "image":
                            image_url = part.get("url", "")
                        elif part.get("type") == "text":
                            text_parts.append(part.get("text", ""))
                    elif isinstance(part, str):
                        text_parts.append(part)
                content = " ".join(text_parts) if text_parts else ""
            result.append({
                "role": "user",
                "content": content,
                "image_url": image_url,
            })
        elif isinstance(msg, AIMessage):
            result.append({"role": "assistant", "content": msg.content})

    return result


# ==================== RAG 知识库管理 ====================
def rag_add_documents(documents: list[str]) -> int:
    """向 RAG 知识库添加文档"""
    return rag_manager.add_documents(documents)


def rag_clear():
    """清空 RAG 知识库并重新从文件加载"""
    rag_manager.delete_collection()
    _load_knowledge_base()


def rag_get_stats() -> dict:
    """获取 RAG 知识库统计"""
    return rag_manager.get_stats()
