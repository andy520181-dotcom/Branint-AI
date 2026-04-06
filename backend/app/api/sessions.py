"""
Sessions API：提供会话的创建、SSE 流式执行、报告查询与快照恢复接口。

NOTE: 本层只负责请求解析和响应封装；所有持久化操作通过 session_repo 进行，
      不在此层直接操作数据库或 JSON 文件。
"""

from __future__ import annotations

import json as _json
import logging
import time as _time
import uuid
from collections.abc import AsyncGenerator
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.repository import session_repo
from app.schema.session import CreateSessionRequest, CreateSessionResponse
from app.service.agent_orchestrator import AgentOrchestrator

router = APIRouter(prefix="/api/sessions", tags=["sessions"])
logger = logging.getLogger(__name__)

# NOTE: 内存缓存层：减少 SSE 流式执行期间的数据库读取次数。
#       仅在 stream_session 执行期间持有，进程内共享。
#       进程重启后从数据库重新加载 —— 这正是 PostgreSQL 迁移的核心收益。
_session_cache: dict[str, dict] = {}


@router.post("", response_model=CreateSessionResponse)
async def create_session(
    body: CreateSessionRequest,
    db: AsyncSession = Depends(get_db),
) -> CreateSessionResponse:
    """
    创建新的品牌咨询会话，持久化到 PostgreSQL。
    返回 session_id 供前端连接 SSE 流。
    """
    session_id = body.session_id or str(uuid.uuid4())

    await session_repo.create_session(
        db,
        session_id=session_id,
        user_id=body.user_id,
        user_prompt=body.user_prompt,
        conversation_history=[r.model_dump() for r in body.conversation_history],
        attachments=body.attachments,
        strategy_clarification_answers=body.strategy_clarification_answers,
        strategy_clarify_round=body.strategy_clarify_round,
    )

    # NOTE: 同步写入内存缓存，避免 stream_session 立即查库
    _session_cache[session_id] = {
        "user_id": body.user_id,
        "user_prompt": body.user_prompt,
        "conversation_history": [r.model_dump() for r in body.conversation_history],
        "attachments": body.attachments,
        "strategy_clarification_answers": body.strategy_clarification_answers,
        "strategy_clarify_round": body.strategy_clarify_round,
        "status": "pending",
        "report": None,
        "selected_agents": [],
        "agent_outputs": {},
        "agent_statuses": {},
    }

    logger.info(
        "创建新会话: %s, 用户: %s, 历史轮次: %d, 附件: %d",
        session_id, body.user_id, len(body.conversation_history), len(body.attachments),
    )
    return CreateSessionResponse(session_id=session_id)


async def _load_session_from_db(
    session_id: str, db: AsyncSession
) -> dict | None:
    """
    从数据库加载会话到内存缓存。
    进程重启后 stream / snapshot 接口调用此方法恢复状态。
    """
    if session_id in _session_cache:
        return _session_cache[session_id]

    record = await session_repo.get_session(db, session_id)
    if not record:
        return None

    data = {
        "user_id": record.user_id,
        "user_prompt": record.user_prompt,
        "conversation_history": record.conversation_history or [],
        "attachments": record.attachments or [],
        "status": record.status,
        "report": record.report,
        "selected_agents": record.selected_agents or [],
        "agent_outputs": record.agent_outputs or {},
        "agent_statuses": record.agent_statuses or {},
    }
    _session_cache[session_id] = data
    return data


