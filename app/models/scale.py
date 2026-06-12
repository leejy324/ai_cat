import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.student import Base


# ASLEC 维度 → 条目映射（1-indexed）
# 基于 刘贤臣(1987) 原始因子结构，交叉负荷条目归入主因子，未归入条目按内容归类：
#   - 条目10(与老师关系紧张) 原因子负荷<0.35，按内容归入人际关系
#   - 条目26(意外惊吓事故) 原因子负荷<0.35，按内容归入健康与适应
#   - 条目18 跨学习压力/受惩罚，归入学习压力
#   - 条目23,24 跨受惩罚/其他，归入受惩罚
ASLEC_DIMENSIONS = {
    "人际关系": [1, 2, 4, 10, 15, 25],
    "学习压力": [3, 9, 16, 18, 22],
    "受惩罚": [17, 19, 20, 21, 23, 24],
    "丧失": [12, 13, 14],
    "健康与适应": [5, 8, 11, 26, 27],
    "其他": [6, 7],
}

# 允许的情绪类型
VALID_EMOTIONS = {"焦虑", "抑郁", "愤怒", "愉快", "悲伤", "恐惧", "厌恶", "惊讶"}


class ScaleRecord(Base):
    __tablename__ = "scale_records"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("students.id"), nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    total_score: Mapped[float] = mapped_column(Float, nullable=False)
    dimension_scores: Mapped[dict] = mapped_column(JSONB, nullable=False)
    ai_feedback: Mapped[str | None] = mapped_column(Text)


class ScaleItem(Base):
    __tablename__ = "scale_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    record_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("scale_records.id", ondelete="CASCADE"), nullable=False)
    item_index: Mapped[int] = mapped_column(Integer, nullable=False)
    dimension: Mapped[str] = mapped_column(String(20), nullable=False)
    occurred: Mapped[bool] = mapped_column(Boolean, nullable=False)
    impact_level: Mapped[int | None] = mapped_column(Integer)


class EmotionRecord(Base):
    __tablename__ = "emotion_records"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    record_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("scale_records.id", ondelete="CASCADE"), nullable=False)
    emotion_type: Mapped[str] = mapped_column(String(20), nullable=False)
    present: Mapped[bool] = mapped_column(Boolean, nullable=False)
