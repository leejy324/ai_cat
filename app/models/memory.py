import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.student import Base

# SQLAlchemy 2.0 新式写法（本项目用的）
#   id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)

# SQLAlchemy 旧式写法（你可能会在其他项目看到）
#   id = Column(UUID, primary_key=True, default=uuid.uuid4)

#   两者效果完全一样，新式写法的好处是有类型提示，IDE 能自动补全。

class StudentMemory(Base):
    __tablename__ = "student_memories"

     # as_uuid=True 让 SQLAlchemy 把它当 UUID 对象而不是字符串处理
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("students.id"), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False) # Text 类型可以存很长的文本（PostgreSQL 中无长度限制）
    topic_tags: Mapped[str | None] = mapped_column(String(255))
    importance: Mapped[str] = mapped_column(String(10), default="medium")  # high / medium / low
    source_session_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("sessions.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
