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

class Message(Base):
    __tablename__ = "messages"

     # as_uuid=True 让 SQLAlchemy 把它当 UUID 对象而不是字符串处理
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sessions.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(10), nullable=False)  # user / assistant
    content: Mapped[str] = mapped_column(Text, nullable=False)
    intent: Mapped[str | None] = mapped_column(String(30))
    emotion_tag: Mapped[str | None] = mapped_column(String(20))
    emotion_intensity: Mapped[str | None] = mapped_column(String(10))
    risk_level: Mapped[str | None] = mapped_column(String(10))
    uncertainty_level: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
