import asyncio
import logging
import uuid
from collections import Counter

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import BusinessException, ForbiddenException, NotFoundException
from app.models.scale import (
    ASLEC_DIMENSIONS,
    VALID_EMOTIONS,
    EmotionRecord,
    ScaleItem,
    ScaleRecord,
)
from app.modules.llm_client import call_llm
from app.prompts.scale_feedback import SCALE_FEEDBACK_SYSTEM, SCALE_FEEDBACK_USER

logger = logging.getLogger(__name__)


def _get_item_dimension(item_index: int) -> str:
    """根据条目编号返回所属维度"""
    for dimension, items in ASLEC_DIMENSIONS.items():
        if item_index in items:
            return dimension
    raise BusinessException(f"无效的条目编号: {item_index}")


def _calculate_scores(items: list[dict]) -> tuple[float, dict[str, float]]:
    """计算维度分和总分"""
    dimension_scores: dict[str, float] = {d: 0.0 for d in ASLEC_DIMENSIONS}
    total = 0.0

    for item in items:
        if item["occurred"] and item["impact_level"] is not None:
            dim = _get_item_dimension(item["item_index"])
            dimension_scores[dim] += item["impact_level"]
            total += item["impact_level"]

    return total, dimension_scores


def _validate_items(items: list[dict]) -> None:
    """验证条目数据合法性"""
    if len(items) != 27:
        raise BusinessException("量表条目数量必须为 27")

    indices = {item["item_index"] for item in items}
    if len(indices) != 27 or min(indices) != 1 or max(indices) != 27:
        raise BusinessException("条目编号必须为 1-27 且不重复")

    for item in items:
        if item["occurred"] and (item["impact_level"] is None or not 1 <= item["impact_level"] <= 5):
            raise BusinessException(f"条目 {item['item_index']}: 已发生时影响程度必须在 1-5 之间")
        if not item["occurred"] and item["impact_level"] is not None:
            raise BusinessException(f"条目 {item['item_index']}: 未发生时影响程度必须为空")


def _validate_emotions(emotions: list[dict]) -> None:
    """验证情绪数据合法性"""
    types_seen = set()
    for emo in emotions:
        if emo["emotion_type"] not in VALID_EMOTIONS:
            raise BusinessException(f"无效的情绪类型: {emo['emotion_type']}，允许的类型: {', '.join(sorted(VALID_EMOTIONS))}")
        if emo["emotion_type"] in types_seen:
            raise BusinessException(f"情绪类型重复: {emo['emotion_type']}")
        types_seen.add(emo["emotion_type"])


async def submit_scale(db: AsyncSession, student_id: str, body) -> dict:
    """提交量表数据，计分、存储、异步生成 AI 反馈"""
    items = [item.model_dump() for item in body.items]
    emotions = [emo.model_dump() for emo in body.emotions]

    _validate_items(items)
    _validate_emotions(emotions)

    total_score, dimension_scores = _calculate_scores(items)

    # 创建量表记录
    record = ScaleRecord(
        id=uuid.uuid4(),
        student_id=uuid.UUID(student_id),
        total_score=total_score,
        dimension_scores=dimension_scores,
        ai_feedback=None,
    )
    db.add(record)
    await db.flush()

    # 创建条目记录
    for item in items:
        dim = _get_item_dimension(item["item_index"])
        scale_item = ScaleItem(
            id=uuid.uuid4(),
            record_id=record.id,
            item_index=item["item_index"],
            dimension=dim,
            occurred=item["occurred"],
            impact_level=item["impact_level"] if item["occurred"] else None,
        )
        db.add(scale_item)

    # 创建情绪记录
    emotions_summary: dict[str, bool] = {}
    for emo in emotions:
        emotion_record = EmotionRecord(
            id=uuid.uuid4(),
            record_id=record.id,
            emotion_type=emo["emotion_type"],
            present=emo["present"],
        )
        db.add(emotion_record)
        emotions_summary[emo["emotion_type"]] = emo["present"]

    await db.flush()

    # 异步生成 AI 反馈
    asyncio.create_task(
        _generate_feedback(str(record.id), student_id, total_score, dimension_scores, emotions_summary)
    )

    return {
        "record_id": record.id,
        "submitted_at": record.submitted_at,
        "total_score": total_score,
        "dimension_scores": dimension_scores,
        "emotions_summary": emotions_summary,
        "ai_feedback": None,
        "feedback_status": "generating",
    }


