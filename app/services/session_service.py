import asyncio
import random
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import BusinessException, ForbiddenException, NotFoundException
from app.models.memory import StudentMemory
from app.models.message import Message
from app.models.session import Session
from app.modules.graph import conversation_graph
from app.modules.m6_memory_update import m6_memory_update
from app.modules.state import ConversationState
from app.schemas.session import (
    MessageHistoryResponse,
    MessageHistoryItem,
    MessageSendResponse,
    MessageMetadata,
    SessionCreateResponse,
    SessionDeleteResponse,
    SessionEndResponse,
    SessionListResponse,
    SessionListItem,
)
from app.services.vector_store import delete_memory as delete_chroma_memory
from app.services.working_memory import (
    add_to_working_memory,
    clear_working_memory,
    get_working_memory,
)

# 降级模板（AI管道不可用时使用）
_FALLBACK_TEMPLATES = [
    "喵~团团有点没听明白。你能再多说一点点吗？",
    "喵呜…团团有点迷糊了，可以再说一次吗？",
    "嗯…团团能感觉到你好像有点心事。如果你愿意说，团团会认真听的。",
    "喵，你现在的感受很重要。想说什么都可以，团团在这儿呢。",
]


# 暂存提取信息：key=session_id, value=list[str]
# 这是一个内存字典，用于暂存 M4（信息提取）模块提取到的个人关键信息
# session_A 发了 3 条消息 → M4 每次提取到一些信息 → 暂存在这里
# session_A 结束 → 一次性取出所有暂存信息 → 交给 M6 做记忆更新
# 为什么不在每条消息时就写入数据库？因为一次对话中提取到的信息可能需要合并去重后再存，所以先攒着，会话结束时统一处理
_pending_extractions_store: dict[str, list[str]] = {}

# 读取（不删除）
def _get_pending_extractions(session_id: str) -> list[str]:
    return _pending_extractions_store.get(session_id, [])

# 写入/更新
def _update_pending_extractions(session_id: str, extractions: list[str]):
    _pending_extractions_store[session_id] = extractions

# 取并删除（pop）
def _get_and_clear_pending_extractions(session_id: str) -> list[str]:
    # dict.pop(key, default = None)，取出并删除指定 key
    # key 不存在时返回的默认值（不传则抛 KeyError）
    # store = {"apple": 3, "banana": 5}
    # count = store.pop("apple", 0)
    # count = 3，store 变成 {"banana": 5}
    return _pending_extractions_store.pop(session_id, [])

# 鉴权辅助函数
async def _verify_session_ownership(db: AsyncSession, session_id: str, student_id: str) -> Session:
    """验证会话归属权"""
    result = await db.execute(select(Session).where(Session.id == uuid.UUID(session_id)))
    session = result.scalar_one_or_none()
    if not session:
        raise NotFoundException("会话不存在")
    if str(session.student_id) != student_id:
        raise ForbiddenException("无权访问此会话")
    return session


async def create_or_get_session(db: AsyncSession, student_id: str) -> SessionCreateResponse:
    """创建或获取进行中的会话"""
    # 第一步：查找该学生是否有未结束的活跃会话
    result = await db.execute(
        select(Session).where(
            Session.student_id == uuid.UUID(student_id),
            Session.ended_at.is_(None), # ← 没有结束时间 = 还在进行中
        ).order_by(Session.started_at.desc()) # ← 按开始时间倒序
    )
    active_session = result.scalar_one_or_none()

     # 第二步：有就返回，没有就创建
    if active_session:
        return SessionCreateResponse(
            id=active_session.id,
            student_id=active_session.student_id,
            started_at=active_session.started_at,
        ) # 返回已有的

    session = Session(student_id=uuid.UUID(student_id))
    db.add(session)
    await db.flush()

    return SessionCreateResponse(
        id=session.id,
        student_id=session.student_id,
        started_at=session.started_at,
    ) # 返回新创建的

