from datetime import timedelta
from uuid import uuid4
import alibabacloud_oss_v2 as oss
from app.infrastructure.storage.client import _get_oss_client

_CONTENT_TYPE_MAP = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "gif": "image/gif",
    "webp": "image/webp",
}


def presign_image(settings, user_id, filename):
    # 根据扩展名推断 Content-Type
    ext = filename.split(".")[-1].lower() if "." in filename else "jpg"
    content_type = _CONTENT_TYPE_MAP.get(ext, "application/octet-stream")
    if ext not in _CONTENT_TYPE_MAP:
        from app.core.errors import BusinessError
        raise BusinessError(400, "只支持 JPG、PNG、GIF、WebP 图片")
    object_key = f"users/{user_id}/{uuid4().hex}.{ext}"

    client = _get_oss_client(settings)
    pre_result = client.presign(
        oss.PutObjectRequest(
            bucket=settings.oss_bucket,
            key=object_key,
            content_type=content_type,
        ),
        expires=timedelta(seconds=3600),
    )

    return {
        "uploadUrl": pre_result.url.strip('"'),
        "contentType": content_type,
        "accessUrl": (
            f"https://{settings.oss_bucket}.{settings.oss_endpoint}/{object_key}"
        ),
    }
