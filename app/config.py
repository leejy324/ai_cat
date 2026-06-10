from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用配置，从环境变量加载"""

    # 数据库（Docker 部署时由 docker-compose.yml 自动注入，本地开发需在 .env 中配置）
    database_url: str = "postgresql+asyncpg://postgres:postgres123@localhost:5432/ai_cat"

    # LLM（豆包大模型，OpenAI兼容模式）—— 必须在 .env 中配置
    openai_api_key: str
    openai_base_url: str = "https://ark.cn-beijing.volces.com/api/v3"
    openai_model: str = "doubao-1.5-pro-32k-250115"

    # JWT —— 必须在 .env 中配置
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_expire_days: int = 7

    # 会话
    session_timeout: int = 1800  # 30分钟无消息自动结束

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
