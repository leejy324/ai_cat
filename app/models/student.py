import uuid
from datetime import datetime

from sqlalchemy import String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# SQLAlchemy 2.0 新式写法（本项目用的）
#   id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)

# SQLAlchemy 旧式写法（你可能会在其他项目看到）
#   id = Column(UUID, primary_key=True, default=uuid.uuid4)

#   两者效果完全一样，新式写法的好处是有类型提示，IDE 能自动补全。

class Base(DeclarativeBase):
    pass


class Student(Base):
    __tablename__ = "students"
    
    # as_uuid=True 让 SQLAlchemy 把它当 UUID 对象而不是字符串处理
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_no: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    nickname: Mapped[str | None] = mapped_column(String(50))
    grade: Mapped[str | None] = mapped_column(String(20))
    gender: Mapped[str | None] = mapped_column(String(10))
    school: Mapped[str | None] = mapped_column(String(100))
    profile_summary: Mapped[str | None] = mapped_column(Text) # Text 类型可以存很长的文本（PostgreSQL 中无长度限制）
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
