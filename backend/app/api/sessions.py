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

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.repository import session_repo, event_repo
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
) -> Optional[dict]:
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
    last_event_id: Optional[str] = Header(None, alias="Last-Event-ID"),
) -> StreamingResponse:
    """
    SSE 流式接口：连接后自动开始执行多个 Agent。
    前端使用 EventSource 连接此接口接收实时输出。

    NOTE: 三条数据路径（优先级从高到低）：

      路径 A：Last-Event-ID 存在（刷新/断线重连）
        → 广播器在线：接入广播器，先回放内存中漏掉的事件，再实时接收
        → 广播器离线（进程重启）：从 DB event_log 精确续传，同时重启 Orchestrator
          填充剩余（如果 status 还是 running）

      路径 B：首次连接（Last-Event-ID 为空，非 completed）
        → 创建广播器 + 启动后台 Orchestrator 任务

      路径 C：已完成会话
        → 直接从 event_log（或 DB 快照）回放所有事件
    """
    from app.service.stream_broadcaster import get_broadcaster, get_or_create_broadcaster
    import asyncio

    session_data = await _load_session_from_db(session_id, db)
    if not session_data:
        raise HTTPException(status_code=404, detail="会话不存在")

    current_status = session_data.get("status", "pending")
    resume_seq = int(last_event_id) if last_event_id and last_event_id.isdigit() else 0

    SSE_HEADERS = {
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
        "Access-Control-Allow-Origin": "*",
    }

    # ─── 路径 C：已完成会话 — 从 event_log 精确回放（最权威）───────────────
    if current_status == "completed":
        async def _replay_from_eventlog() -> AsyncGenerator[str, None]:
            """优先从 event_log 回放（有 seq id 字段，前端可精确追踪位置）"""
            from app.db.database import AsyncSessionFactory
            async with AsyncSessionFactory() as replay_db:
                events = await event_repo.fetch_since(replay_db, session_id, resume_seq)

            if events:
                # event_log 有完整记录，逐条回放（保留原始 SSE 格式）
                for ev in events:
                    yield f"id: {ev.seq}\n{ev.raw_sse}"
                    if not ev.raw_sse.endswith("\n\n"):
                        yield "\n"
            else:
                # 降级：event_log 无记录（旧会话），从 DB 快照构建
                report = session_data.get("report")
                agent_outputs = session_data.get("agent_outputs") or {}
                selected = session_data.get("selected_agents") or []
                agent_media = session_data.get("agent_media") or {}

                if selected:
                    yield f"event: routing_decided\ndata: {_json.dumps(selected)}\n\n"
                for aid, output in agent_outputs.items():
                    if output:
                        yield f"event: agent_start\ndata: {aid}\n\n"
                        yield f"event: agent_output\ndata: {_json.dumps({'id': aid, 'content': output}, ensure_ascii=False)}\n\n"
                        yield f"event: agent_complete\ndata: {aid}\n\n"
                for img in agent_media.get("agentImages", []):
                    yield f"event: agent_image\ndata: {_json.dumps(img, ensure_ascii=False)}\n\n"
                for vid in agent_media.get("agentVideos", []):
                    yield f"event: agent_video\ndata: {_json.dumps(vid, ensure_ascii=False)}\n\n"
                yield f"event: session_complete\ndata: {_json.dumps({'report': report or ''})}\n\n"

        return StreamingResponse(_replay_from_eventlog(), media_type="text/event-stream", headers=SSE_HEADERS)

    # ─── 路径 A & B：会话仍在运行 ──────────────────────────────────────────
    broadcaster = get_broadcaster(session_id)

    if broadcaster:
        # 路径 A-1：广播器在线（刷新重连），接入即得最新进度
        logger.info("广播器在线，刷新重连: %s (Last-Event-ID=%s)", session_id, last_event_id)

        async def sse_listener_live() -> AsyncGenerator[str, None]:
            async for event in broadcaster.listen():
                yield event

        return StreamingResponse(sse_listener_live(), media_type="text/event-stream", headers=SSE_HEADERS)

    # 路径 A-2 或 B：广播器不在线（进程重启 或 首次连接）
    broadcaster, is_new = get_or_create_broadcaster(session_id)

    if resume_seq > 0:
        # 路径 A-2：进程重启后的续传（Last-Event-ID 存在但广播器已死）
        # 先从 event_log 把 0..resume_seq 的历史灌入广播器（内存快速回放用）
        # 再根据 status 决定是否重启 Orchestrator
        logger.info("进程重启续传: %s (从 seq=%d 继续)", session_id, resume_seq)
        async with db as restore_db:
            missed = await event_repo.fetch_since(restore_db, session_id, 0)
            for ev in missed:
                broadcaster.put(f"id: {ev.seq}\n{ev.raw_sse}")
    else:
        logger.info("首次连接，启动后台 Orchestrator: %s", session_id)

    if is_new or current_status in ("pending", "running"):
        asyncio.create_task(
            _run_orchestrator_background(session_id, session_data, broadcaster),
            name=f"orchestrator-{session_id[:8]}",
        )

    async def sse_listener() -> AsyncGenerator[str, None]:
        async for event in broadcaster.listen():
            yield event

    return StreamingResponse(sse_listener(), media_type="text/event-stream", headers=SSE_HEADERS)





