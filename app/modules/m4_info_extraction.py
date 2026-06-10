import logging

from app.modules.llm_client import call_llm_json
from app.modules.state import ConversationState
from app.prompts.info_extraction import INFO_EXTRACTION_SYSTEM, INFO_EXTRACTION_USER

logger = logging.getLogger(__name__)


async def m4_info_extraction(state: ConversationState) -> ConversationState:
    """M4: 信息提取 - 从消息中提取关键个人信息，暂存待M6更新"""
    message = state["user_message"]
    user_prompt = INFO_EXTRACTION_USER.format(message=message)

    result = await call_llm_json(INFO_EXTRACTION_SYSTEM, user_prompt, temperature=0.3)

    extracted_info = ""
    if result:
        extracted_info = result.get("extracted_info", "")

    state["extracted_info"] = extracted_info

    # 累积提取信息
    pending = state.get("pending_extractions", [])
    if extracted_info:
        pending.append(extracted_info)
    state["pending_extractions"] = pending

    return state
