"""
ORM 数据模型：users 表。

存储认证信息及关联业务字段。
"""

from typing import Optional
from datetime import datetime
from sqlalchemy import Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class User(Base):
    __tablename__ = "users"

    # 主键：生成唯一 UUID
    id: Mapped[str] = mapped_column(Text, primary_key=True)

    # 邮箱，唯一索引
    email: Mapped[str] = mapped_column(Text, unique=True, index=True, nullable=False)

    # 密码哈希值
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)

    # 头像 URL (支持指向阿里云 OSS)
    avatar_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # 创建更新时间
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
