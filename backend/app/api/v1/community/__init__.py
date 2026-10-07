"""社区路由装配；各子模块只处理 HTTP 输入输出。"""
from app.api.errors import ApiRouter
from . import posts, pets, profiles, social, interactions, moderation, media, bookmarks, notifications, report_feedback
router = ApiRouter(prefix='/community')
for module in (posts, pets, profiles, social, interactions, moderation, media, bookmarks, notifications, report_feedback):
    router.include_router(module.router)
