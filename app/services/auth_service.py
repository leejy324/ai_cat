# 这个文件包含认证相关的所有业务逻辑：密码加密、JWT 签发与验证、注册、登录

from datetime import datetime, timedelta, timezone

import bcrypt # bcrypt 是一种专门用于密码加密的算法
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.exceptions import BusinessException, UnauthorizedException
from app.models.student import Student
from app.schemas.auth import AuthResponse

# 验证明文密码是否匹配哈希值
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode(), hashed_password.encode()) # .encode() - bcrypt 只接受 bytes，所以字符串要转字节


def hash_password(password: str) -> str:
    # bcrypt.gensalt() - 自动生成随机盐值（salt），相同密码每次加密结果不同
    # .decode() 存到数据库需要 str，所以结果要转回字符串
    # bcrypt.hashpw(password: bytes, salt: bytes) -> bytes，用 bcrypt 算法对密码进行哈希加密
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode() 


def create_access_token(student_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=settings.jwt_expire_days) # 设置会员卡过期时间
    payload = {"sub": student_id, "exp": expire} # 构造payload，sub 是 JWT 标准字段，表示"主体"（谁是用户）

    # 用密钥签名，防止篡改
    # JWT 是不加密的，任何人都能 base64 解码看到内容。但因为有签名，所以无法伪造——篡改后签名验证会失败
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> str:
    """解码JWT token，返回student_id。失败抛出UnauthorizedException"""
    try:
        # jwt.decode() 会自动验证签名和过期时间
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        student_id: str | None = payload.get("sub")
        if student_id is None:
            raise UnauthorizedException("无效的认证令牌")
        return student_id
    # 如果 token 被篡改或过期 → 抛出 JWTError → 捕获后转为 UnauthorizedException
    except JWTError:
        raise UnauthorizedException("认证令牌已过期或无效")


async def register(db: AsyncSession, student_no: str, password: str,
                   nickname: str | None, grade: str | None,
                   gender: str | None, school: str | None) -> AuthResponse:
    """学生注册：学号唯一性校验 → 密码哈希 → 创建Student → 签发JWT"""
    # 学号唯一性检查
    result = await db.execute(select(Student).where(Student.student_no == student_no))
    if result.scalar_one_or_none(): # scalar_one_or_none() → 最多返回一条记录，没有则返回 None，适合"按唯一键查询"的场景
        raise BusinessException("该学号已注册") # 学号已存在 → 409 错误

    student = Student(
        student_no=student_no,
        password_hash=hash_password(password),
        nickname=nickname,
        grade=grade,
        gender=gender,
        school=school,
    )
    db.add(student) # 对象加入 session（还没发 SQL）
    await db.flush() # 真正执行 INSERT SQL（但事务还没提交）
    # 这里用 flush 而不是 commit，是因为事务由 FastAPI 统一管理——在 get_db() 中统一 commit 或 rollback

    token = create_access_token(str(student.id))
    return AuthResponse(id=student.id, student_no=student.student_no, nickname=student.nickname, token=token)


async def login(db: AsyncSession, student_no: str, password: str) -> AuthResponse:
    """学生登录：查询Student → 验证密码 → 签发JWT"""
    result = await db.execute(select(Student).where(Student.student_no == student_no))
    student = result.scalar_one_or_none()
    if not student or not verify_password(password, student.password_hash):
        raise UnauthorizedException("学号或密码错误")

    token = create_access_token(str(student.id))
    return AuthResponse(id=student.id, student_no=student.student_no, nickname=student.nickname, token=token)


async def get_current_student_id(token: str) -> str:
    """从JWT token中提取student_id，供FastAPI依赖使用"""
    return decode_access_token(token)
