import json
import logging

from openai import AsyncOpenAI

from app.config import settings

logger = logging.getLogger(__name__)

client = AsyncOpenAI(
    api_key=settings.openai_api_key,
    base_url=settings.openai_base_url,
)


async def call_llm(system_prompt: str, user_message: str, temperature: float = 0.7) -> str:
    """调用LLM，返回文本内容。失败时返回空字符串。"""
    try:
        response = await client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=temperature,
        )
        return response.choices[0].message.content or ""
    except Exception as e:
        logger.error(f"LLM调用失败: {e}")
        return ""


async def call_llm_json(system_prompt: str, user_message: str, temperature: float = 0.3) -> dict:
    """调用LLM并解析JSON输出。失败时返回空字典。"""
    try:
        response = await client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=temperature,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content or "{}"
        return json.loads(content)
    except json.JSONDecodeError as e:
        logger.error(f"LLM JSON解析失败: {e}, content: {content}")
        return {}
    except Exception as e:
        logger.error(f"LLM调用失败: {e}")
        return {}
