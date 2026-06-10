from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import auth_required # ← 从 auth.py 导入认证依赖
from app.database import get_db
from app.schemas.session import (
    MessageHistoryResponse,
    MessageSendRequest,
    MessageSendResponse,
    SessionCreateResponse,
    SessionDeleteResponse,
    SessionEndResponse,
    SessionListResponse,
)
from app.services import session_service

router = APIRouter()

@router.post("", response_model=SessionCreateResponse, status_code=201)
async def create_session(
    student_id: str = Depends(auth_required), # Depends(auth_required) → 鉴权，拿到 student_id
    db: AsyncSession = Depends(get_db), # 注入数据库会话
):
    # 如果用户已有活跃会话就返回现有的，没有就创建新的（"创建或获取"的语义）
    return await session_service.create_or_get_session(db, student_id)


# 这个接口是整个系统的触发点——调用 session_service.send_message() 后，会启动 M1→M2→M3→M4→M5 的 AI 管道
@router.post("/{session_id}/messages", response_model=MessageSendResponse)
async def send_message(
    session_id: str,
    body: MessageSendRequest, # ← 请求体（JSON body），如 {"content": "你好"} 
    student_id: str = Depends(auth_required), # ← 认证
    db: AsyncSession = Depends(get_db),
):
    return await session_service.send_message(db, session_id, student_id, body.content)

# 和创建会话一样的路径 /api/sessions，但方法是 GET。返回该用户的所有会话列表
@router.get("", response_model=SessionListResponse)
async def list_sessions(
    student_id: str = Depends(auth_required), # ← 认证
    db: AsyncSession = Depends(get_db),
):
    return await session_service.get_session_list(db, student_id)


@router.get("/{session_id}/messages", response_model=MessageHistoryResponse)
async def get_messages(
    session_id: str,
    student_id: str = Depends(auth_required),
    db: AsyncSession = Depends(get_db),
):
    return await session_service.get_messages(db, session_id, student_id)

# 结束会话会触发 M6 异步记忆更新——AI 会总结这次对话并更新学生的长期记忆
@router.post("/{session_id}/end", response_model=SessionEndResponse)
async def end_session(
    session_id: str,
    student_id: str = Depends(auth_required),
    db: AsyncSession = Depends(get_db),
):
    return await session_service.end_session(db, session_id, student_id)


@router.delete("/{session_id}", response_model=SessionDeleteResponse)
async def delete_session(
    session_id: str,
    student_id: str = Depends(auth_required),
    db: AsyncSession = Depends(get_db),
):
    return await session_service.delete_session(db, session_id, student_id)
