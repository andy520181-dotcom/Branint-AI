"""
ORM 数据模型：agent_events 事件日志表（Event Sourcing）。

设计原则：
  - Append-Only：只追加，永不修改或删除
  - 事件序号 seq 在同一 session 内单调递增
  - raw_sse 存储完整的 SSE 事件字符串，用于精确回放
  - 利用 SSE 协议原生 `id:` 字段 + `Last-Event-ID` 请求头实现断点续传

这是解决"刷新丢档"和"服务器重启丢失进度"的数据库级保障。
即使进程崩溃，重启后仍能从此表精确回放到最后一个已落盘事件。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import BigInteger, Integer, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class AgentEvent(Base):
    """
    Agent 事件日志表（append-only）。

    每条 SSE 事件（agent_chunk / routing_decided / agent_output / ...）
    在推送给前端之前先写入此表，保证 Event Sourcing 的原子性。

    seq：同一 session 内的事件序号，从 1 开始单调递增，
         对应 SSE `id:` 字段，前端断线重连时通过 `Last-Event-ID` 请求头携带，
         后端直接 WHERE seq > last_event_id 精确补发漏掉的事件。
    """
    __tablename__ = "agent_events"

    # 全局自增主键（BigSerial）
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    # 所属会话
    session_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)

    # 会话内事件序号（1-based，严格递增）
    seq: Mapped[int] = mapped_column(Integer, nullable=False)

    # 事件类型（便于查询/过滤）
    event_type: Mapped[str] = mapped_column(Text, nullable=False)

    # 产生该事件的 agent（可为空，如 routing_decided 无特定 agent）
    agent_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # 完整的 SSE 原始字符串（含 event:/data:/id: 行），用于零损耗回放
    raw_sse: Mapped[str] = mapped_column(Text, nullable=False)

    # 结构化 payload（便于 snapshot 接口直接聚合，无需解析 raw_sse）
    payload: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)

    # 时间戳
    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )
