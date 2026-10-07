from app.infrastructure.storage.community import CommunityMedia

class AvatarMedia(CommunityMedia):
    @staticmethod
    def key(media_id, thumbnail=False):
        return f'avatars/{media_id}/{"thumb" if thumbnail else "image"}.webp'
