import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory
from app.models.memory import StudentMemory
from app.models.session import Session
from app.models.student import Student
from app.modules.state import ConversationState
from app.services.vector_store import query_memories
from app.services.working_memory import get_working_memory

logger = logging.getLogger(__name__)

# 传入的参数是Session表格，但这里sessions并不是数据库表本身，而是从数据库表中查出来的结果，是一个 Python list
def _format_recent_sessions(sessions: list) -> str:
    """格式化最近会话为上下文字符串"""
    if not sessions:
        return "暂无历史记录"
    lines = []
    for s in sessions:
        # strftime 是 datetime 对象的方法，意思是 "string format time"——把日期转成指定格式的字符串
        date_str = s.started_at.strftime("%m月%d日") if s.started_at else "未知日期"
        emotion = s.emotion_tag or "未知"
        summary = s.summary or "无摘要"
        lines.append(f"- {date_str}：{summary}（情绪：{emotion}）")
    return "\n".join(lines)

# 传入的参数是memory(StudentMemory)表查询出来的返回结果，是一个list
def _format_relevant_memories(memories: list) -> str:
    """格式化相关记忆为上下文字符串"""
    if not memories:
        return "暂无相关记忆"
    lines = []
    for m in memories:
        date_str = m.created_at.strftime("%m月%d日") if m.created_at else "未知日期"
        lines.append(f"- {date_str}：{m.content}")
    return "\n".join(lines)


def _format_working_memory(messages: list[dict]) -> str:
    """格式化工作记忆为对话文本"""
    if not messages:
        return "（当前会话无历史消息）"
    lines = []
    for msg in messages:
        role_label = "学生" if msg["role"] == "user" else "团团"
        lines.append(f"{role_label}：{msg['content']}")
    return "\n".join(lines)


async def m3_memory_retrieval(state: ConversationState) -> ConversationState:
    """M3: 记忆检索 - 从数据库检索语义记忆和情景记忆，组装上下文"""
    student_id = state["student_id"]
    session_id = state["session_id"]
    user_message = state["user_message"]

    # 等价于async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session_factory() as db:
        try:
            # 1. 检索学生档案摘要（语义记忆）
            result = await db.execute(
                select(Student).where(Student.id == uuid.UUID(student_id))
            )
            student = result.scalar_one_or_none()
            profile_summary = student.profile_summary if student else "暂无学生档案"

            # 2. 检索最近3条已结束会话（情景记忆 - 固定注入）
            result = await db.execute(
                select(Session)
                .where(
                    Session.student_id == uuid.UUID(student_id),
                    Session.ended_at.is_not(None),
                )
                .order_by(Session.ended_at.desc())
                .limit(3)
            )
            recent_sessions = result.scalars().all()
            recent_sessions_str = _format_recent_sessions(list(recent_sessions))

            # 3. 检索相关记忆（情景记忆 - 语义相似度匹配）
            try:
                relevant_memories = query_memories(
                    query_text=user_message,
                    student_id=student_id,
                    n_results=3,
                )
                # 用 Chroma 返回的 id 去 PostgreSQL 查完整记录
                relevant_db_memories = []
                if relevant_memories:
                    memory_ids = [uuid.UUID(m["id"]) for m in relevant_memories]
                    result = await db.execute(
                        select(StudentMemory)
                        .where(StudentMemory.id.in_(memory_ids))
                    )
                    relevant_db_memories = list(result.scalars().all())
                relevant_memories_str = _format_relevant_memories(relevant_db_memories)
            except Exception as e:
                logger.warning(f"Chroma 查询失败，跳过相关记忆: {e}")
                relevant_memories_str = "暂无相关记忆"

        except Exception as e:
            logger.error(f"M3 数据库查询失败: {e}")
            profile_summary = "暂无学生档案"
            recent_sessions_str = "暂无历史记录"
            relevant_memories_str = "暂无相关记忆"

    # 4. 获取工作记忆
    working_memory = get_working_memory(session_id)
    working_memory_str = _format_working_memory(working_memory)

    # 组装上下文
    context_parts = [
        f"【学生档案】\n{profile_summary}",
        f"【近期情况】\n{recent_sessions_str}",
        f"【相关记忆】\n{relevant_memories_str}",
        f"【当前对话】\n{working_memory_str}",
    ]
    state["context_str"] = "\n\n".join(context_parts)

    return state
