from io import BytesIO
import logging
import warnings
from PIL import Image, ImageOps, UnidentifiedImageError
from app.core.errors import BusinessError

def prepare_image(data):
    if not data or len(data) > 10 * 1024 * 1024:
        raise BusinessError(422, '每张图片必须大于 0 且不超过 10 MB')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as source:
                if source.format not in ('JPEG', 'PNG', 'WEBP') or source.width * source.height > 20000000:
                    raise ValueError()
                source.load()
                image = ImageOps.exif_transpose(source).convert('RGB')
                result = []
                for size in (1600, 480):
                    copy = image.copy()
                    copy.thumbnail((size, size))
                    buffer = BytesIO()
                    copy.save(buffer, format='WEBP', quality=85)
                    result.append(buffer.getvalue())
                return result
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise BusinessError(422, '图片损坏或格式不支持，请使用 JPEG/PNG/WebP，像素不超过 2000 万') from None

def replace_avatar(users, user_id, avatar_id, media):
    old = users.set_avatar(user_id, avatar_id)
    if old:
        try:
            media.delete(old)
        except Exception:
            logging.getLogger(__name__).warning('旧头像清理失败，待清理的对象 ID：%s', old)
    return {'avatar_id': avatar_id}

def upload_avatar(users, user_id, data, media):
    from uuid import uuid4
    images = prepare_image(data)
    avatar_id = uuid4().hex
    try:
        media.put(avatar_id, [images[1], images[1]])
        return replace_avatar(users, user_id, avatar_id, media)
    except Exception:
        try:
            media.delete(avatar_id)
        except Exception:
            logging.getLogger(__name__).warning('未完成头像上传需清理：%s', avatar_id)
        raise

def upload_post_image(community, user_id, data, media):
    images = prepare_image(data)
    media_id = community.new_media(user_id)
    media.put(media_id, images)
    community.ready_media(media_id)
    return {'id': media_id}
