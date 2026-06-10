import logging
import os
from pathlib import Path

from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

_model = None
_MODEL_NAME = "BAAI/bge-large-zh-v1.5"

# Docker 部署场景：模型已 COPY 到 /app/models/bge-large-zh-v1.5/
# 本地开发场景：models/ 目录不存在，回退到 HF 缓存（需先运行 scripts/download_model.py 或手动下载）
_LOCAL_MODEL_PATH = Path(__file__).resolve().parent.parent.parent / "models" / "bge-large-zh-v1.5"


def get_model() -> SentenceTransformer:
    """获取全局单例 embedding 模型"""
    global _model
    if _model is None:
        # 优先从项目本地目录加载（Docker 部署 + 本地预下载场景）
        if _LOCAL_MODEL_PATH.is_dir():
            logger.info(f"从本地目录加载 embedding 模型: {_LOCAL_MODEL_PATH}")
            _model = SentenceTransformer(str(_LOCAL_MODEL_PATH))
        else:
            # 回退到 HF 缓存：若已缓存过直接加载，否则报错提示先下载
            logger.info(f"从 HF 缓存加载 embedding 模型: {_MODEL_NAME}")
            _model = SentenceTransformer(_MODEL_NAME, local_files_only=True)
        logger.info("embedding 模型加载完成")
    return _model


def encode(text: str) -> list[float]:
    """将文本编码为向量"""
    return get_model().encode(text).tolist()
