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
        "agent_media": getattr(record, "agent_media", {}),
        "strategy_clarification_answers": getattr(record, "strategy_clarification_answers", None),
        "strategy_clarify_round": getattr(record, "strategy_clarify_round", 0),
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

    NOTE: 核心架构——Orchestrator 以 asyncio.create_task 独立挂靠在事件循环上，
          HTTP 连接只是"旁听频道"。浏览器刷新时：
          - 旧的 HTTP 连接断开，对应队列被销毁
          - 后台 Orchestrator 进程完全不受影响，继续运行
          - 新的 HTTP 连接接入广播器，立刻收到 history replay（补到当前进度）
          - 之后实时接收新产出的 chunks

    两条路径：
      A. 首次连接（或进程重启后）：创建广播器 + 启动后台任务
      B. 刷新重连：广播器已存在，直接订阅，秒速回放历史事件
    """
    from app.service.stream_broadcaster import get_or_create_broadcaster, remove_broadcaster
    import asyncio

    session_data = await _load_session_from_db(session_id, db)
    if not session_data:
        raise HTTPException(status_code=404, detail="会话不存在")

    current_status = session_data.get("status", "pending")

    # 已完成的会话：直接从 DB 回放，无需 Orchestrator
    if current_status == "completed":
        async def _replay_completed() -> AsyncGenerator[str, None]:
            """已完成会话的快速重放：直接返回落盘数据，不调用 LLM"""
            report = session_data.get("report")
            # 回放所有已落盘的 agent 输出
            agent_outputs = session_data.get("agent_outputs") or {}
            agent_statuses = session_data.get("agent_statuses") or {}
            selected = session_data.get("selected_agents") or []

            if selected:
                yield f"event: routing_decided\ndata: {_json.dumps(selected)}\n\n"

            for aid, output in agent_outputs.items():
                if output:
                    yield f"event: agent_start\ndata: {aid}\n\n"
                    yield f"event: agent_chunk\ndata: {_json.dumps({'id': aid, 'chunk': output}, ensure_ascii=False)}\n\n"
                    yield f"event: agent_output\ndata: {_json.dumps({'id': aid, 'content': output}, ensure_ascii=False)}\n\n"
                    yield f"event: agent_complete\ndata: {aid}\n\n"

            # 回放媒体资产
            agent_media = session_data.get("agent_media") or {}
            for img in agent_media.get("agentImages", []):
                yield f"event: agent_image\ndata: {_json.dumps(img, ensure_ascii=False)}\n\n"
            for vid in agent_media.get("agentVideos", []):
                yield f"event: agent_video\ndata: {_json.dumps(vid, ensure_ascii=False)}\n\n"

            yield f"event: session_complete\ndata: {_json.dumps({'report': report or ''})}\n\n"

        return StreamingResponse(
            _replay_completed(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Access-Control-Allow-Origin": "*",
            },
        )

    # 获取或创建广播器
    broadcaster, is_new = get_or_create_broadcaster(session_id)

    if is_new:
        # 路径 A：首次连接，启动后台 Orchestrator 任务
        logger.info("首次连接，启动后台 Orchestrator 任务: %s", session_id)
        asyncio.create_task(
            _run_orchestrator_background(session_id, session_data, broadcaster),
            name=f"orchestrator-{session_id[:8]}",
        )
    else:
        logger.info("刷新重连，接入已有广播器: %s (历史事件数=%d)", session_id, len(broadcaster._history))

    async def sse_listener() -> AsyncGenerator[str, None]:
        """从广播器订阅事件流，回放历史后接收实时推送"""
        async for event in broadcaster.listen():
            yield event

    return StreamingResponse(
        sse_listener(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
        },
    )


async def _run_orchestrator_background(
    session_id: str,
    session_data: dict,
    broadcaster: "SessionBroadcaster",
) -> None:
    """
    后台独立运行 Orchestrator，完全不依赖任何 HTTP 连接。
    所有产出通过 broadcaster.put() 推送给所有订阅的前端连接。

    NOTE: 此函数通过 asyncio.create_task() 挂靠在 uvicorn 的事件循环上，
          生命周期独立于 HTTP 请求，浏览器断连不会 cancel 该 task。
    """
    from app.service.stream_broadcaster import remove_broadcaster, SessionBroadcaster
    from app.db.database import AsyncSessionFactory

    user_prompt = session_data["user_prompt"]
    conversation_history = session_data.get("conversation_history", [])
    attachments = session_data.get("attachments", [])

    checkpoint = {
        "agent_outputs": session_data.get("agent_outputs", {}),
        "agent_statuses": session_data.get("agent_statuses", {}),
        "selected_agents": session_data.get("selected_agents", []),
    }
    if not any(checkpoint.values()):
        checkpoint = None

    orchestrator = AgentOrchestrator()
    _chunk_buffers: dict[str, str] = {}
    _last_persist_ts: dict[str, float] = {}
    THROTTLE_SECS = 1.0

    try:
        async with AsyncSessionFactory() as gen_db:
            await session_repo.update_session_status(gen_db, session_id, "running")
            if session_id in _session_cache:
                _session_cache[session_id]["status"] = "running"

            final_report: str | None = None

            async for event in orchestrator.run_session(
                user_prompt,
                conversation_history,
                checkpoint=checkpoint,
                attachments=attachments,
                strategy_clarification_answers=session_data.get("strategy_clarification_answers"),
                strategy_clarify_round=session_data.get("strategy_clarify_round", 0),
            ):
                # 推送给所有在线听众
                broadcaster.put(event)

                # 拦截 routing_decided
                if "event: routing_decided" in event:
                    for line in event.split("\n"):
                        if line.startswith("data: "):
                            try:
                                agents_list = _json.loads(line[6:])
                                if isinstance(agents_list, list):
                                    if session_id in _session_cache:
                                        _session_cache[session_id]["selected_agents"] = agents_list
                                    await session_repo.update_selected_agents(gen_db, session_id, agents_list)
                            except Exception:
                                pass

                # 拦截 agent_chunk：节流写库
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
                                        try:
                                            import asyncio as _asyncio
                                            await _asyncio.wait_for(
                                                session_repo.update_agent_output(
                                                    gen_db, session_id, aid,
                                                    _chunk_buffers[aid], status="running",
                                                ),
                                                timeout=3.0,
                                            )
                                            _last_persist_ts[aid] = now
                                        except _asyncio.TimeoutError:
                                            logger.warning("写库超时 agent=%s", aid)
                                            await gen_db.rollback()
                                        except Exception as e:
                                            logger.warning("写库失败 agent=%s: %s", aid, e)
                                            await gen_db.rollback()
                            except Exception:
                                pass

                # 拦截 agent_output：立即最终落库
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

                # 拦截 agent_image / agent_video 落库
                if "event: agent_image" in event or "event: agent_video" in event:
                    event_type = "agentImages" if "agent_image" in event else "agentVideos"
                    for line in event.split("\n"):
                        if line.startswith("data: "):
                            try:
                                payload = _json.loads(line[6:])
                                await session_repo.update_agent_media(gen_db, session_id, event_type, payload)
                            except Exception:
                                pass

                # 拦截 session_complete
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

                # 拦截 session_pause（战略追问挂起）
                if "event: session_pause" in event:
                    # 不关闭广播器，等待下一次连接（新 session_id）
                    logger.info("会话挂起（战略追问）: %s", session_id)

            # 流结束：写入最终报告
            if final_report is not None:
                await session_repo.set_session_report(gen_db, session_id, final_report)
                if session_id in _session_cache:
                    _session_cache[session_id]["report"] = final_report
            else:
                await session_repo.update_session_status(gen_db, session_id, "completed")

            if session_id in _session_cache:
                _session_cache[session_id]["status"] = "completed"
            logger.info("后台任务完成: %s", session_id)

    except Exception as e:
        logger.error("后台 Orchestrator 异常: %s, 错误: %s", session_id, e, exc_info=True)
        error_event = f"event: error\ndata: {str(e)}\n\n"
        broadcaster.put(error_event)

        # 错误时强制落盘所有已缓存 chunk
        async with AsyncSessionFactory() as err_db:
            for aid, buf in _chunk_buffers.items():
                if buf:
                    try:
                        await session_repo.update_agent_output(err_db, session_id, aid, buf, status="error")
                    except Exception:
                        pass
            await session_repo.update_session_status(err_db, session_id, "error")

        if session_id in _session_cache:
            _session_cache[session_id]["status"] = "error"

    finally:
        # 无论成功失败，都关闭广播器（通知所有监听者结束）
        broadcaster.close()
        remove_broadcaster(session_id)






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

    NOTE: 当会话处于 running 状态时，agent_outputs 可能落盘不全（节流机制），
          因此额外融合内存广播器的历史事件来补全内容。
    """
    from app.service.stream_broadcaster import get_broadcaster

    # NOTE: 直接查库，保证进程重启后仍能返回最新数据
    record = await session_repo.get_session(db, session_id)
    if not record:
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
            "agent_media": getattr(record, "agent_media", {}) or {},
            "report": record.report,
            "selected_agents": record.selected_agents or [],
            "conversation_history": record.conversation_history or [],
        }

    agent_outputs = dict(data.get("agent_outputs") or {})
    agent_statuses = dict(data.get("agent_statuses") or {})
    report = data.get("report")

    # NOTE: 兼容旧版会话格式：早期只落盘了 report，没有 agent_outputs
    if not agent_outputs and report:
        agent_outputs = {"consultant_review": report}
        agent_statuses = {"consultant_review": "completed"}

    # NOTE: 对 running 状态下的会话，广播器 history 里存有最新 chunk 数据，
    #       但节流写库导致 DB 可能落盘较旧版本。通过重放 history 补全落盘缺口。
    broadcaster = get_broadcaster(session_id)
    if broadcaster and data.get("status") == "running":
        # 从广播历史中解析 agent_chunk 累加，得到最新的实时内容
        realtime_buffers: dict[str, str] = {}
        for event in broadcaster._history:
            if "event: agent_chunk" in event:
                for line in event.split("\n"):
                    if line.startswith("data: "):
                        try:
                            payload = _json.loads(line[6:])
                            aid = payload.get("id", "")
                            chunk = payload.get("chunk", "")
                            if aid and chunk:
                                realtime_buffers[aid] = realtime_buffers.get(aid, "") + chunk
                        except Exception:
                            pass
            elif "event: routing_decided" in event:
                for line in event.split("\n"):
                    if line.startswith("data: "):
                        try:
                            agents_list = _json.loads(line[6:])
                            if isinstance(agents_list, list) and not data.get("selected_agents"):
                                data["selected_agents"] = agents_list
                        except Exception:
                            pass
        # 用实时 buffer 覆盖落盘数据中较旧的内容
        for aid, content in realtime_buffers.items():
            if len(content) > len(agent_outputs.get(aid, "")):
                agent_outputs[aid] = content
                agent_statuses[aid] = "running"

    return {
        "session_id": session_id,
        "status": data.get("status", "pending"),
        "user_prompt": data.get("user_prompt", ""),
        "agent_outputs": agent_outputs,
        "agent_statuses": agent_statuses,
        "agent_media": data.get("agent_media") or {},
        "report": report,
        "selected_agents": data.get("selected_agents") or [],
        "conversation_history": data.get("conversation_history") or [],
    }

