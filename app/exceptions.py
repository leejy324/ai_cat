from fastapi import HTTPException, status


class BusinessException(HTTPException):
    """业务异常基类"""

    def __init__(self, detail: str, status_code: int = status.HTTP_400_BAD_REQUEST):
        super().__init__(status_code=status_code, detail=detail)


class UnauthorizedException(BusinessException):
    def __init__(self, detail: str = "未认证或认证已过期"):
        super().__init__(detail=detail, status_code=status.HTTP_401_UNAUTHORIZED)


class NotFoundException(BusinessException):
    def __init__(self, detail: str = "资源不存在"):
        super().__init__(detail=detail, status_code=status.HTTP_404_NOT_FOUND)


class ForbiddenException(BusinessException):
    def __init__(self, detail: str = "无权访问"):
        super().__init__(detail=detail, status_code=status.HTTP_403_FORBIDDEN)