async def _run_orchestrator_background(
    session_id: str,
    session_data: dict,
    broadcaster: "SessionBroadcaster",
) -> None:
    """
    后台独立运行 Orchestrator，完全不依赖任何 HTTP 连接。
    所有产出通过 broadcaster.put() 推送给所有订阅的前端连接。

    Event Sourcing：每条关键事件先写入 agent_events 表（append-only），
    再推给广播器。进程重启后可从 DB 精确续传到任意位置。

    NOTE: 此函数通过 asyncio.create_task() 挂靠在 uvicorn 的事件循环上，
          生命周期独立于 HTTP 请求，浏览器断连不会 cancel 该 task。
    """
    from app.service.stream_broadcaster import remove_broadcaster, SessionBroadcaster
    from app.db.database import AsyncSessionFactory
    import asyncio as _asyncio

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
    _last_persist_ts: dict[str, float] = {}   # sessions 表写入节流
    _last_evlog_ts: dict[str, float] = {}      # event_log chunk 写入节流
    EVLOG_THROTTLE = 2.0                        # event_log 的 chunk 最小写入间隔（秒）

    try:
        async with AsyncSessionFactory() as gen_db:
            await session_repo.update_session_status(gen_db, session_id, "running")
            if session_id in _session_cache:
                _session_cache[session_id]["status"] = "running"

            final_report: Optional[str] = None

            async for event in orchestrator.run_session(
                user_prompt,
                conversation_history,
                checkpoint=checkpoint,
                attachments=attachments,
                strategy_clarification_answers=session_data.get("strategy_clarification_answers"),
                strategy_clarify_round=session_data.get("strategy_clarify_round", 0),
            ):
                is_chunk = "event: agent_chunk" in event
                is_heartbeat = event.strip().startswith(": heartbeat")

                # ── Event Sourcing：非心跳事件写入 event_log ──────────────
                if not is_heartbeat:
                    if not is_chunk:
                        # 关键事件（routing_decided / agent_output / agent_complete 等）立即落盘
                        try:
                            seq = await event_repo.append_independent(session_id, event)
                            broadcaster.put(f"id: {seq}\n{event}")
                        except Exception as evlog_err:
                            logger.warning("event_log 写入失败（降级无 seq）: %s", evlog_err)
                            broadcaster.put(event)
                    else:
                        # agent_chunk：节流写 event_log（高频 token 不能每次都写 DB）
                        for line in event.split("\n"):
                            if line.startswith("data: "):
                                try:
                                    payload = _json.loads(line[6:])
                                    aid = payload.get("id", "")
                                    chunk = payload.get("chunk", "")
                                    if aid and chunk:
                                        _chunk_buffers[aid] = _chunk_buffers.get(aid, "") + chunk
                                        now = _time.monotonic()
                                        if now - _last_evlog_ts.get(aid, 0) >= EVLOG_THROTTLE:
                                            try:
                                                seq = await event_repo.append_independent(session_id, event)
                                                broadcaster.put(f"id: {seq}\n{event}")
                                                _last_evlog_ts[aid] = now
                                            except Exception:
                                                broadcaster.put(event)
                                        else:
                                            # 节流期内不写 event_log，但实时推送广播（保证流畅）
                                            broadcaster.put(event)
                                except Exception:
                                    broadcaster.put(event)
                else:
                    # 心跳直接广播，不写 DB
                    broadcaster.put(event)

                # ── 拦截业务事件更新 sessions 表 ─────────────────────────
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

                if "event: agent_chunk" in event:
                    for line in event.split("\n"):
                        if line.startswith("data: "):
                            try:
                                payload = _json.loads(line[6:])
                                aid = payload.get("id", "")
                                if aid and _chunk_buffers.get(aid):
                                    now = _time.monotonic()
                                    if now - _last_persist_ts.get(aid, 0) >= 1.0:
                                        try:
                                            await _asyncio.wait_for(
                                                session_repo.update_agent_output(
                                                    gen_db, session_id, aid,
                                                    _chunk_buffers[aid], status="running",
                                                ),
                                                timeout=3.0,
                                            )
                                            _last_persist_ts[aid] = now
                                        except _asyncio.TimeoutError:
                                            logger.warning("sessions 写库超时 agent=%s", aid)
                                            await gen_db.rollback()
                                        except Exception as e:
                                            logger.warning("sessions 写库失败 agent=%s: %s", aid, e)
                                            await gen_db.rollback()
                            except Exception:
                                pass

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

                if "event: agent_image" in event or "event: agent_video" in event:
                    event_type_key = "agentImages" if "agent_image" in event else "agentVideos"
                    for line in event.split("\n"):
                        if line.startswith("data: "):
                            try:
                                payload = _json.loads(line[6:])
                                await session_repo.update_agent_media(gen_db, session_id, event_type_key, payload)
                            except Exception:
                                pass

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

                if "event: session_pause" in event:
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
            logger.info("后台任务完成: %s (event_log 已落盘)", session_id)

    except Exception as e:
        logger.error("后台 Orchestrator 异常: %s, 错误: %s", session_id, e, exc_info=True)
        error_event = f"event: error\ndata: {str(e)}\n\n"
        broadcaster.put(error_event)

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

