"""
AI 宠物管家 Agent 服务

封装了 LLM 模型、RAG 知识库、对话 Agent、会话管理的完整生命周期。
所有依赖通过构造函数注入，无模块级全局状态。

使用方式（通过 FastAPI 依赖注入）:
    pet_service = request.app.state.pet_agent_service
    async for chunk in pet_service.consult(prompt, image, thread_id):
        ...
"""

import os
import re
import hashlib
import sqlite3
from typing import AsyncGenerator

from langchain.chat_models import init_chat_model
from langchain_tavily import TavilySearch
from langchain.agents import create_agent
from langchain.tools import tool
from langchain.messages import HumanMessage, AIMessage, AIMessageChunk
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader, Docx2txtLoader
from langgraph.checkpoint.sqlite import SqliteSaver

from app.common.logger import logger
from app.common.rag_manager import RAGManager
from app.core.config import Settings


# ==================== Prompt 模板（类级别常量） ====================

_QUERY_EXPAND_PROMPT = """你是一个搜索查询优化器。将以下用户问题改写为 {n} 个不同角度的搜索查询。

要求：
- 每个查询从不同维度或使用不同措辞表达同一问题
- 用关键词组合，简洁直接，不要完整句子
- 保持原始问题的核心意图
- 每行一个查询，不要编号、不要引号

原始问题: {query}

改写查询:"""

