import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory
from app.services.vector_store import add_memory, delete_memory
from app.models.memory import StudentMemory
from app.models.message import Message
from app.models.session import Session
from app.models.student import Student
from app.modules.llm_client import call_llm, call_llm_json
from app.prompts.memory_extract import MEMORY_EXTRACT_SYSTEM, MEMORY_EXTRACT_USER
from app.prompts.memory_merge import MEMORY_MERGE_SYSTEM, MEMORY_MERGE_USER

logger = logging.getLogger(__name__)

MEMORY_LIMIT_PER_STUDENT = 50


async def update_session_record(db: AsyncSession, session_id: str, student_id: str, messages: list[Message]):
    """第一步：更新会话记录 - 生成摘要，更新统计"""
    # 构建对话文本用于摘要生成
    conversation_lines = []
    for msg in messages:
        role_label = "学生" if msg.role == "user" else "团团"
        conversation_lines.append(f"{role_label}：{msg.content}")
    conversation_text = "\n".join(conversation_lines[-20:])  # 取最近20条

    # 调用LLM生成摘要
    summary_prompt = f"请用一句话（不超过30字）概括以下对话的主要内容：\n\n{conversation_text}"
    summary = await call_llm(summary_prompt, "请生成摘要。", temperature=0.3)
    if not summary:
        summary = "（无法生成摘要）"

    # 统计会话主要情绪和最高风险
    emotion_counts: dict[str, int] = {}
    max_risk = "none"
    for msg in messages:
        if msg.role == "user" and msg.emotion_tag:
            emotion_counts[msg.emotion_tag] = emotion_counts.get(msg.emotion_tag, 0) + 1
        if msg.role == "user" and msg.risk_level:
            risk_order = {"high": 3, "medium": 2, "low": 1, "none": 0}
            if risk_order.get(msg.risk_level, 0) > risk_order.get(max_risk, 0):
                max_risk = msg.risk_level

    # 取出现次数最多的情绪
    main_emotion = max(emotion_counts, key=emotion_counts.get) if emotion_counts else None

    # 更新会话记录
    result = await db.execute(select(Session).where(Session.id == uuid.UUID(session_id)))
    session = result.scalar_one_or_none()
    # SQLAlchemy 会自动追踪这些修改（脏检查机制）
    if session:
        session.summary = summary # → 会被追踪为 UPDATE ... SET summary = ?
        session.emotion_tag = main_emotion
        session.risk_level = max_risk
        session.message_count = len(messages)
        
    # flush() 把上面追踪到的修改翻译成 UPDATE SQL 发给数据库执行
    await db.flush()
    return summary


async def update_semantic_memory(db: AsyncSession, student_id: str, pending_extractions: list[str]):
    """第二步：更新语义记忆 - 合并新信息到学生档案"""
    if not pending_extractions:
        return

    # 获取现有档案
    result = await db.execute(select(Student).where(Student.id == uuid.UUID(student_id)))
    student = result.scalar_one_or_none()
    existing_profile = student.profile_summary if student and student.profile_summary else "暂无档案信息"

    new_extractions = "\n".join(f"- {e}" for e in pending_extractions)
    user_prompt = f"{MEMORY_MERGE_SYSTEM}\n\n【现有档案】\n{existing_profile}\n\n【本次会话新提取的信息】\n{new_extractions}"

    updated_profile = await call_llm(user_prompt, MEMORY_MERGE_USER, temperature=0.3)

    if updated_profile and student:
        student.profile_summary = updated_profile
        student.updated_at = datetime.utcnow()
        await db.flush()


