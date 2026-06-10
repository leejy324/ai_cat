from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


# --- 请求 ---

class ScaleItemRequest(BaseModel):
    item_index: int = Field(..., ge=1, le=27)
    occurred: bool
    impact_level: int | None = Field(default=None, ge=1, le=5)


class EmotionRequest(BaseModel):
    emotion_type: str = Field(..., min_length=1)
    present: bool


class ScaleSubmitRequest(BaseModel):
    items: list[ScaleItemRequest]
    emotions: list[EmotionRequest]


# --- 响应 ---

class ScaleSubmitResponse(BaseModel):
    record_id: UUID
    submitted_at: datetime
    total_score: float
    dimension_scores: dict[str, float]
    emotions_summary: dict[str, bool]
    ai_feedback: str | None
    feedback_status: str


class ScaleFeedbackResponse(BaseModel):
    record_id: UUID
    feedback_status: str
    ai_feedback: str | None


class ScaleRecordItem(BaseModel):
    record_id: UUID
    submitted_at: datetime
    total_score: float
    dimension_scores: dict[str, float]
    emotions_summary: dict[str, bool]


class ScaleStatsResponse(BaseModel):
    total_records: int
    records: list[ScaleRecordItem]
    score_trend: list[float]
    emotion_frequency: dict[str, int]
