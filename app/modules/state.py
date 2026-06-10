from typing import TypedDict


class ConversationState(TypedDict, total=False):
    """LangGraph管道的状态定义"""
    # 输入
    student_id: str
    session_id: str
    user_message: str
    # M1 输出
    risk_level: str
    risk_reason: str
    intent: str
    confidence: float
    emotion_tag: str
    emotion_intensity: str
    # M2 输出
    uncertainty_level: int  # 0/1/2
    # M3 输出
    context_str: str  # 组装好的上下文字符串
    # M4 输出（暂存）
    extracted_info: str
    # M5 输出
    response: str
    # 会话级累积
    pending_extractions: list[str]
