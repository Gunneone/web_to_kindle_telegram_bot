"""
Errors the API answers with `{"error": {"code": ...}}`; the client translates the code.
"""


class ApiError(Exception):
    def __init__(self, status: int, code: str, **extra):
        super().__init__(code)
        self.status = status
        self.code = code
        self.extra = extra