@router.get("/{session_id}/stream")
async def stream_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """
    SSE 流式接口：连接后自动开始执行多个 Agent。
    前端使用 EventSource 连接此接口接收实时输出。

    NOTE: db 依赖注入在 StreamingResponse 生成器中无法直接复用（生命周期不同），
          在 generator 内部通过 AsyncSessionFactory 新建独立 Session 进行写操作。
    """
    session_data = await _load_session_from_db(session_id, db)
    if not session_data:
        raise HTTPException(status_code=404, detail="会话不存在")

    # NOTE: 已完成 / 已出错 的会话不应重新执行 Orchestrator，
    #       直接返回已落盘的数据即可。这是防止"历史记录点击后重新生成"的核心保护。
    current_status = session_data.get("status", "pending")

    if current_status == "completed":
        async def _replay_completed() -> AsyncGenerator[str, None]:
            """已完成会话的快速重放：直接返回落盘数据，不调用 LLM"""
            import json as _j
            report = session_data.get("report")
            yield f"event: session_complete\ndata: {_j.dumps({'report': report or ''})}\n\n"

        return StreamingResponse(
            _replay_completed(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Access-Control-Allow-Origin": "*",
            },
        )

    user_prompt = session_data["user_prompt"]
    conversation_history = session_data.get("conversation_history", [])
    attachments = session_data.get("attachments", [])

    # NOTE: 加载 checkpoint：已落库的 agent 输出 + 状态 + 路由顺序
    #       Orchestrator 会跳过已完成的 Agent，直接重放存档输出
    checkpoint = {
        "agent_outputs": session_data.get("agent_outputs", {}),
        "agent_statuses": session_data.get("agent_statuses", {}),
        "selected_agents": session_data.get("selected_agents", []),
    }
    if not any(checkpoint.values()):
        checkpoint = None

    orchestrator = AgentOrchestrator()

    async def event_generator() -> AsyncGenerator[str, None]:
        # NOTE: StreamingResponse 的生成器在独立协程中运行，
        #       需要自己管理数据库 Session（不能复用 Depends 注入的 session）
        from app.db.database import AsyncSessionFactory

        _chunk_buffers: dict[str, str] = {}
        _last_persist_ts: dict[str, float] = {}
        THROTTLE_SECS = 1.0  # 每个 agent 最多每 1 秒写一次数据库，降低中断丢失的 chunk 量

        try:
            async with AsyncSessionFactory() as gen_db:
                # NOTE: 仅在非 completed 状态下才标记为 running（已完成的在上方短路返回）
                await session_repo.update_session_status(gen_db, session_id, "running")
                _session_cache[session_id]["status"] = "running"

                final_report: str | None = None

                async for event in orchestrator.run_session(
                    user_prompt, conversation_history, checkpoint=checkpoint, attachments=attachments
                ):
                    # 拦截 routing_decided：保存本次路由顺序
                    if "event: routing_decided" in event:
                        for line in event.split("\n"):
                            if line.startswith("data: "):
                                try:
                                    agents_list = _json.loads(line[6:])
                                    if isinstance(agents_list, list):
                                        _session_cache[session_id]["selected_agents"] = agents_list
                                        await session_repo.update_selected_agents(
                                            gen_db, session_id, agents_list
                                        )
                                except Exception:
                                    pass

                    # 拦截 agent_chunk：节流写库（防止 I/O 过频）
                    if "event: agent_chunk" in event:
                        for line in event.split("\n"):
                            if line.startswith("data: "):
                                try:
                                    payload = _json.loads(line[6:])
                                    aid = payload.get("id", "")
                                    chunk = payload.get("chunk", "")
                                    if aid and chunk:
                                        _chunk_buffers[aid] = _chunk_buffers.get(aid, "") + chunk
                                        now = _time.monotonic()
                                        if now - _last_persist_ts.get(aid, 0) >= THROTTLE_SECS:
                                            # NOTE: 强制写入超时，即使数据库由于连接黑洞卡死，也不能阻塞向前端推送文字的流！
                                            try:
                                                import asyncio
                                                await asyncio.wait_for(
                                                    session_repo.update_agent_output(
                                                        gen_db, session_id, aid,
                                                        _chunk_buffers[aid], status="running",
                                                    ),
                                                    timeout=3.0,
                                                )
                                                _last_persist_ts[aid] = now
                                            except asyncio.TimeoutError:
                                                logger.warning(f"更新 Agent {aid} 输出写库超时，回滚本次事务")
                                                await gen_db.rollback()
                                            except Exception as e:
                                                logger.warning(f"更新 Agent {aid} 输出失败: {e}")
                                                await gen_db.rollback()
                                except Exception:
                                    pass

                    # 拦截 agent_output：Agent 完整输出，立即最终落库
                    if "event: agent_output" in event:
                        for line in event.split("\n"):
                            if line.startswith("data: "):
                                try:
                                    payload = _json.loads(line[6:])
                                    aid = payload.get("id", "")
                                    content = payload.get("content", "")
                                    if aid and content:
                                        _chunk_buffers[aid] = content
                                        await session_repo.update_agent_output(
                                            gen_db, session_id, aid, content, status="completed"
                                        )
                                except Exception:
                                    pass

                    # 拦截 session_complete：提取最终报告
                    if "event: session_complete" in event:
                        for line in event.split("\n"):
                            if line.startswith("data: "):
                                try:
                                    payload = _json.loads(line[6:])
                                    r = payload.get("report")
                                    if isinstance(r, str):
                                        final_report = r
                                except Exception:
                                    pass

                    yield event

                # 流结束：写入最终报告并标记完成
                if final_report is not None:
                    await session_repo.set_session_report(gen_db, session_id, final_report)
                    _session_cache[session_id]["report"] = final_report
                else:
                    await session_repo.update_session_status(gen_db, session_id, "completed")

                _session_cache[session_id]["status"] = "completed"

        except Exception as e:
            logger.error("会话执行失败: %s, 错误: %s", session_id, e)
            yield f"event: error\ndata: {str(e)}\n\n"
            async with AsyncSessionFactory() as err_db:
                # NOTE: 连接中断时把已缓存的 chunk 强制落盘，
                #       确保刷新后前端能恢复已生成的内容
                for aid, buf in _chunk_buffers.items():
                    if buf:
                        try:
                            await session_repo.update_agent_output(
                                err_db, session_id, aid, buf, status="error"
                            )
                        except Exception:
                            pass
                await session_repo.update_session_status(err_db, session_id, "error")
            _session_cache[session_id]["status"] = "error"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # NOTE: 禁用 Nginx 缓冲，确保 SSE 实时推送
            "Access-Control-Allow-Origin": "*",
        },
    )


