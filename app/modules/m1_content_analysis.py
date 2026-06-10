import json
import logging
import random

from app.modules.llm_client import call_llm_json
from app.modules.state import ConversationState
from app.prompts.content_analysis import CONTENT_ANALYSIS_SYSTEM, CONTENT_ANALYSIS_USER
from app.prompts.response_generation import SAFETY_TEMPLATES


logger = logging.getLogger(__name__)

# 高危关键词
HIGH_RISK_KEYWORDS = ["自杀", "不想活了", "跳楼", "割腕"]


def _keyword_fallback_check(message: str) -> str | None:
    """关键词兜底：匹配到高危关键词返回 'high'，否则返回 None"""
    for keyword in HIGH_RISK_KEYWORDS:
        if keyword in message:
            return "high"
    return None


# M1 LLM调用失败时的降级结果
_M1_FALLBACK = {
    "risk_level": "none",
    "risk_reason": "",
    "intent": "other",
    "confidence": 0.5,
    "emotion_tag": "neutral",
    "emotion_intensity": "medium",
}


async def m1_content_analysis(state: ConversationState) -> ConversationState:
    """M1: 内容分析 - 关键词兜底 + LLM分析"""
    message = state["user_message"]

    # 1. 关键词兜底（优先执行）
    keyword_risk = _keyword_fallback_check(message)
    if keyword_risk == "high":
        state["risk_level"] = "high"
        state["risk_reason"] = "关键词匹配到高危内容"
        state["intent"] = "venting"
        state["confidence"] = 1.0
        state["emotion_tag"] = "sad"
        state["emotion_intensity"] = "high"
        state["response"] = random.choice(SAFETY_TEMPLATES)

    # 2. LLM分析
    user_prompt = CONTENT_ANALYSIS_USER.format(message=message)
    result = await call_llm_json(CONTENT_ANALYSIS_SYSTEM, user_prompt, temperature=0.3)

    if not result:
        # .warning() 日志级别方法，表示警告
        # 为什么不直接 print？无法控制级别，无法过滤，生产环境不方便管理
        # logger.warning()可以按级别过滤、按模块过滤、输出到文件、统一格式化
        logger.warning("M1 LLM调用失败，使用降级结果")
        result = _M1_FALLBACK

    state["risk_level"] = result.get("risk_level", "none")
    state["risk_reason"] = result.get("risk_reason", "")
    state["intent"] = result.get("intent", "other")
    state["confidence"] = float(result.get("confidence", 0.5))
    state["emotion_tag"] = result.get("emotion_tag", "neutral")
    state["emotion_intensity"] = result.get("emotion_intensity", "low")

    # 高风险时直接设置安全回复
    if state["risk_level"] == "high":
        state["response"] = random.choice(SAFETY_TEMPLATES)

    return state
