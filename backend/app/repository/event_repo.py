"""
事件日志数据访问层（Event Sourcing Repository）。

所有对 agent_events 表的读写操作集中在此。
核心方法：
  - append_independent() : 原子追加一条事件，使用独立事务，与业务事务完全隔离
  - fetch_since()        : 从指定 seq 之后查询所有事件（用于 Last-Event-ID 续传）
  - fetch_all()          : 查询 session 所有事件（用于完整重建状态）

NOTE: append_independent() 使用独立的 AsyncSessionFactory，与主业务 db session 完全解耦。
      写入失败只记录 warning，不中断 SSE 流，不污染 sessions 表的主事务。
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.model.agent_event import AgentEvent

logger = logging.getLogger(__name__)


def _parse_event_type(raw_sse: str) -> str:
    """从 SSE 原始字符串中提取 event 类型名称"""
    for line in raw_sse.split("\n"):
        if line.startswith("event: "):
            return line[7:].strip()
    return "unknown"


def _parse_agent_id(raw_sse: str) -> Optional[str]:
    """从 SSE data 字段中尝试提取 agent_id"""
    for line in raw_sse.split("\n"):
        if line.startswith("data: "):
            data = line[6:].strip()
            try:
                parsed = json.loads(data)
                if isinstance(parsed, dict):
                    return parsed.get("id")
            except Exception:
                if re.match(r'^\[a-zA-Z_]+$', data):
                    return data
    return None


def _parse_payload(raw_sse: str) -> Optional[Dict[str, Any]]:
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


async def append_independent(
    session_id: str,
    raw_sse: str,
) -> int:
    """
    追加一条事件到日志，使用完全独立的数据库事务。

    NOTE: 与主业务 db session 完全隔离。写入失败只记录 warning，
          不会传染 sessions 表的主事务，确保 SSE 流不被 DB 错误中断。

    Returns:
        seq 序号（从 1 开始），失败时返回 0 表示未写入。
    """
    from app.db.database import AsyncSessionFactory

    # 过滤心跳（不写库）
    if raw_sse.strip().startswith(": heartbeat"):
        return 0

    event_type = _parse_event_type(raw_sse)
    agent_id = _parse_agent_id(raw_sse)
    payload = _parse_payload(raw_sse)

    try:
        async with AsyncSessionFactory() as ev_db:
            result = await ev_db.execute(
                select(func.coalesce(func.max(AgentEvent.seq), 0)).where(
                    AgentEvent.session_id == session_id
                )
            )
            max_seq: int = result.scalar() or 0
            next_seq = max_seq + 1

            event = AgentEvent(
                session_id=session_id,
                seq=next_seq,
                event_type=event_type,
                agent_id=agent_id,
                raw_sse=raw_sse,
                payload=payload,
            )
            ev_db.add(event)
            await ev_db.commit()
            return next_seq
    except Exception as e:
        logger.warning("event_log 写入失败 [%s] %s: %s", session_id, event_type, e)
        return 0


async def fetch_since(
    db: AsyncSession,
    session_id: str,
    after_seq: int,
) -> List[AgentEvent]:
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
) -> List[AgentEvent]:
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


async def delete_events_by_agents(
    db: AsyncSession,
    session_id: str,
    agent_ids: List[str],
) -> None:
    """物理删除属于某些 agent 的所有事件记录（用于战略追问时清除旧的分支记录）"""
    if not agent_ids:
        return
    from sqlalchemy import delete
    await db.execute(
        delete(AgentEvent)
        .where(
            AgentEvent.session_id == session_id,
            AgentEvent.agent_id.in_(agent_ids),
        )
    )
    await db.commit()
