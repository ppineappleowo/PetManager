import alibabacloud_oss_v2 as oss
from app.core.config import Settings

def _get_oss_client(settings: Settings) -> oss.Client:
    """根据配置创建 OSS 客户端。

    每次调用都重新创建以确保使用最新的凭证。
    """
    import os
    os.environ['OSS_ACCESS_KEY_ID'] = settings.oss_access_key_id
    os.environ['OSS_ACCESS_KEY_SECRET'] = settings.oss_access_key_secret
    credentials_provider = oss.credentials.EnvironmentVariableCredentialsProvider()
    cfg = oss.config.load_default()
    cfg.credentials_provider = credentials_provider
    cfg.region = settings.oss_region
    return oss.Client(cfg)