# 发送消息——最核心的函数
async def send_message(db: AsyncSession, session_id: str, student_id: str, content: str) -> MessageSendResponse:
    """发送消息：保存用户消息 → 调用AI管道 → 保存AI回复 → 返回"""
    session = await _verify_session_ownership(db, session_id, student_id)
    if session.ended_at:
        raise BusinessException("该会话已结束")

    # 保存用户消息
    user_message = Message(
        session_id=uuid.UUID(session_id),
        role="user",
        content=content,
    )

    db.add(user_message)
    await db.flush()

    # 更新工作记忆
    # 把消息加到内存缓存中，供后续 M3（记忆检索）模块使用
    add_to_working_memory(session_id, "user", content)

    # 调用LangGraph AI管道
    state = ConversationState(
        student_id=student_id,
        session_id=session_id,
        user_message=content,
        pending_extractions=_get_pending_extractions(session_id),
    )

    # .ainvoke()是.invoke()的异步版本 
    result_state = await conversation_graph.ainvoke(state) # 启动 LangGraph 管道，经过 M1→M2→M3→M4→M5

    # 如果管道没有返回 response（出错了），就用降级模板
    response_content = result_state.get("response", random.choice(_FALLBACK_TEMPLATES))

    # 更新用户消息的分析元数据
    user_message.intent = result_state.get("intent")
    user_message.emotion_tag = result_state.get("emotion_tag")
    user_message.emotion_intensity = result_state.get("emotion_intensity")
    user_message.risk_level = result_state.get("risk_level")
    user_message.uncertainty_level = result_state.get("uncertainty_level")

    # 构造返回给前端的元数据。注意每个字段都有默认值——即使管道部分失败，也能返回有效数据
    metadata = MessageMetadata(
        risk_level=result_state.get("risk_level", "none"),
        intent=result_state.get("intent", "other"),
        emotion_tag=result_state.get("emotion_tag", "neutral"),
        uncertainty_level=result_state.get("uncertainty_level", 2),
    )

    # 更新暂存的提取信息
    _update_pending_extractions(session_id, result_state.get("pending_extractions", []))

    # 保存AI回复
    assistant_message = Message(
        session_id=uuid.UUID(session_id),
        role="assistant",
        content=response_content,
        risk_level=metadata.risk_level,
    )
    db.add(assistant_message)
    await db.flush()

    # 更新工作记忆
    add_to_working_memory(session_id, "assistant", response_content)

    # 更新会话消息计数
    # 消息计数 +2（一条用户消息 + 一条 AI 回复）
    session.message_count = (session.message_count or 0) + 2

    return MessageSendResponse(
        id=assistant_message.id,
        role=assistant_message.role,
        content=assistant_message.content,
        metadata=metadata,
    )


async def get_session_list(db: AsyncSession, student_id: str) -> SessionListResponse:
    """获取学生会话列表"""
    result = await db.execute(
        select(Session)
        .where(Session.student_id == uuid.UUID(student_id))
        .order_by(Session.started_at.desc())
    )
    # sessions 的值大概是这样：[Session(id=3, started_at=2026-04-07), Session(id=2, started_at=2026-04-05), Session(id=1, started_at=2026-04-01)]
    sessions = result.scalars().all()

    # 遍历每个 Session 对象，转成 SessionListItem（前端需要的格式），再包装进 SessionListResponse
    return SessionListResponse(
        sessions=[
            SessionListItem(
                id=s.id,
                summary=s.summary,
                emotion_tag=s.emotion_tag,
                risk_level=s.risk_level,
                started_at=s.started_at,
                ended_at=s.ended_at,
                message_count=s.message_count or 0,
            )
            for s in sessions
        ]
    )


async def get_messages(db: AsyncSession, session_id: str, student_id: str) -> MessageHistoryResponse:
    """获取会话消息历史"""
    await _verify_session_ownership(db, session_id, student_id)

    result = await db.execute(
        select(Message)
        .where(Message.session_id == uuid.UUID(session_id))
        .order_by(Message.created_at.asc())
    )
    messages = result.scalars().all()
    return MessageHistoryResponse(
        messages=[
            MessageHistoryItem(id=m.id, role=m.role, content=m.content, created_at=m.created_at)
            for m in messages
        ]
    )


async def end_session(db: AsyncSession, session_id: str, student_id: str) -> SessionEndResponse:
    """结束会话"""
    session = await _verify_session_ownership(db, session_id, student_id)
    if session.ended_at:
        raise BusinessException("该会话已结束")

    session.ended_at = datetime.now(timezone.utc)
    await db.flush()

    # 获取并清除暂存提取信息
    # 会话结束时，取出该会话暂存的所有提取信息，同时删除这个 key
    pending = _get_and_clear_pending_extractions(session_id)

    # 清除工作记忆
    clear_working_memory(session_id)

    # 异步触发M6记忆更新
    asyncio.create_task(m6_memory_update(session_id, student_id, pending))

    return SessionEndResponse(
        id=session.id,
        summary=session.summary,
        emotion_tag=session.emotion_tag,
        ended_at=session.ended_at,
    )


async def delete_session(db: AsyncSession, session_id: str, student_id: str) -> SessionDeleteResponse:
    """删除会话及其所有关联数据（messages、memories、Chroma 向量、工作记忆、暂存提取信息）"""
    session = await _verify_session_ownership(db, session_id, student_id)

    # 1. 查询并删除关联的 StudentMemory，同步删除 Chroma 向量
    memory_result = await db.execute(
        select(StudentMemory).where(StudentMemory.source_session_id == uuid.UUID(session_id))
    )
    memories = memory_result.scalars().all()
    for memory in memories:
        delete_chroma_memory(str(memory.id))
        await db.delete(memory)

    # 2. 查询并删除关联的 Message
    message_result = await db.execute(
        select(Message).where(Message.session_id == uuid.UUID(session_id))
    )
    messages = message_result.scalars().all()
    for message in messages:
        await db.delete(message)

    # 3. 清除工作记忆
    clear_working_memory(session_id)

    # 4. 清除暂存提取信息
    _get_and_clear_pending_extractions(session_id)

    # 5. 删除 session 本身
    await db.delete(session)
    await db.flush()

    return SessionDeleteResponse(id=session.id)
