import alibabacloud_oss_v2 as oss
from app.core.errors import BusinessError
from app.infrastructure.storage.client import _get_oss_client

class CommunityMedia:

    def __init__(self, settings):
        self.settings = settings

    def client(self):
        if not all((self.settings.oss_bucket, self.settings.oss_access_key_id, self.settings.oss_access_key_secret)):
            raise BusinessError(503, '图片存储尚未配置，请稍后再试或发布纯文字')
        return _get_oss_client(self.settings)

    @staticmethod
    def key(media_id, thumbnail=False):
        return f'community/{media_id}/{('thumb' if thumbnail else 'image')}.webp'

    def put(self, media_id, images):
        client = self.client()
        try:
            for thumbnail, data in zip((False, True), images):
                client.put_object(oss.PutObjectRequest(bucket=self.settings.oss_bucket, key=self.key(media_id, thumbnail), body=data, content_type='image/webp', acl='private'))
        except Exception:
            raise BusinessError(503, '图片上传失败，请重试') from None

    def get(self, media_id, thumbnail=False):
        client = self.client()
        try:
            response = client.get_object(oss.GetObjectRequest(bucket=self.settings.oss_bucket, key=self.key(media_id, thumbnail)))
            try:
                return response.body.read()
            finally:
                response.body.close()
        except Exception:
            raise BusinessError(503, '图片暂时不可用') from None

    def delete(self, media_id):
        client = self.client()
        for thumbnail in (False, True):
            client.delete_object(oss.DeleteObjectRequest(bucket=self.settings.oss_bucket, key=self.key(media_id, thumbnail)))