_SYSTEM_PROMPT = """
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

# 支持加载的文档格式
_SUPPORTED_EXTS = frozenset({".txt", ".md", ".pdf", ".docx"})


# ==================== Query 扩展（模块级工具函数） ====================

def _expand_query_impl(query: str, model, n: int = 3) -> list[str]:
    """使用 LLM 将用户查询扩展为多个搜索变体，提高召回率。

    Args:
        query: 原始查询文本。
        model: LLM 模型实例（需支持 invoke）。
        n: 期望生成的变体数量（含原始查询）。

    Returns:
        去重后的查询变体列表，第一条始终为原始查询。
    """
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

    seen = {query}
    variants = [query]
    for line in lines:
        if line not in seen and len(variants) < n:
            seen.add(line)
            variants.append(line)

    if len(variants) > 1:
        logger.info(f"查询扩展: {len(variants)} 个变体 → {variants}")
    return variants


# ==================== 文件读取工具（模块级） ====================

def _read_text_file(fpath: str) -> str | None:
    """读取纯文本文件，编码回退 UTF-8 → GBK。"""
    try:
        with open(fpath, "r", encoding="utf-8") as f:
            return f.read().strip()
    except UnicodeDecodeError:
        with open(fpath, "r", encoding="gbk") as f:
            return f.read().strip()


def _load_file_as_docs(fpath: str, fname: str) -> list[Document]:
    """按扩展名选择合适的 loader 加载单个文件为 Document 列表。"""
    ext = os.path.splitext(fname)[1].lower()
    source = os.path.splitext(fname)[0]

    if ext in (".txt", ".md"):
        content = _read_text_file(fpath)
        if content:
            return [Document(page_content=content, metadata={"source": source})]
        return []

    if ext == ".pdf":
        loader = PyPDFLoader(fpath)
        docs = loader.load()
        for d in docs:
            d.metadata["source"] = source
        return docs

    if ext == ".docx":
        loader = Docx2txtLoader(fpath)
        docs = loader.load()
        for d in docs:
            d.metadata["source"] = source
        return docs

    return []


# ==================== PetAgentService ====================

class PetAgentService:
    """AI 宠物管家服务 —— 封装 LLM + RAG + Agent + 会话管理。

    所有外部依赖通过构造函数注入：
    - settings: 应用配置（Pydantic Settings）
    - rag_manager: RAG 知识库管理器

    生命周期由调用方管理：
    1. 实例化 → 初始化模型、数据库、Agent、加载知识库
    2. 调用 consult() / get_messages() 等业务方法
    3. 调用 close() 释放资源
    """

    def __init__(self, settings: Settings, rag_manager: RAGManager):
        """
        Args:
            settings: 应用配置实例。
            rag_manager: 已配置 API key 的 RAG 管理器。
        """
        self.settings = settings
        self.rag_manager = rag_manager

        # ── 1. 初始化 LLM 模型 ──
        self.model = init_chat_model(
            model=settings.llm_model,
            model_provider=settings.llm_provider,
            base_url=settings.dashscope_base_url,
            api_key=settings.dashscope_api_key,
        )
        logger.info(f"LLM 已初始化: {settings.llm_model}")

        # ── 2. 初始化 SQLite 对话存储 ──
        os.makedirs(os.path.dirname(settings.db_full_path), exist_ok=True)
        self.connection = sqlite3.connect(
            settings.db_full_path, check_same_thread=False
        )
        self.checkpointer = SqliteSaver(self.connection)
        self.checkpointer.setup()
        logger.info(f"对话存储已就绪: {settings.db_full_path}")

        # ── 3. 初始化 Web 搜索 ──
        self.web_search = TavilySearch(
            tavily_api_key=settings.tavily_api_key,
            max_results=settings.tavily_max_results,
            topic=settings.tavily_topic,
        )

        # ── 4. 创建 Agent（含知识库搜索工具） ──
        self.agent = create_agent(
            model=self.model,
            system_prompt=_SYSTEM_PROMPT,
            tools=[self._create_knowledge_tool()],
            checkpointer=self.checkpointer,
        )
        logger.info("Agent 已创建")

        # ── 5. 加载知识库 ──
        self._load_knowledge_base()

    # ==================== 知识库搜索工具 ====================

    def _create_knowledge_tool(self):
        """创建 pet_knowledge_search 工具。

        通过闭包捕获 rag_manager / model / web_search / settings 引用，
        避免模块级全局变量。
        """
        rag = self.rag_manager
        model = self.model
        web_search = self.web_search
        settings = self.settings

        @tool
        def pet_knowledge_search(query: str) -> str:
            """
            搜索宠物养护知识。
            优先从本地RAG宠物知识库查询，若本地查不到或相关性不足则自动从网络搜索。
            用于查找宠物喂养、洗护、训练、疾病、疫苗、驱虫、急救等各类宠物养护信息。
            """
            logger.info(f"[知识搜索]: {query}")

            # Step 0: 查询扩展
            queries = _expand_query_impl(
                query=query,
                model=model,
                n=settings.rag_query_expand_n,
            )

            # Step 1: 多查询并搜 RAG（粗排）
            all_candidates: list[dict] = []
            seen_fingerprint: set[str] = set()

            for q in queries:
                try:
                    results = rag.search(q, n_results=3, use_rerank=False)
                    for doc in results:
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
                    web_result = web_search.invoke(
                        {"query": f"宠物养护 {query}"}
                    )
                    return "【网络搜索结果】\n\n" + str(web_result)
                except Exception as e:
                    logger.error(f"网络搜索失败: {e}")
                    return "未找到相关信息，请基于自身知识回答用户问题。"

            # 按粗排分排序后取 Top-9 送精排
            all_candidates.sort(key=lambda x: x["score"], reverse=True)
            rerank_input = all_candidates[:9]

            logger.info(
                f"多查询合并: {len(queries)} 子查询 → "
                f"去重后 {len(all_candidates)} 条 → "
                f"送精排 {len(rerank_input)} 条"
            )

            # Step 3: 统一精排
            rag_results = rag.rerank_candidates(
                query=query,
                candidates=rerank_input,
                top_n=settings.rag_top_n,
            )

            docs_text = []
            for i, doc in enumerate(rag_results):
                source = doc.get("metadata", {}).get("source", "未知来源")
                docs_text.append(
                    f"{i + 1}. [{source}] (相关度: {doc['score']})\n{doc['content']}"
                )
            logger.info(
                f"RAG命中 {len(rag_results)} 条，"
                f"最高相关度: {rag_results[0]['score']}"
            )
            return (
                "【本地宠物知识库检索结果】\n\n"
                + "\n\n---\n\n".join(docs_text)
                + "\n\n（以上信息来自本地宠物养护知识库）"
            )

        return pet_knowledge_search

    # ==================== 知识库加载 ====================

    def _get_docs_hash(self) -> str:
        """计算 rag_docs 目录下所有支持文件的哈希值，用于检测更新。"""
        hasher = hashlib.md5()
        docs_dir = self.settings.rag_docs_dir
        if not os.path.isdir(docs_dir):
            return ""
        for fname in sorted(os.listdir(docs_dir)):
            ext = os.path.splitext(fname)[1].lower()
            if ext in _SUPPORTED_EXTS:
                fpath = os.path.join(docs_dir, fname)
                with open(fpath, "rb") as f:
                    hasher.update(fname.encode())
                    hasher.update(f.read())
        return hasher.hexdigest()

    def _load_knowledge_base(self):
        """加载 rag_docs 目录下的文档（txt/md/pdf/docx），分块后同步到 ChromaDB。

        通过比较文件哈希值实现增量更新：仅当文档变化时才重建索引。
        """
        settings = self.settings
        rag = self.rag_manager
        docs_dir = settings.rag_docs_dir

        current_hash = self._get_docs_hash()

        # 检查是否需要更新
        existing_count = rag.get_stats()["document_count"]
        try:
            stored_hash = rag.collection.metadata.get("docs_hash", "")
        except Exception:
            stored_hash = ""

        if existing_count > 0 and current_hash == stored_hash:
            logger.info(f"知识库未变化，跳过加载（{existing_count} 个 chunk）")
            return

        # 有变化：清空重建
        if existing_count > 0:
            logger.info("检测到知识库文件变化，重新索引...")
            rag.delete_collection()

        if not os.path.isdir(docs_dir):
            logger.warning(f"知识库目录不存在: {docs_dir}")
            return

        # Step 1: 按扩展名分发 loader，统一生成 Document 对象
        raw_docs: list[Document] = []
        stats: dict[str, int] = {}

        for fname in sorted(os.listdir(docs_dir)):
            ext = os.path.splitext(fname)[1].lower()
            if ext not in _SUPPORTED_EXTS:
                continue
            fpath = os.path.join(docs_dir, fname)
            try:
                docs = _load_file_as_docs(fpath, fname)
                if docs:
                    raw_docs.extend(docs)
                    stats[ext] = stats.get(ext, 0) + 1
            except Exception as e:
                logger.warning(f"加载文件失败 {fname}: {e}")

        if not raw_docs:
            logger.warning(f"知识库目录为空，未加载任何文档 ({docs_dir})")
            return

        logger.info(
            f"文档加载完成: {' | '.join(f'{v} {k}' for k, v in sorted(stats.items()))}"
        )

        # Step 2: LangChain RecursiveCharacterTextSplitter 语义分块
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.rag_chunk_size,
            chunk_overlap=settings.rag_chunk_overlap,
            separators=["\n\n", "\n", "。", ".", "！", "？", " ", ""],
        )
        chunks = splitter.split_documents(raw_docs)
        logger.info(f"文档分块完成: {len(raw_docs)} 篇 → {len(chunks)} 个 chunk")

        # Step 3: 写入 ChromaDB
        rag.add_documents(
            documents=[chunk.page_content for chunk in chunks],
            metadatas=[chunk.metadata for chunk in chunks],
        )
        rag.collection.modify(metadata={"docs_hash": current_hash})
        logger.info(
            f"知识库加载完成: {len(chunks)} 个 chunk (来自 {docs_dir})"
        )

    # ==================== 流式对话 ====================

    async def consult(
        self, prompt: str, image: str, thread_id: str, user_id: str
    ) -> AsyncGenerator[str, None]:
        """调用 Agent 进行宠物养护咨询（流式输出）。

        Args:
            prompt: 用户输入文本。
            image: 图片 URL（可为空字符串表示纯文本对话）。
            thread_id: 会话 ID，用于多轮对话上下文关联。
            user_id: 用户 ID，用于多租户隔离。
        Yields:
            流式输出的文本块。
        """
        checkpoint_ns = f"user:{user_id}"
        logger.info(
            f"[用户咨询]: {prompt}, image: {image}, "
            f"thread_id: {thread_id}, user_id: {user_id}"
        )
        try:
            if not image or image.strip() == "":
                message = HumanMessage(content=prompt)
            else:
                message = HumanMessage(content=[
                    {"type": "image", "url": image},
                    {"type": "text", "text": prompt},
                ])

            async for chunk, _metadata in self.agent.astream(
                {"messages": [message]},
                {"configurable": {"thread_id": thread_id, "checkpoint_ns": checkpoint_ns}},
                stream_mode="messages",
            ):
                if isinstance(chunk, AIMessageChunk) and chunk.content:
                    yield chunk.content

        except Exception as e:
            logger.error(f"\n[错误]: {str(e)}")
            yield "信息检索失败，试试看手动输入宠物情况？"

    # ==================== 会话管理 ====================

    def list_threads(self, user_id: str) -> list[dict]:
        """获取指定用户的会话列表，包含标题和消息数量。

        Args:
            user_id: 用户 ID，用于多租户隔离。
        Returns:
            [{"thread_id": ..., "title": ..., "message_count": ...}, ...]
        """
        checkpoint_ns = f"user:{user_id}"
        cursor = self.connection.cursor()
        try:
            cursor.execute(
                "SELECT DISTINCT thread_id FROM checkpoints "
                "WHERE checkpoint_ns = ? "
                "ORDER BY thread_id DESC",
                (checkpoint_ns,),
            )
            rows = cursor.fetchall()
        except Exception:
            return []

        threads = []
        for row in rows:
            thread_id = row[0]
            title = "新会话"
            messages = self.get_messages(thread_id, user_id)
            for m in messages:
                if m["role"] == "user":
                    content = m["content"]
                    if isinstance(content, list):
                        text_parts = [
                            c.get("text", "")
                            for c in content
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

    def clear_messages(self, thread_id: str, user_id: str):
        """清空指定用户指定会话的所有消息。

        直接执行 SQL 以确保同时过滤 thread_id 和 checkpoint_ns，
        避免 SqliteSaver.delete_thread() 仅按 thread_id 删除的局限。

        Args:
            thread_id: 会话 ID。
            user_id: 用户 ID，用于多租户隔离。
        """
        checkpoint_ns = f"user:{user_id}"
        logger.info(
            f"清空历史消息，thread_id: {thread_id}, user_id: {user_id}"
        )
        self.connection.execute(
            "DELETE FROM checkpoints WHERE thread_id = ? AND checkpoint_ns = ?",
            (thread_id, checkpoint_ns),
        )
        self.connection.execute(
            "DELETE FROM writes WHERE thread_id = ? AND checkpoint_ns = ?",
            (thread_id, checkpoint_ns),
        )
        self.connection.commit()

    def get_messages(self, thread_id: str, user_id: str) -> list[dict[str, str]]:
        """获取指定用户指定会话的历史消息。

        Args:
            thread_id: 会话 ID。
            user_id: 用户 ID，用于多租户隔离。

        Returns:
            [{"role": "user"|"assistant", "content": ..., "image_url": ...?}, ...]
        """
        checkpoint_ns = f"user:{user_id}"
        logger.info(f"获取历史消息，thread_id: {thread_id}, user_id: {user_id}")

        checkpoint = self.checkpointer.get(
            {"configurable": {"thread_id": thread_id, "checkpoint_ns": checkpoint_ns}}
        )
        if not checkpoint:
            return []

        channel_values = checkpoint.get("channel_values")
        if not channel_values:
            return []

        messages = channel_values.get("messages", [])
        if not messages:
            return []

        result: list[dict[str, str]] = []
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

    def rag_add_documents(self, documents: list[str]) -> int:
        """向 RAG 知识库添加文档。

        Args:
            documents: 文档内容字符串列表。

        Returns:
            实际添加的文档数量。
        """
        return self.rag_manager.add_documents(documents)

    def rag_clear(self):
        """清空 RAG 知识库并重新从本地文件加载。"""
        self.rag_manager.delete_collection()
        self._load_knowledge_base()

    def rag_get_stats(self) -> dict:
        """获取 RAG 知识库统计信息。"""
        return self.rag_manager.get_stats()

    # ==================== 资源释放 ====================

    def close(self):
        """关闭数据库连接，释放资源。

        应在应用关闭时调用，避免连接泄漏。
        """
        try:
            self.connection.close()
            logger.info("数据库连接已关闭")
        except Exception as e:
            logger.warning(f"关闭数据库连接时出错: {e}")
