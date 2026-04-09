"""
Session Repository：封装所有会话的数据库读写操作。

NOTE: API 层不得直接操作数据库，所有持久化逻辑必须经由此 Repository 进行。
      每个方法接受 AsyncSession 参数，由调用方（API 层）通过依赖注入提供，
      便于单元测试时替换为 mock session。
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.model.session import Session as SessionModel

logger = logging.getLogger(__name__)


async def create_session(
    db: AsyncSession,
    *,
    session_id: str,
    user_id: str,
    title: str,
    user_prompt: str,
    conversation_history: list[Any],
    attachments: list[str],
    strategy_clarification_answers: str | None = None,
    strategy_clarify_round: int = 0,
) -> SessionModel:
    """
    创建新会话记录，初始状态为 pending。
    """
    record = SessionModel(
        id=session_id,
        user_id=user_id,
        title=title,
        is_pinned=False,
        user_prompt=user_prompt,
        conversation_history=conversation_history,
        attachments=attachments,
        strategy_clarification_answers=strategy_clarification_answers,
        strategy_clarify_round=strategy_clarify_round,
        status="pending",
        selected_agents=[],
        agent_outputs={},
        agent_statuses={},
        report=None,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    logger.info("会话已创建: %s, 用户: %s", session_id, user_id)
    return record


async def get_session(db: AsyncSession, session_id: str) -> Optional[SessionModel]:
    """
    按 ID 查询会话，不存在时返回 None。
    """
    result = await db.execute(select(SessionModel).where(SessionModel.id == session_id))
    return result.scalar_one_or_none()


async def get_user_sessions(db: AsyncSession, user_id: str) -> list[SessionModel]:
    """
    获取用户的全部会话列表，用于侧边栏渲染。
    云端排序逻辑：优先置顶项，其它按更新时间倒序。
    """
    stmt = (
        select(SessionModel)
        .where(SessionModel.user_id == user_id)
        .order_by(SessionModel.is_pinned.desc(), SessionModel.updated_at.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def update_session_meta(
    db: AsyncSession,
    session_id: str,
    title: str | None = None,
    is_pinned: bool | None = None,
) -> None:
    """
    更新前端操作的元数据（重命名、置顶）。
    """
    updates: dict[str, Any] = {}
    if title is not None:
        updates["title"] = title
    if is_pinned is not None:
        updates["is_pinned"] = is_pinned
        
    if not updates:
        return

    await db.execute(
        update(SessionModel)
        .where(SessionModel.id == session_id)
        .values(**updates)
    )
    await db.commit()


async def delete_session(db: AsyncSession, session_id: str) -> None:
    """
    物理删除会话记录。
    """
    await db.execute(
        delete(SessionModel)
        .where(SessionModel.id == session_id)
    )
    await db.commit()


async def continue_session(
    db: AsyncSession,
    *,
    session_id: str,
    user_prompt: str,
    conversation_history: list[Any],
    attachments: list[str],
    strategy_clarification_answers: str | None = None,
    strategy_clarify_round: int = 0,
) -> None:
    """
    继续现有会话。

    NOTE: 多轮对话或战略追问回复时调用。
    更新 user_prompt、conversation_history 等。
    如果是战略追问回复，保留之前的 market / consultant_plan 的断点以复用；
    否则清空所有以便全新流式生成。
    """
    result = await db.execute(select(SessionModel).where(SessionModel.id == session_id))
    record = result.scalar_one_or_none()
    if not record:
        return

    if strategy_clarification_answers:
        # 是战略追问回调：清除当前策略及后续 Agent 的旧数据，保留之前完成的成果（如 market）
        new_outputs = dict(record.agent_outputs or {})
        new_statuses = dict(record.agent_statuses or {})
        for a in ["strategy", "content", "visual", "consultant_review"]:
            new_outputs.pop(a, None)
            new_statuses.pop(a, None)
        selected_agents = list(record.selected_agents or [])
        report = record.report
    else:
        # 新的多轮聊天：彻底清空，重新跑全流程
        new_outputs = {}
        new_statuses = {}
        selected_agents = []
        report = None

    await db.execute(
        update(SessionModel)
        .where(SessionModel.id == session_id)
        .values(
            user_prompt=user_prompt,
            conversation_history=conversation_history,
            attachments=attachments,
            strategy_clarification_answers=strategy_clarification_answers,
            strategy_clarify_round=strategy_clarify_round,
            status="pending",
            agent_outputs=new_outputs,
            agent_statuses=new_statuses,
            selected_agents=selected_agents,
            report=report,
        )
    )
    await db.commit()
    logger.info("会话已续写（复用 session_id）: %s", session_id)




async def update_session_status(
    db: AsyncSession,
    session_id: str,
    status: str,
) -> None:
    """
    更新会话整体状态（running / completed / error）。
    """
    await db.execute(
        update(SessionModel)
        .where(SessionModel.id == session_id)
        .values(status=status)
    )
    await db.commit()


async def update_selected_agents(
    db: AsyncSession,
    session_id: str,
    agents: list[str],
) -> None:
    """
    保存 Orchestrator 决定的 Agent 执行顺序（routing_decided 事件触发）。
    """
    await db.execute(
        update(SessionModel)
        .where(SessionModel.id == session_id)
        .values(selected_agents=agents)
    )
    await db.commit()


async def update_agent_output(
    db: AsyncSession,
    session_id: str,
    agent_id: str,
    output: str,
    status: str = "completed",
) -> None:
    """
    更新单个 Agent 的输出与状态。

    NOTE: 使用 PostgreSQL JSONB 的 concat 操作（|| 运算符）做字段级 upsert，
          避免每次更新需要先 SELECT 再 UPDATE 整个 JSON 对象。
          这里使用 SQLAlchemy 的 Python 端 merge 方式以保持 ORM 兼容性。
    """
    result = await db.execute(select(SessionModel).where(SessionModel.id == session_id))
    record = result.scalar_one_or_none()
    if not record:
        logger.warning("update_agent_output: 会话不存在 %s", session_id)
        return

    # NOTE: 直接修改 JSONB 字段的 Python dict 对象后，
    #       SQLAlchemy 可能无法检测到 dict 内部变化（mutable 检测问题）
    #       使用 dict() 拷贝后重新赋值，强制触发 dirty 标记
    new_outputs = dict(record.agent_outputs or {})
    new_outputs[agent_id] = output
    new_statuses = dict(record.agent_statuses or {})
    new_statuses[agent_id] = status

    await db.execute(
        update(SessionModel)
        .where(SessionModel.id == session_id)
        .values(agent_outputs=new_outputs, agent_statuses=new_statuses)
    )
    await db.commit()


async def set_session_report(
    db: AsyncSession,
    session_id: str,
    report: str,
) -> None:
    """
    写入最终汇总报告并将状态标记为 completed。
    """
    await db.execute(
        update(SessionModel)
        .where(SessionModel.id == session_id)
        .values(report=report, status="completed")
    )
    await db.commit()


async def update_agent_media(
    db: AsyncSession,
    session_id: str,
    media_category: str,  # "agentImages" or "agentVideos"
    media_item: dict,     # {"id": "visual", "type": ..., "data_url": ...}
) -> None:
    """
    更新 Session 中的多媒体资产记录 (JSONB)。
    主要用于将 OSS 上传后的网络 URL 或视频 URL 记录下来，供前端复用。
    """
    result = await db.execute(select(SessionModel).where(SessionModel.id == session_id))
    record = result.scalar_one_or_none()
    if not record:
        logger.warning("update_agent_media: 会话不存在 %s", session_id)
        return

    new_media = dict(getattr(record, "agent_media", None) or {})
    cat_list = list(new_media.get(media_category, []))
    cat_list.append(media_item)
    new_media[media_category] = cat_list

    await db.execute(
        update(SessionModel)
        .where(SessionModel.id == session_id)
        .values(agent_media=new_media)
    )
    await db.commit()
    logger.info("会话报告已落库: %s", session_id)