@router.get("/{session_id}/report")
async def get_report(
    session_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """获取已完成会话的报告（用于分享链接只读访问）"""
    session_data = await _load_session_from_db(session_id, db)
    if not session_data:
        raise HTTPException(status_code=404, detail="会话不存在")
    if session_data["status"] != "completed":
        raise HTTPException(status_code=202, detail="报告尚未生成完成")
    return {"session_id": session_id, "report": session_data.get("report")}


@router.get("/{session_id}/snapshot")
async def get_snapshot(
    session_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    获取会话的实时快照（无论是否完成）。
    前端刷新后优先调用此接口恢复 UI 状态。
    进程重启后从数据库重新加载，不依赖内存缓存。
    """
    # NOTE: 不走缓存，直接查库，保证进程重启后仍能返回最新数据
    record = await session_repo.get_session(db, session_id)
    if not record:
        # 降级到内存缓存（极端情况：db 查无记录但缓存仍在）
        if session_id in _session_cache:
            data = _session_cache[session_id]
        else:
            raise HTTPException(status_code=404, detail="会话不存在")
    else:
        data = {
            "status": record.status,
            "user_prompt": record.user_prompt,
            "agent_outputs": record.agent_outputs or {},
            "agent_statuses": record.agent_statuses or {},
            "report": record.report,
            "selected_agents": record.selected_agents or [],
        }

    agent_outputs = data.get("agent_outputs") or {}
    agent_statuses = data.get("agent_statuses") or {}
    report = data.get("report")

    # NOTE: 兼容旧版会话格式：早期只落盘了 report，没有 agent_outputs
    if not agent_outputs and report:
        agent_outputs = {"consultant_review": report}
        agent_statuses = {"consultant_review": "completed"}

    return {
        "session_id": session_id,
        "status": data.get("status", "pending"),
        "user_prompt": data.get("user_prompt", ""),
        "agent_outputs": agent_outputs,
        "agent_statuses": agent_statuses,
        "report": report,
        "selected_agents": data.get("selected_agents") or [],
    }
