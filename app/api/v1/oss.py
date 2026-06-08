"""阿里云 OSS 上传签名 URL 接口"""

from datetime import timedelta

import alibabacloud_oss_v2 as oss
from fastapi import APIRouter, Depends, Query

from app.core.config import Settings
from app.core.dependencies import get_settings


router = APIRouter()

# Content-Type 映射表
_CONTENT_TYPE_MAP = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "gif": "image/gif",
    "webp": "image/webp",
}


def _get_oss_client(settings: Settings) -> oss.Client:
    """根据配置创建 OSS 客户端。

    每次调用都重新创建以确保使用最新的凭证。
    """
    # 设置临时环境变量供 SDK 读取
    import os
    os.environ["OSS_ACCESS_KEY_ID"] = settings.oss_access_key_id
    os.environ["OSS_ACCESS_KEY_SECRET"] = settings.oss_access_key_secret

    credentials_provider = (
        oss.credentials.EnvironmentVariableCredentialsProvider()
    )
    cfg = oss.config.load_default()
    cfg.credentials_provider = credentials_provider
    cfg.region = settings.oss_region

    return oss.Client(cfg)


@router.get("/oss/presign")
def generate_presigned_url(
    filename: str = Query(..., description="上传文件名（含扩展名）"),
    settings: Settings = Depends(get_settings),
):
    """生成 OSS 预签名上传 URL。

    Returns:
        uploadUrl: 预签名上传 URL（有效期 1 小时）
        contentType: 文件 MIME 类型
        accessUrl: 上传后的公开访问 URL
    """
    # 根据扩展名推断 Content-Type
    ext = filename.split(".")[-1].lower() if "." in filename else "jpg"
    content_type = _CONTENT_TYPE_MAP.get(ext, "application/octet-stream")

    client = _get_oss_client(settings)
    pre_result = client.presign(
        oss.PutObjectRequest(
            bucket=settings.oss_bucket,
            key=filename,
            content_type=content_type,
        ),
        expires=timedelta(seconds=3600),
    )

    return {
        "uploadUrl": pre_result.url.strip('"'),
        "contentType": content_type,
        "accessUrl": (
            f"https://{settings.oss_bucket}.{settings.oss_endpoint}/{filename}"
        ),
    }
