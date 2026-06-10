# CLAUDE.md
## 项目概述

"小猫咪AI心理陪伴伴侣"（团团）——面向青少年的 AI 心理陪伴系统。后端基于 FastAPI + LangGraph + PostgreSQL + ChromaDB。

**部署后端服务请移步查看Readme.md**

两个独立子系统：
1. **AI 对话陪伴**——基于 LangGraph 管道的心理咨询对话
2. **量表评估**——ASLEC（青少年生活事件量表）心理测评数据采集与计分


## 常用命令

```bash
# 启动开发服务器
uvicorn app.main:app --reload --port 8000

# 数据库迁移（必须用 python -m，裸 alembic 命令会因模块解析失败）
python -m alembic upgrade head
python -m alembic revision --autogenerate -m "描述"

```
docker pull ccr.ccs.tencentyun.com/library/python:3.11-slim
## 架构

```
app/api/        → 薄路由层（FastAPI Router + Depends 注入认证/数据库）
app/services/   → 业务逻辑层（编排模型、LLM 调用、向量存储）
app/modules/    → LangGraph AI 管道节点（M1–M6）
app/prompts/    → LLM 提示词模板（system + user 消息字符串）
app/schemas/    → Pydantic v2 请求/响应模型
app/models/     → SQLAlchemy 2.0 ORM 模型（mapped_column, Mapped[]）
app/config.py   → 通过 pydantic-settings 从 .env 加载配置
app/database.py → 异步引擎 + 会话工厂 + get_db() 依赖注入
```

所有数据库操作均为**异步**（asyncpg 驱动）。`get_db()` 是 FastAPI 依赖项，成功时自动提交，异常时自动回滚。

## LangGraph 管道（对话陪伴）

AI 对话流是一个 LangGraph 状态图（`app/modules/graph.py`）：

**状态**：`ConversationState`（TypedDict，定义在 `app/modules/state.py`）

**流程**：
```
用户消息 → M1（内容分析 + 风险检测）
  ├─ 高风险 → 安全响应 → 结束
  └─ 低/中风险 → M2（不确定性评估 0/1/2）
       ├─ L0: M3（记忆检索）→ M4（信息提取）→ M5（回复生成）
       ├─ L1: M3 → M5（跳过提取）
       └─ L2: M5（跳过检索和提取）
  → M6（会话结束时异步更新记忆）
```

**LLM 客户端**：`app/modules/llm_client.py`——OpenAI 兼容 API（豆包大模型）。两个方法：`call_llm()` 返回文本，`call_llm_json()` 返回结构化 JSON。

## 量表评估（ASLEC）

独立于对话系统。ASLEC 27 条目生活事件问卷，6 个维度。

- 维度映射见 `app/models/scale.py:ASLEC_DIMENSIONS`——基于刘贤臣(1987) 因子结构，交叉负荷/未归属条目按注释说明处理
- 计分：影响程度（1-5）按维度累加及求总分（仅对已发生事件计分）
- AI 反馈通过 `asyncio.create_task()` 异步生成，使用独立的数据库会话
- 情绪：8 种基本情绪（焦虑/抑郁/愤怒/愉快/悲伤/恐惧/厌恶/惊讶），每条记录独立是/否选择

## 关键模式

- **认证**：JWT 令牌，`auth_required` 依赖项返回 `student_id: str`
- **异步任务**：后台任务（AI 反馈、记忆更新）使用 `asyncio.create_task()`，通过 `async_session_factory()` 创建独立数据库会话
- **向量存储**：ChromaDB（`app/services/vector_store.py`）用于语义记忆检索，嵌入模型使用 sentence-transformers
- **异常处理**：`BusinessException`（自定义状态码）、`ForbiddenException`（403）、`NotFoundException`（404）
- **代码注释**：代码库使用大量中文行内注释（教学项目），注释解释"为什么"而非"是什么"