async def _generate_feedback(
    record_id: str,
    student_id: str,
    total_score: float,
    dimension_scores: dict[str, float],
    emotions_summary: dict[str, bool],
) -> None:
    """异步生成 AI 反馈（独立数据库会话）"""
    from app.database import async_session_factory
    from app.models.student import Student

    async with async_session_factory() as db:
        try:
            # 获取学生档案
            stmt = select(Student).where(Student.id == uuid.UUID(student_id))
            result = await db.execute(stmt)
            student = result.scalar_one_or_none()
            profile_summary = student.profile_summary if student else "暂无学生档案"

            # 构建维度详情
            dim_detail = "\n".join(f"  {k}: {v}" for k, v in dimension_scores.items())
            emo_detail = ", ".join(
                f"{k}({'是' if v else '否'})" for k, v in emotions_summary.items() if v
            ) or "未报告明显情绪"

            user_prompt = SCALE_FEEDBACK_USER.format(
                profile_summary=profile_summary,
                total_score=total_score,
                dimension_scores_detail=dim_detail,
                emotions_detail=emo_detail,
            )

            feedback = await call_llm(SCALE_FEEDBACK_SYSTEM, user_prompt, temperature=0.7)

            if not feedback:
                feedback = "反馈生成失败，请稍后重试。"

            # 更新反馈
            stmt = select(ScaleRecord).where(ScaleRecord.id == uuid.UUID(record_id))
            result = await db.execute(stmt)
            record = result.scalar_one_or_none()
            if record:
                record.ai_feedback = feedback
                await db.commit()

        except Exception as e:
            logger.error(f"AI反馈生成失败 record_id={record_id}: {e}")
            await db.rollback()


async def get_feedback(db: AsyncSession, record_id: str, student_id: str) -> dict:
    """获取量表 AI 反馈"""
    stmt = select(ScaleRecord).where(ScaleRecord.id == uuid.UUID(record_id))
    result = await db.execute(stmt)
    record = result.scalar_one_or_none()

    if not record:
        raise NotFoundException("量表记录不存在")
    if str(record.student_id) != student_id:
        raise ForbiddenException("无权访问此记录")

    status = "completed" if record.ai_feedback else "generating"
    return {
        "record_id": record.id,
        "feedback_status": status,
        "ai_feedback": record.ai_feedback,
    }


async def get_stats(db: AsyncSession, student_id: str) -> dict:
    """获取学生个人统计"""
    # 查询所有量表记录
    stmt = (
        select(ScaleRecord)
        .where(ScaleRecord.student_id == uuid.UUID(student_id))
        .order_by(ScaleRecord.submitted_at.asc())
    )
    result = await db.execute(stmt)
    records = result.scalars().all()

    if not records:
        return {
            "total_records": 0,
            "records": [],
            "score_trend": [],
            "emotion_frequency": {},
        }

    # 查询所有关联的情绪记录
    record_ids = [r.id for r in records]
    emo_stmt = select(EmotionRecord).where(EmotionRecord.record_id.in_(record_ids))
    emo_result = await db.execute(emo_stmt)
    emotion_records = emo_result.scalars().all()

    # 构建情绪映射: record_id → {emotion_type: present}
    emo_map: dict[uuid.UUID, dict[str, bool]] = {}
    for er in emotion_records:
        emo_map.setdefault(er.record_id, {})[er.emotion_type] = er.present

    # 构建记录列表
    record_items = []
    score_trend = []
    emotion_counter: Counter = Counter()

    for r in records:
        record_items.append({
            "record_id": r.id,
            "submitted_at": r.submitted_at,
            "total_score": r.total_score,
            "dimension_scores": r.dimension_scores,
            "emotions_summary": emo_map.get(r.id, {}),
        })
        score_trend.append(r.total_score)

        # 统计情绪频率（只统计 present=True）
        for emo_type, present in emo_map.get(r.id, {}).items():
            if present:
                emotion_counter[emo_type] += 1

    return {
        "total_records": len(records),
        "records": record_items,
        "score_trend": score_trend,
        "emotion_frequency": dict(emotion_counter),
    }