async def update_episodic_memory(db: AsyncSession, student_id: str, session_id: str, messages: list[Message]):
    """第三步：更新情景记忆 - 从对话中提取关键记忆片段"""
    conversation_lines = []
    for msg in messages:
        role_label = "学生" if msg.role == "user" else "团团"
        conversation_lines.append(f"{role_label}：{msg.content}")
    conversation_text = "\n".join(conversation_lines)

    system_prompt = MEMORY_EXTRACT_SYSTEM.format(conversation=conversation_text)
    result = await call_llm_json(system_prompt, MEMORY_EXTRACT_USER, temperature=0.3)

    if not result:
        return

    memories = result.get("memories", [])
    if not memories:
        return

    added_memories: list[StudentMemory] = []

    for mem_data in memories:
        content = mem_data.get("content", "").strip()
        if not content:
            continue

        topic_tags = mem_data.get("topic_tags", [])
        importance = mem_data.get("importance", "medium")

        # 去重检查：简单检查内容相似度（前20字符相同则认为重复）
        existing = await db.execute(
            select(StudentMemory).where(
                StudentMemory.student_id == uuid.UUID(student_id),
                StudentMemory.content.ilike(f"{content[:20]}%"),
            )
        )
        if existing.scalar_one_or_none():
            continue

        new_memory = StudentMemory(
            student_id=uuid.UUID(student_id),
            content=content,
            topic_tags=",".join(topic_tags) if topic_tags else None,
            importance=importance,
            source_session_id=uuid.UUID(session_id),
        )
        db.add(new_memory)
        added_memories.append(new_memory)

    await db.flush()

    # 将新记忆同步写入 Chroma 向量库
    # 注意：flush() 后 db.new 会被清空，所以必须在 flush 前用 added_memories 记录
    for mem in added_memories:
        created_at_str = mem.created_at.strftime("%Y-%m-%d") if mem.created_at else "unknown"
        try:
            add_memory(
                memory_id=str(mem.id),
                content=mem.content,
                student_id=student_id,
                created_at=created_at_str,
                importance=mem.importance or "medium",
            )
        except Exception as e:
            logger.warning(f"Chroma 写入失败（不影响主流程）: {e}")

    # 淘汰策略：超过50条时按重要性+时间衰减淘汰
    count_result = await db.execute(
        select(func.count()).where(StudentMemory.student_id == uuid.UUID(student_id))
    )
    total_count = count_result.scalar() or 0

    if total_count > MEMORY_LIMIT_PER_STUDENT:
        # 删除重要性为low的最旧记忆（high不淘汰）
        excess = total_count - MEMORY_LIMIT_PER_STUDENT
        low_memories = await db.execute(
            select(StudentMemory)
            .where(
                StudentMemory.student_id == uuid.UUID(student_id),
                StudentMemory.importance == "low",
            )
            .order_by(StudentMemory.created_at.asc())
            .limit(excess)
        )
        for mem in low_memories.scalars().all():
            try:
                delete_memory(str(mem.id))
            except Exception as e:
                logger.warning(f"Chroma 删除失败（不影响主流程）: {e}")
            await db.delete(mem)

        # 如果low的还不够，删除medium的最旧的
        count_result = await db.execute(
            select(func.count()).where(StudentMemory.student_id == uuid.UUID(student_id))
        )
        remaining = count_result.scalar() or 0
        if remaining > MEMORY_LIMIT_PER_STUDENT:
            excess = remaining - MEMORY_LIMIT_PER_STUDENT
            medium_memories = await db.execute(
                select(StudentMemory)
                .where(
                    StudentMemory.student_id == uuid.UUID(student_id),
                    StudentMemory.importance == "medium",
                )
                .order_by(StudentMemory.created_at.asc())
                .limit(excess)
            )
            for mem in medium_memories.scalars().all():
                try:
                    delete_memory(str(mem.id))
                except Exception as e:
                    logger.warning(f"Chroma 删除失败（不影响主流程）: {e}")
                await db.delete(mem)

        await db.flush()


async def m6_memory_update(session_id: str, student_id: str, pending_extractions: list[str]):
    """M6: 记忆更新（独立async函数，由会话结束时异步触发）

    三步线性流程：
    1. 更新会话记录（摘要、情绪、风险）
    2. 更新语义记忆（合并新信息到学生档案）
    3. 更新情景记忆（提取关键记忆片段）
    """
    try:
        async with async_session_factory() as db:
            try:
                # 查询会话所有消息
                result = await db.execute(
                    select(Message)
                    .where(Message.session_id == uuid.UUID(session_id))
                    .order_by(Message.created_at.asc())
                )
                messages = list(result.scalars().all())

                if not messages:
                    return

                # 第一步：更新会话记录
                await update_session_record(db, session_id, student_id, messages)

                # 第二步：更新语义记忆
                await update_semantic_memory(db, student_id, pending_extractions)

                # 第三步：更新情景记忆
                await update_episodic_memory(db, student_id, session_id, messages)

                await db.commit()
                logger.info(f"M6 记忆更新完成：session={session_id}")

            except Exception:
                await db.rollback()
                raise

    except Exception as e:
        logger.error(f"M6 记忆更新失败：session={session_id}, error={e}", exc_info=True)
