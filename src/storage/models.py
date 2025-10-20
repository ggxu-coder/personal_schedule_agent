from __future__ import annotations

"""SQLAlchemy ORM 模型定义。

包含两类核心实体：
- Event：日程事件
- UserPreference：用户偏好键值对（可含嵌入向量与权重）
"""

import uuid
from typing import Optional, List
from datetime import datetime

from sqlalchemy import DateTime, Float, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from src.storage.database import Base


class Event(Base):
    """日程事件实体。

    覆盖常见日程字段：标题、描述、起止时间、地点、标签、状态与来源等。
    """

    __tablename__ = "events"

    # 事件主键，使用 UUID 字符串以便跨系统去重/合并
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    # 标题（必填）
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    # 描述（可选，长文本）
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # 开始/结束时间（带时区）
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # 地点（可选）
    location: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    # 标签（JSON 数组，便于筛选/搜索）
    tags: Mapped[List[str]] = mapped_column(JSON, default=list)
    # 事件状态（如 confirmed/tentative/cancelled）
    status: Mapped[str] = mapped_column(String(50), default="confirmed")
    # 事件来源（如 user/ics/api 等）
    source: Mapped[str] = mapped_column(String(50), default="user")
    # 创建/更新时间（由数据库填充，保持审计性）
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=True
    )


class UserPreference(Base):
    """用户偏好实体。

    以 (user_id, preference_key) 做唯一约束；
    支持描述、权重与向量表示（embedding），便于偏好检索与排序。
    """

    __tablename__ = "user_preferences"
    __table_args__ = (
        UniqueConstraint("user_id", "preference_key", name="uq_user_preference_key"),
    )

    # 主键 UUID
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    # 用户标识
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    # 偏好键（如 working_hours、meeting_buffer 等）
    preference_key: Mapped[str] = mapped_column(String(128), nullable=False)
    # 可选描述
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # 偏好值（字符串或 JSON 序列化后的文本）
    preference_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # 偏好向量表示，用于相似度检索/排序
    embedding: Mapped[Optional[List[float]]] = mapped_column(JSON, nullable=True)
    # 偏好权重，默认 1.0
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    # 审计字段
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=True
    )


