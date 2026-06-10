from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.exceptions import UnauthorizedException
from app.schemas.auth import AuthResponse, LoginRequest, RegisterRequest
from app.services.auth_service import get_current_student_id, login, register


router = APIRouter()
security = HTTPBearer()



async def auth_required(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """认证依赖：验证JWT并返回student_id"""
    return await get_current_student_id(credentials.credentials) # credentials.credentials就是提取出来的 token 字符串（会员卡号/身份证号）

# response_model=AuthResponse，响应数据按 AuthResponse 格式化（自动过滤多余字段）
# 注册成功返回 201 Created（而不是默认的 200）
# body: RegisterRequest 自动解析请求体 JSON 为 RegisterRequest 对象
@router.post("/register", response_model=AuthResponse, status_code=201)
async def register_endpoint(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    return await register(db, body.student_no, body.password, body.nickname, body.grade, body.gender, body.school)


@router.post("/login", response_model=AuthResponse)
async def login_endpoint(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    return await login(db, body.student_no, body.password)
