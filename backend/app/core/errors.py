"""业务失败类型；不导入 FastAPI，HTTP 映射在 api/errors.py。"""


class BusinessError(Exception):
    def __init__(self, status_code, detail, headers=None):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail
        self.headers = headers
