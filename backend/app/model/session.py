"""
ORM 数据模型：sessions 表。

NOTE: 使用 JSONB 类型存储 conversation_history / attachments / agent_outputs 等半结构化字段，
      既保留 JSON 灵活性，又支持 PostgreSQL 索引查询。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class Session(Base):
    """
    品牌咨询会话主表。

    生命周期：pending → running → completed / error
    agent_outputs / agent_statuses 在流式执行时实时写入，完成后不再变化。
    """
    __tablename__ = "sessions"

    # 主键：与前端生成的 UUID 保持一致，直接使用字符串存储
    id: Mapped[str] = mapped_column(Text, primary_key=True)

    # 用户标识（JWT 解码后的 user_id）
    user_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)

    # 用户本轮输入
    user_prompt: Mapped[str] = mapped_column(Text, nullable=False)

    # 多轮对话历史：[{"user_prompt": "...", "agent_outputs": {"market": "..."}}]
    conversation_history: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, default=list
    )

    # 附件 URL 列表：["https://oss.../xxx.pdf"]
    attachments: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list
    )

    # 会话状态：pending | running | completed | error
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")

    # Orchestrator 决定的 Agent 执行顺序
    selected_agents: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list
    )

    # 各 Agent 完整文本输出：{"market": "...", "strategy": "..."}
    agent_outputs: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )

    # 各 Agent 执行状态：{"market": "completed", "strategy": "running"}
    agent_statuses: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )

    # 顾问最终汇总报告（session_complete 事件产出）
    report: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # 时间戳：自动管理，无需应用层手动设置
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),  # 数据库端生成，避免时区问题
    )
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
