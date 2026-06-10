from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class SessionCreateResponse(BaseModel):
    """创建/获取会话响应"""
    id: UUID
    student_id: UUID
    started_at: datetime


class MessageSendRequest(BaseModel):
    """发送消息请求"""
    content: str = Field(..., min_length=1, description="消息内容")


# 这是 AI 管道（M1 + M2）分析后的结果。它被嵌套在 MessageSendResponse 中返回给前端
class MessageMetadata(BaseModel):
    """消息元数据（AI分析结果）"""
    risk_level: str
    intent: str
    emotion_tag: str
    uncertainty_level: int


class MessageSendResponse(BaseModel):
    """发送消息响应"""
    id: UUID
    role: str
    content: str
    metadata: MessageMetadata # # ← 嵌套了上面的元数据

#   AI 回复后返回的完整结构：

#   {
#     "id": "...",
#     "role": "assistant",
#     "content": "你好呀，今天感觉怎么样？",
#     "metadata": {
#       "risk_level": "low",
#       "intent": "greeting",
#       "emotion_tag": "neutral",
#       "uncertainty_level": 0
#     }
#   }


class SessionListItem(BaseModel):
    """会话列表项"""
    id: UUID
    summary: str | None
    emotion_tag: str | None
    risk_level: str | None
    started_at: datetime
    ended_at: datetime | None
    message_count: int


class SessionListResponse(BaseModel):
    """会话列表响应"""
    # list[SessionListItem] 是 Python 3.9+ 泛型语法，等价于 List[SessionListItem]。用一个外层 Response 包裹列表是常见做法，方便后续扩展分页等字段
    sessions: list[SessionListItem] # 列表包装


class MessageHistoryItem(BaseModel):
    """消息历史项"""
    id: UUID
    role: str # "user" 或 "assistant"
    content: str
    created_at: datetime


class MessageHistoryResponse(BaseModel):
    """消息历史响应"""
    messages: list[MessageHistoryItem]


class SessionEndResponse(BaseModel):
    """结束会话响应"""
    id: UUID
    summary: str | None
    emotion_tag: str | None
    ended_at: datetime


class SessionDeleteResponse(BaseModel):
    """删除会话响应"""
    id: UUID
