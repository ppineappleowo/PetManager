"""清理至少 24 小时未引用的社区图片：uv run python -m app.clean_community_media。"""
from app.core.config import get_settings
from app.services.community.posts import CommunityService
from app.infrastructure.storage.community import CommunityMedia
from app.database.setup import initialize_database

if __name__ == '__main__':
    settings = get_settings()
    url = settings.database_url.get_secret_value()
    initialize_database(url)
    store = CommunityService(url)
    try:
        print(f'已清理 {store.clean_media(CommunityMedia(settings))} 张无引用图片')
    finally:
        store.close()
