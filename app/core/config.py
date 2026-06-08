"""
统一配置管理 —— 使用 Pydantic Settings 作为所有配置的单一来源。

所有环境变量和硬编码的配置项集中在此，支持 .env 文件自动加载。
使用方式:
    from app.core.config import get_settings
    settings = get_settings()
    model_name = settings.llm_model
"""

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


# ==================== 项目路径常量 ====================
# 从当前文件向上 3 级: app/core/config.py → 项目根
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    """应用全局配置

    配置优先级（从高到低）:
    1. 环境变量
    2. .env 文件
    3. 此处的默认值
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ==================== LLM 大模型 ====================
    llm_model: str = "qwen3.5-omni-plus"
    llm_provider: str = "openai"
    dashscope_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    dashscope_api_key: str = ""

    # ==================== Embedding 向量化 ====================
    embedding_model: str = "text-embedding-v2"
    embedding_dim: int = 1536
    embedding_batch_size: int = 20

    # ==================== Reranker 精排 ====================
    rerank_model: str = "qwen3-rerank"
    rerank_batch_size: int = 25

    # ==================== RAG 知识库 ====================
    rag_chunk_size: int = 500
    rag_chunk_overlap: int = 100
    rag_min_similarity: float = 0.3
    rag_recall_multiplier: int = 5
    rag_top_n: int = 3
    rag_query_expand_n: int = 3

    # ==================== ChromaDB 向量数据库 ====================
    chroma_collection_name: str = "pet_knowledge"

    # ==================== 文档加载 ====================
    # 注意: 列表类型在 .env 中需要用 JSON 数组格式，如 '["a","b"]'
    rag_supported_exts: list[str] = [".txt", ".md", ".pdf", ".docx"]

    # ==================== Web 搜索 (Tavily) ====================
    tavily_api_key: str = ""
    tavily_max_results: int = 5
    tavily_topic: str = "general"

    # ==================== 阿里云 OSS ====================
    oss_endpoint: str = "oss-cn-beijing.aliyuncs.com"
    oss_bucket: str = ""
    oss_region: str = "cn-beijing"
    oss_access_key_id: str = ""
    oss_access_key_secret: str = ""

    # ==================== 服务器 ====================
    server_host: str = "127.0.0.1"
    server_port: int = 8001

    # ==================== LangSmith ====================
    langsmith_tracing: bool = False
    langsmith_api_key: str = ""
    langsmith_project: str = "AIdemo"

    # ==================== 推导路径（properties，不可通过 env 覆写） ====================
    @property
    def project_root(self) -> Path:
        return _PROJECT_ROOT

    @property
    def resources_dir(self) -> Path:
        return _PROJECT_ROOT / "resources"

    @property
    def chroma_persist_dir(self) -> str:
        return str(self.resources_dir / "pet_rag_db")

    @property
    def rag_docs_dir(self) -> str:
        return str(self.resources_dir / "rag_docs")

    @property
    def db_full_path(self) -> str:
        return str(self.resources_dir / "pet.db")


# ==================== 单例工厂 ====================
_settings: Settings | None = None


def get_settings() -> Settings:
    """获取 Settings 单例。

    首次调用时从 .env 加载，后续调用返回同一实例。
    确保整个应用使用一致的配置，且 .env 只被读取一次。
    """
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reset_settings() -> None:
    """重置 Settings 单例（仅用于测试）。"""
    global _settings
    _settings = None
