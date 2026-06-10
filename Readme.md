# 后端服务部署指南

> **小猫咪AI心理陪伴伴侣** — 后端服务部署与 API 对接文档

---

## 一、项目简介

本后端服务为"小猫咪AI心理陪伴伴侣"提供两个核心功能：

| 子系统 | 说明 |
|--------|------|
| **AI 对话陪伴** | 学生与 AI 心理陪伴角色"团团"进行对话，系统自动检测风险、分析情绪并生成回复 |
| **量表评估** | ASLEC（青少年生活事件量表）27 题问卷的提交、自动计分与 AI 反馈 |

技术栈：FastAPI + LangGraph + PostgreSQL + ChromaDB，全部通过 Docker 容器化部署。

---

## 二、环境准备

### 2.1 安装 Docker Desktop

下载并安装 [Docker Desktop for Windows](https://www.docker.com/products/docker-desktop/)，安装后确保 Docker 正常运行：

```bash
docker --version
```

### 2.2 配置 Docker 镜像加速（国内网络必须）

打开 Docker Desktop → Settings → Docker Engine，将 JSON 配置替换为：

```json
{
  "registry-mirrors": [
    "https://docker.1ms.run",
    "https://docker.m.daocloud.io",
    "https://ccr.ccs.tencentyun.com",
    "https://docker.xuanyuan.me",
    "https://registry-1.docker.io"
  ]
}
```

点击 **Apply & Restart**，等待 Docker 重启完成。

### 2.3 VPN 准备

部署过程中 **仅第 3 步（下载 Embedding 模型）需要 VPN**，其余步骤不需要。请确保在执行模型下载时 VPN 处于开启状态。

---

## 三、部署步骤

> 以下所有命令均在**项目根目录**下执行。

### 第 1 步：配置环境变量

将 `.env.example` 复制为 `.env`：

```bash
cp .env.example .env
```

打开 `.env` 文件，按需填写以下配置：

```bash
# LLM（豆包大模型）—— 需填写 API Key
OPENAI_API_KEY=          # ← 向后端开发人员获取
OPENAI_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
OPENAI_MODEL=doubao-1.5-pro-32k-250115

# JWT 密钥 —— 需填写一个随机字符串
JWT_SECRET_KEY=          # ← 向后端开发人员获取
JWT_ALGORITHM=HS256
JWT_EXPIRE_DAYS=7

# 会话超时（秒）
SESSION_TIMEOUT=1800
```

> 💡 `OPENAI_API_KEY` 和 `JWT_SECRET_KEY` 需要向后端开发人员获取，其余项保持默认即可。
> 💡 `DATABASE_URL` 由 `docker-compose.yml` 自动注入，**不要**在 `.env` 中手动设置。

### 第 2 步：下载 Embedding 模型（需开启 VPN）

Embedding 模型（`BAAI/bge-large-zh-v1.5`，约 1.3GB）需要从 HuggingFace 下载。**无需在本地安装 Python**，全部通过 Docker 完成。

**① 构建基础镜像**（只安装 Python 依赖，不含模型）：

Dockerfile 采用多阶段构建，`--target base` 只构建第一阶段（跳过模型 COPY），用于下载模型：

```bash
docker build --target base -t ai_cat-base .
```

> ⚠️ 如果此步构建失败，请先检查 Docker 镜像加速是否已配置（见 2.2 节）。

**② 运行容器下载模型到本地**（**确保 VPN 已开启**）：

```bash
docker run --rm \
  -v "你的项目绝对路径/models:/app/models" \
  -e HF_ENDPOINT=https://huggingface.co \
  ai_cat-base \
  python -c "from sentence_transformers import SentenceTransformer; m = SentenceTransformer('BAAI/bge-large-zh-v1.5'); m.save('/app/models/bge-large-zh-v1.5'); print('模型下载完成!')"
```

> 📌 请将 `你的项目绝对路径` 替换为实际的**项目根目录绝对路径**，例如 `D:/work/ai_cat`。

下载完成后，验证模型文件：

```bash
ls models/bge-large-zh-v1.5/
# 预期输出：
# 1_Pooling/  2_Normalize/  config.json  model.safetensors  tokenizer.json  ...
```

**③ 关闭 VPN**（后续步骤不再需要）。

---

<details>
<summary><strong>⚠️ 方案 A 失败？点击展开备选方案（使用本地 Python 下载）</strong></summary>

**如果 Docker 下载模型失败（网络超时、卷挂载路径问题等），可以用本地 Python 作为备选**：

**前提**：电脑已安装 Python 3.9+，并开启 VPN。

```bash
python scripts/download_model.py
```

脚本会自动检测并安装所需依赖（`sentence-transformers`，含 PyTorch 等大型库，首次安装较慢），下载完成后模型保存在 `models/bge-large-zh-v1.5/`。

> 💡 如果你更习惯用 Conda / venv 等虚拟环境，在对应环境中运行脚本即可。

</details>

### 第 3 步：启动全部服务

```bash
docker compose up -d --build
```

该命令会自动完成：
1. 构建后端镜像（安装依赖 + 复制模型）
2. 启动 PostgreSQL 数据库
3. 等待数据库就绪后自动运行数据库迁移
4. 启动后端服务

**验证服务是否正常：**

```bash
# 查看容器状态（两个容器应均为 Up）
docker compose ps

# 查看后端日志（末尾应出现 "Uvicorn running on http://0.0.0.0:8000"）
docker compose logs backend --tail 10

# 健康检查（返回 {"status":"ok"} 即成功）
curl http://localhost:8000/health
```

---

## 四、API 文档入口

服务启动后，可通过浏览器访问以下交互式 API 文档：

| 文档类型 | 地址 | 说明 |
|---------|------|------|
| **Swagger UI** | http://localhost:8000/docs | 可直接在页面测试 API（推荐） |
| **ReDoc** | http://localhost:8000/redoc | 阅读型文档，排版更清晰 |
| **健康检查** | http://localhost:8000/health | 快速验证服务是否运行 |

> 💡 Swagger UI 页面右上角有 **Authorize** 按钮，输入 Token 后即可直接测试需要认证的接口。

---

## 五、API 接口一览

### 5.1 认证模块 `/api/auth`

| 方法 | 路径 | 说明 | 认证 |
|------|------|------|:----:|
| `POST` | `/api/auth/register` | 学生注册 | ❌ |
| `POST` | `/api/auth/login` | 学生登录 | ❌ |

#### POST /api/auth/register — 注册

```json
// 请求体
{
  "student_no": "2024001",       // 必填，学号（1-20字符）
  "password": "123456",          // 必填，密码（6-50字符）
  "nickname": "小明",            // 可选，昵称
  "grade": "大一",               // 可选，年级
  "gender": "男",                // 可选，性别
  "school": "XX大学"             // 必填，学校
}

// 响应 201
{
  "id": "uuid",
  "student_no": "2024001",
  "nickname": "小明",
  "token": "eyJhbGciOiJIUzI1NiIs..."   // ← JWT Token，后续请求需要
}
```

#### POST /api/auth/login — 登录

```json
// 请求体
{
  "student_no": "2024001",
  "password": "123456"
}

// 响应 200
{
  "id": "uuid",
  "student_no": "2024001",
  "nickname": "小明",
  "token": "eyJhbGciOiJIUzI1NiIs..."
}
```

---

### 5.2 会话模块 `/api/sessions`

> 以下所有接口均需要 **Authorization 请求头**，格式见第六节。

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/sessions` | 创建 / 获取当前活跃会话 |
| `GET` | `/api/sessions` | 获取用户所有会话列表 |
| `POST` | `/api/sessions/{session_id}/messages` | 发送消息给 AI |
| `GET` | `/api/sessions/{session_id}/messages` | 获取会话消息历史 |
| `POST` | `/api/sessions/{session_id}/end` | 结束会话 |
| `DELETE` | `/api/sessions/{session_id}` | 删除会话 |

#### POST /api/sessions — 创建会话

```json
// 响应 201
{
  "id": "uuid",
  "student_id": "uuid",
  "started_at": "2025-06-10T12:00:00"
}
```

#### POST /api/sessions/{session_id}/messages — 发送消息

```json
// 请求体
{
  "content": "我最近压力很大"       // 必填，消息内容
}

// 响应 201
{
  "id": "uuid",
  "role": "assistant",
  "content": "我能理解你的感受，愿意跟我聊聊吗？",
  "metadata": {
    "risk_level": "low",              // 风险等级：low / medium / high
    "intent": "emotional_expression", // 意图识别
    "emotion_tag": "anxiety",         // 情绪标签
    "uncertainty_level": 0            // 不确定性等级：0 / 1 / 2
  }
}
```

#### GET /api/sessions — 会话列表

```json
// 响应 200
{
  "sessions": [
    {
      "id": "uuid",
      "summary": "讨论了学业压力...",
      "emotion_tag": "anxiety",
      "risk_level": "low",
      "started_at": "2025-06-10T12:00:00",
      "ended_at": "2025-06-10T12:30:00",
      "message_count": 15
    }
  ]
}
```

#### GET /api/sessions/{session_id}/messages — 消息历史

```json
// 响应 200
{
  "messages": [
    {
      "id": "uuid",
      "role": "user",               // "user" 或 "assistant"
      "content": "我最近压力很大",
      "created_at": "2025-06-10T12:01:00"
    },
    {
      "id": "uuid",
      "role": "assistant",
      "content": "我能理解你的感受...",
      "created_at": "2025-06-10T12:01:05"
    }
  ]
}
```

#### POST /api/sessions/{session_id}/end — 结束会话

```json
// 响应 200
{
  "id": "uuid",
  "summary": "本次对话主要讨论了...",
  "emotion_tag": "anxiety",
  "ended_at": "2025-06-10T12:30:00"
}
```

#### DELETE /api/sessions/{session_id} — 删除会话

```json
// 响应 200
{
  "id": "uuid"
}
```

---

### 5.3 量表评估模块 `/api/scales`

> 以下所有接口均需要 **Authorization 请求头**。

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/scales/submit` | 提交量表评估 |
| `GET` | `/api/scales/{record_id}/feedback` | 获取 AI 反馈 |
| `GET` | `/api/scales/stats` | 获取用户量表统计 |

#### POST /api/scales/submit — 提交量表

```json
// 请求体（27 个条目 + 8 种情绪）
{
  "items": [
    { "item_index": 1, "occurred": true, "impact_level": 3 },
    { "item_index": 2, "occurred": false, "impact_level": null },
    ...
  ],
  "emotions": [
    { "emotion_type": "焦虑", "present": true },
    { "emotion_type": "抑郁", "present": false },
    { "emotion_type": "愤怒", "present": false },
    { "emotion_type": "愉快", "present": true },
    { "emotion_type": "悲伤", "present": false },
    { "emotion_type": "恐惧", "present": false },
    { "emotion_type": "厌恶", "present": false },
    { "emotion_type": "惊讶", "present": false }
  ]
}

// 响应 201
{
  "record_id": "uuid",
  "submitted_at": "2025-06-10T12:00:00",
  "total_score": 45.0,
  "dimension_scores": {          // 6 个维度得分
    "人际关系": 15.0,
    "学习压力": 12.0,
    ...
  },
  "emotions_summary": {
    "焦虑": true,
    "抑郁": false,
    ...
  },
  "ai_feedback": null,           // AI 反馈异步生成，初始为 null
  "feedback_status": "pending"   // pending → completed / failed
}
```

#### GET /api/scales/{record_id}/feedback — 获取 AI 反馈

```json
// 响应 200
{
  "record_id": "uuid",
  "feedback_status": "completed",
  "ai_feedback": "根据你的量表结果..."
}
```

> 💡 `ai_feedback` 是异步生成的，提交后稍等几秒再查询。`feedback_status` 可能的值：`pending`（生成中）、`completed`（已完成）、`failed`（生成失败）。

#### GET /api/scales/stats — 量表统计

```json
// 响应 200
{
  "total_records": 3,
  "records": [ ... ],                   // 历史提交记录列表
  "score_trend": [45.0, 38.0, 30.0],   // 总分趋势（按时间排序）
  "emotion_frequency": {                 // 情绪出现次数统计
    "焦虑": 3,
    "愉快": 2,
    ...
  }
}
```

---

## 六、认证机制

### JWT Bearer Token

除注册和登录外，所有接口均需在请求头中携带 Token：

```
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
```

### 完整对接流程

```
1. 调用 POST /api/auth/register 注册 → 获取 token
   或
   调用 POST /api/auth/login 登录 → 获取 token

2. 后续所有请求在 Header 中携带：
   Authorization: Bearer <token>

3. Token 有效期：7 天（过期后需重新登录）
```


### 认证错误

| 状态码 | 含义 | 处理方式 |
|--------|------|---------|
| `401` | Token 无效或过期 | 引导用户重新登录 |
| `409` | 学号已注册（注册接口） | 提示用户直接登录 |

---

## 七、CORS 说明

后端已开启**全量 CORS**，允许任意来源的跨域请求：

```python
allow_origins=["*"]      # 允许所有域名
allow_credentials=True   # 允许携带 Cookie
allow_methods=["*"]      # 允许所有 HTTP 方法
allow_headers=["*"]      # 允许所有请求头
```

**前端无需配置代理**，可直接使用 `http://localhost:8000` 作为 API 基础地址。

---

## 八、常见问题排查

### 端口 8000 被占用

```bash
# 查看占用进程
netstat -ano | findstr :8000

# 方案一：结束占用进程
taskkill /PID <进程ID> /F

# 方案二：修改 docker-compose.yml 中的端口映射
ports:
  - "8001:8000"    # 改为其他端口
```

### 容器启动失败

```bash
# 查看后端日志
docker compose logs backend

# 查看数据库日志
docker compose logs db

# 重建并查看实时日志
docker compose up --build
```

### 构建时报模型目录缺失

```
ERROR: ... COPY models/bge-large-zh-v1.5 ...
```

说明未执行模型下载步骤（第 2 步），请确保 `models/bge-large-zh-v1.5/` 目录存在且包含 `model.safetensors` 文件。

### 数据库连接失败

```bash
# 检查数据库是否健康
docker compose ps

# 重启数据库
docker compose restart db

# 完全重建（⚠️ 会清空数据）
docker compose down -v
docker compose up -d --build
```

### Swagger 页面打不开或加载慢

Swagger UI 资源已配置为国内 CDN（bootcdn.net）。如仍无法加载，可直接使用 ReDoc：http://localhost:8000/redoc

---

## 九、常用运维命令速查

```bash
# 启动服务
docker compose up -d

# 停止服务
docker compose down

# 查看日志
docker compose logs -f backend

# 重建并启动（代码有更新时）
docker compose up -d --build

# 重置所有数据（删除数据库 + 向量存储）
docker compose down -v

# 查看容器状态
docker compose ps
```
