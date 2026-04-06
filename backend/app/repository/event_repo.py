"""
事件日志数据访问层（Event Sourcing Repository）。

所有对 agent_events 表的读写操作集中在此。
核心方法：
  - append()      : 原子追加一条事件，返回其 seq 序号
  - fetch_since() : 从指定 seq 之后查询所有事件（用于 Last-Event-ID 续传）
  - fetch_all()   : 查询 session 所有事件（用于完整重建状态）
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.model.agent_event import AgentEvent

logger = logging.getLogger(__name__)


def _parse_event_type(raw_sse: str) -> str:
    """从 SSE 原始字符串中提取 event 类型名称"""
    for line in raw_sse.split("\n"):
        if line.startswith("event: "):
            return line[7:].strip()
    return "unknown"


def _parse_agent_id(raw_sse: str) -> str | None:
    """从 SSE data 字段中尝试提取 agent_id"""
    for line in raw_sse.split("\n"):
        if line.startswith("data: "):
            data = line[6:].strip()
            # data 可能是 JSON {"id": "xxx"} 或纯文本 agent_id
            try:
                parsed = json.loads(data)
                if isinstance(parsed, dict):
                    return parsed.get("id")
            except Exception:
                # 纯文本（如 agent_start / agent_complete）
                if re.match(r'^[a-zA-Z_]+$', data):
                    return data
    return None


def _parse_payload(raw_sse: str) -> dict[str, Any] | None:
    """从 SSE data 字段提取结构化 payload"""
    for line in raw_sse.split("\n"):
        if line.startswith("data: "):
            data = line[6:].strip()
            try:
                parsed = json.loads(data)
                if isinstance(parsed, (dict, list)):
                    return parsed if isinstance(parsed, dict) else {"value": parsed}
            except Exception:
                return {"raw": data}
    return None


async def append(
    db: AsyncSession,
    session_id: str,
    raw_sse: str,
) -> int:
    """
    追加一条事件到日志，返回该事件的 seq 序号。

    NOTE: seq 通过 SELECT MAX(seq)+1 生成，需要在事务内执行以保证原子性。
          使用 asyncio.wait_for 兜底，防止写库阻塞 SSE 推送。
    """
    # 获取当前 session 的最大 seq（无记录时为 0）
    result = await db.execute(
        select(func.coalesce(func.max(AgentEvent.seq), 0)).where(
            AgentEvent.session_id == session_id
        )
    )
    max_seq: int = result.scalar() or 0
    next_seq = max_seq + 1

    event_type = _parse_event_type(raw_sse)
    agent_id = _parse_agent_id(raw_sse)
    payload = _parse_payload(raw_sse)

    # 过滤心跳（不写库）
    if raw_sse.strip().startswith(": heartbeat"):
        return next_seq - 1  # 心跳不占 seq

    # 过滤高频 agent_chunk（节流：只写每个 agent 每秒一次）
    # NOTE: 此处不过滤，由调用方决定。event_repo 只负责写入，不做业务判断。

    event = AgentEvent(
        session_id=session_id,
        seq=next_seq,
        event_type=event_type,
        agent_id=agent_id,
        raw_sse=raw_sse,
        payload=payload,
    )
    db.add(event)
    await db.flush()  # flush 就可获取 seq，不需要 commit（由调用方决定事务边界）
    return next_seq


async def fetch_since(
    db: AsyncSession,
    session_id: str,
    after_seq: int,
) -> list[AgentEvent]:
    """
    查询 seq > after_seq 的所有事件，按序号升序返回。
    用于 Last-Event-ID 续传：前端携带最后收到的 seq，后端补发漏掉的事件。
    """
    result = await db.execute(
        select(AgentEvent)
        .where(
            AgentEvent.session_id == session_id,
            AgentEvent.seq > after_seq,
        )
        .order_by(AgentEvent.seq.asc())
    )
    return list(result.scalars().all())


async def fetch_all(
    db: AsyncSession,
    session_id: str,
) -> list[AgentEvent]:
    """查询 session 的全部事件，用于完整状态重建"""
    result = await db.execute(
        select(AgentEvent)
        .where(AgentEvent.session_id == session_id)
        .order_by(AgentEvent.seq.asc())
    )
    return list(result.scalars().all())


async def get_latest_seq(
    db: AsyncSession,
    session_id: str,
) -> int:
    """返回当前 session 最大的 seq（0 表示无任何事件）"""
    result = await db.execute(
        select(func.coalesce(func.max(AgentEvent.seq), 0)).where(
            AgentEvent.session_id == session_id
        )
    )
    return result.scalar() or 0
