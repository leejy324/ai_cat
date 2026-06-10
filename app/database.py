from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

# create_async_engine 返回的对象可以在多个协程之间安全共享，所以它在模块顶层创建（全局单例）
engine = create_async_engine(settings.database_url, echo=False) # echo=False — 不打印 SQL 语句到控制台

async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncSession:
    """FastAPI依赖注入：获取数据库会话"""
    async with async_session_factory() as session:
        try:
            yield session # 把 session 交给路由函数使用
            await session.commit() # 路由函数正常结束后，自动提交
        except Exception: # 关键点：这里except 捕获的不是 yield 本身的异常，而是路由函数中抛出的异常
            await session.rollback() # 若fastAPI的路由函数出错了，回滚所有未提交的数据库操作
            raise
        finally:
            await session.close() # 最终关闭会话



#   yield 是关键——它把一个普通函数变成了生成器，FastAPI 的 Depends 对此有特殊处理：

#   请求进来
#     → Depends(get_db) 调用 get_db()
#       → 创建 session
#       → yield session（暂停，把 session 注入到路由函数）
#       → 路由函数执行（比如 register() 里的 db.add()、db.flush()）
#       → 路由函数返回
#       → 继续执行 yield 后面的代码
#         → 成功？commit()
#         → 报错？rollback()
#       → session.close()