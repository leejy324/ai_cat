import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.student import Base


# SQLAlchemy 2.0 新式写法（本项目用的）
#   id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)

# SQLAlchemy 旧式写法（你可能会在其他项目看到）
#   id = Column(UUID, primary_key=True, default=uuid.uuid4)

#   两者效果完全一样，新式写法的好处是有类型提示，IDE 能自动补全。



class Session(Base):
    __tablename__ = "sessions"

     # as_uuid=True 让 SQLAlchemy 把它当 UUID 对象而不是字符串处理
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("students.id"), nullable=False)
    emotion_tag: Mapped[str | None] = mapped_column(String(20))
    risk_level: Mapped[str | None] = mapped_column(String(10))
    summary: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    message_count: Mapped[int] = mapped_column(Integer, default=0)
