from uuid import UUID
from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    """学生注册请求"""
    student_no: str = Field(..., min_length=1, max_length=20, description="学号") # ...表示必填，None表示可选
    password: str = Field(..., min_length=6, max_length=50, description="密码")
    nickname: str | None = Field(None, max_length=50, description="昵称") # str | None的写法等价于 Optional[str]，表示"字符串或空值"
    grade: str | None = Field(None, max_length=20, description="年级")
    gender: str | None = Field(None, max_length=10, description="性别")
    school: str = Field(..., max_length=100, description="学校")


class LoginRequest(BaseModel):
    """学生登录请求"""
    student_no: str = Field(..., description="学号")
    password: str = Field(..., description="密码")


class AuthResponse(BaseModel):
    """认证响应（注册/登录）"""
    id: UUID
    student_no: str
    nickname: str | None
    token: str
