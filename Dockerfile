# ---- 阶段一：基础镜像（安装 Python 依赖，不含模型）----
# 用于模型下载：docker build --target base -t ai_cat-base .
FROM python:3.11-slim AS base

WORKDIR /app

# torch/sentence-transformers 编译依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ---- 阶段二：最终镜像（加入模型 + 应用代码）----
FROM base AS final

# 复制预下载的 embedding 模型（避免构建时联网下载）
COPY models/bge-large-zh-v1.5 /app/models/bge-large-zh-v1.5

# 复制应用代码
COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
