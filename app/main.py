# main.py 只负责组装，不包含任何业务逻辑。这是 FastAPI 的最佳实践——入口文件保持简洁，具体逻辑分散到各模块中

import logging # Python 标准日志库
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request # FastAPI 核心 + 请求对象
from fastapi.middleware.cors import CORSMiddleware # 跨域中间件
from fastapi.responses import JSONResponse # JSON 响应

from app.api.auth import router as auth_router # 认证路由
from app.api.sessions import router as sessions_router # 会话路由
from app.api.scales import router as scales_router # 量表评估路由
from app.exceptions import BusinessException # 自定义业务异常
from app.services.embedding_service import get_model

logging.basicConfig(level=logging.INFO) # basicConfig 设置全局日志级别为 INFO（只打印 INFO 及以上级别的日志）
logger = logging.getLogger(__name__) 

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时预热 embedding 模型
    get_model()
    yield

app = FastAPI(
    title="小猫咪AI心理陪伴伴侣",
    version="1.0.0",
    # swagger_js_url / swagger_css_url：这是关键。FastAPI 默认从 unpkg.com 加载 Swagger UI 的前端资源
    # 但国内访问很慢甚至打不开。这里换成了 bootcdn.net（国内 CDN），确保 /docs 页面能正常打开
    swagger_js_url="https://cdn.bootcdn.net/ajax/libs/swagger-ui/5.10.5/swagger-ui-bundle.js",
    swagger_css_url="https://cdn.bootcdn.net/ajax/libs/swagger-ui/5.10.5/swagger-ui.css",
    lifespan=lifespan,
)

# CORS（跨域资源共享）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # 允许所有来源
    allow_credentials=True, # 允许携带 Cookie
    allow_methods=["*"], # 允许所有 HTTP 方法
    allow_headers=["*"], # # 允许所有请求头
)


app.include_router(auth_router, prefix="/api/auth", tags=["认证"])

app.include_router(sessions_router, prefix="/api/sessions", tags=["会话"])
app.include_router(scales_router, prefix="/api/scales", tags=["量表评估"])

# 这是一个全局异常处理器。当代码中任何地方抛出 BusinessException 时，不会返回 500 错误，而是返回自定义的状态码和消息
# 比如"学号已存在"这种业务错误，抛出 BusinessException(status_code=409, detail="学号已注册")，用户会收到 409 Conflict 而不是 500 Internal Server Error
@app.exception_handler(BusinessException)
async def business_exception_handler(request: Request, exc: BusinessException):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

# 兜底异常处理
# 这是最后的安全网。所有未被上面捕获的异常都会到这里：
#   - logger.error 把错误详情记录到日志（exc_info=True 会打印完整堆栈）
#   - 返回 503 而不是 500，并且不暴露任何内部错误细节给用户（防止信息泄露）
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"未处理异常: {exc}", exc_info=True)
    return JSONResponse(status_code=503, content={"detail": "服务暂时不可用"})

# 健康检查接口
# 简单的接口，返回服务是否正常运行。通常用于运维监控、负载均衡器探活等场景
@app.get("/health")
async def health_check():
    return {"status": "ok"}
