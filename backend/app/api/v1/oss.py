from fastapi import Depends, Query
from app.api.errors import ApiRouter
from app.api.dependencies import get_settings, get_current_user
from app.core.config import Settings
from app.services.oss_signing import presign_image

router = ApiRouter()

@router.get('/oss/presign')
def generate_presigned_url(filename: str = Query(..., description='上传文件名（含扩展名）'), settings: Settings = Depends(get_settings), current_user: dict = Depends(get_current_user)):
    return presign_image(settings, current_user['id'], filename)
