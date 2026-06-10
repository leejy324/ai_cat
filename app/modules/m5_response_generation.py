import logging
import random

from app.modules.llm_client import call_llm
from app.modules.state import ConversationState
from app.prompts.response_generation import (
    CAT_PERSONA,
    CONSERVATIVE_TEMPLATES,
    FALLBACK_TEMPLATES,
    RESPONSE_GENERATION_L0_SYSTEM,
    RESPONSE_GENERATION_L0_USER,
)

logger = logging.getLogger(__name__)


def _get_conservative_response(intent: str) -> str:
    """根据意图选择保守模板"""
    templates = CONSERVATIVE_TEMPLATES.get(intent, CONSERVATIVE_TEMPLATES["default"])
    return random.choice(templates)


def _get_fallback_response() -> str:
    """获取降级模板"""
    return random.choice(FALLBACK_TEMPLATES)


async def m5_response_generation(state: ConversationState) -> ConversationState:
    """M5: 回应生成 - 根据不确定度选择生成策略"""
    uncertainty = state.get("uncertainty_level", 2)

    # 如果M1已设置安全回复（高风险），直接返回
    if state.get("response"):
        return state

    if uncertainty == 0:
        # L0: 自由生成 - LLM结合上下文和猫咪人设
        system_prompt = RESPONSE_GENERATION_L0_SYSTEM.format(
            cat_persona=CAT_PERSONA,
            profile_summary=state.get("context_str", "暂无学生档案"),
            recent_sessions="",
            relevant_memories="",
            working_memory=state.get("context_str", ""),
        )
        user_prompt = RESPONSE_GENERATION_L0_USER.format(message=state["user_message"])
        response = await call_llm(system_prompt, user_prompt, temperature=0.8)

        if not response:
            logger.warning("M5 LLM调用失败，使用降级模板")
            response = _get_fallback_response()

        state["response"] = response

    elif uncertainty == 1:
        # L1: 保守模板
        intent = state.get("intent", "other")
        state["response"] = _get_conservative_response(intent)

    else:
        # L2: 降级模板
        state["response"] = _get_fallback_response()

    return state
