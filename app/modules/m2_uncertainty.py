from app.modules.state import ConversationState


def calculate_uncertainty_level(
    confidence: float,
    emotion_intensity: str,
    intent: str,
    risk_level: str,
) -> int:
    """
    计算不确定度等级，返回 0, 1, 2：
    - 0: 低不确定 → 自由生成（L0）
    - 1: 中不确定 → 保守模板（L1）
    - 2: 高不确定 → 降级模板（L2）
    """
    score = 0

    # 维度1: 置信度 (0-40分)
    score += int((1 - confidence) * 40)

    # 维度2: 情绪强度 (0-25分)
    score += {"high": 25, "medium": 12, "low": 0}.get(emotion_intensity, 0)

    # 维度3: 意图类型 (0-20分)
    score += {
        "venting": 5, "sharing": 0, "greeting": 0,
        "seeking_advice": 15, "question": 10, "other": 20
    }.get(intent, 20)

    # 维度4: 风险等级 (0-15分)
    score += {"none": 0, "low": 5, "medium": 15}.get(risk_level, 0)

    if score >= 80:
        return 2
    elif score >= 55:
        return 1
    else:
        return 0


async def m2_uncertainty(state: ConversationState) -> ConversationState:
    """M2: 不确定度判断 - 纯规则计算"""
    uncertainty = calculate_uncertainty_level(
        confidence=state.get("confidence", 0.5),
        emotion_intensity=state.get("emotion_intensity", "low"),
        intent=state.get("intent", "other"),
        risk_level=state.get("risk_level", "none"),
    )
    state["uncertainty_level"] = uncertainty
    return state
