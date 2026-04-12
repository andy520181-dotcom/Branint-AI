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
from pydantic import BaseModel
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import AsyncSessionFactory

from app.db.database import get_db
from app.repository import session_repo, event_repo
from app.schema.session import (
    CreateSessionRequest,
    CreateSessionResponse,
    ContinueSessionRequest,
    SessionListItem,
    SessionMetaUpdate,
)
from app.service.agent_orchestrator import AgentOrchestrator

router = APIRouter(prefix="/api/sessions", tags=["sessions"])
logger = logging.getLogger(__name__)

# NOTE: 内存缓存层：减少 SSE 流式执行期间的数据库读取次数。
#       仅在 stream_session 执行期间持有，进程内共享。
#       进程重启后从数据库重新加载 —— 这正是 PostgreSQL 迁移的核心收益。
_session_cache: dict[str, dict] = {}


# ─── 会话列表与元数据管理 ─────────────────────

@router.get("", response_model=list[SessionListItem])
async def list_user_sessions(
    user_id: str,
    db: AsyncSession = Depends(get_db),
) -> list[SessionListItem]:
    records = await session_repo.get_user_sessions(db, user_id)
    return [
        SessionListItem(
            session_id=r.id,
            title=r.title or (r.user_prompt[:40] if r.user_prompt else "新对话"),
            is_pinned=bool(r.is_pinned),
            created_at=r.created_at,
            updated_at=r.updated_at,
        )
        for r in records
    ]

@router.put("/{session_id}/meta")
async def update_session_meta(
    session_id: str,
    body: SessionMetaUpdate,
    db: AsyncSession = Depends(get_db),
) -> dict:
    await session_repo.update_session_meta(
        db, session_id, title=body.title, is_pinned=body.is_pinned
    )
    return {"status": "ok"}

@router.delete("/{session_id}")
async def delete_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    await session_repo.delete_session(db, session_id)
    return {"status": "ok"}


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
    title_val = body.title if body.title else body.user_prompt[:40]

    await session_repo.create_session(
        db,
        session_id=session_id,
        user_id=body.user_id,
        title=title_val,
        user_prompt=body.user_prompt,
        conversation_history=[r.model_dump() for r in body.conversation_history],
        attachments=body.attachments,
        strategy_clarification_answers=body.strategy_clarification_answers,
        strategy_clarify_round=body.strategy_clarify_round,
    )

    # NOTE: 同步写入内存缓存，避免 stream_session 立即查库
    _session_cache[session_id] = {
        "user_id": body.user_id,
        "title": title_val,
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

    # NOTE: POST 接口负责直接启动后台任务，实现真正的读写分离
    from app.service.stream_broadcaster import get_or_create_broadcaster
    import asyncio

    broadcaster, _ = get_or_create_broadcaster(session_id)
    session_data = _session_cache[session_id]
    
    logger.info("启动后台 Orchestrator 任务: %s", session_id)
    asyncio.create_task(
        _run_orchestrator_background(session_id, session_data, broadcaster),
        name=f"orchestrator-{session_id[:8]}",
    )

    return CreateSessionResponse(session_id=session_id)


@router.patch("/{session_id}/continue")
async def continue_session(
    session_id: str,
    body: ContinueSessionRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    继续现有会话。

    NOTE: 多轮对话或战略追问回复时调用（区别于 POST /sessions 的新建）。
    复用已有的 session_id 不变，只更新 user_prompt、conversation_history 等字段，
    并重置 status = pending、清空 agent_outputs 准备重跑新一轮 Orchestrator。
    """
    # 1. 持久化：更新现有会话记录
    await session_repo.continue_session(
        db,
        session_id=session_id,
        user_prompt=body.user_prompt,
        conversation_history=[r.model_dump() for r in body.conversation_history],
        attachments=body.attachments,
        strategy_clarification_answers=body.strategy_clarification_answers,
        strategy_clarify_round=body.strategy_clarify_round or 0,
    )

    # 获取最新落地的数据
    record = await session_repo.get_session(db, session_id)

    # 2. 更新内存缓存，保证 SSE stream 立即使用新的数据（带有保留的 market 输出）
    _session_cache[session_id] = {
        "user_prompt": body.user_prompt,
        "conversation_history": [r.model_dump() for r in body.conversation_history],
        "attachments": body.attachments,
        "strategy_clarification_answers": body.strategy_clarification_answers,
        "strategy_clarify_round": body.strategy_clarify_round or 0,
        "status": "pending",
        "report": record.report if record else None,
        "selected_agents": record.selected_agents if record else [],
        "agent_outputs": record.agent_outputs if record else {},
        "agent_statuses": record.agent_statuses if record else {},
    }

    # 3. 启动新一轮 Orchestrator 后台任务
    from app.service.stream_broadcaster import get_or_create_broadcaster
    import asyncio

    broadcaster, _ = get_or_create_broadcaster(session_id)
    session_data = _session_cache[session_id]

    logger.info("续写会话，启动新一轮 Orchestrator: %s", session_id)
    asyncio.create_task(
        _run_orchestrator_background(session_id, session_data, broadcaster),
        name=f"orchestrator-cont-{session_id[:8]}",
    )

    return {"status": "ok", "session_id": session_id}

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
        "asset_recommendations": getattr(record, "agent_media", {}).get("assetRecommendations", {}),
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
    SSE 流式接口：纯只读监听器。
    
    绝对禁止在此接口中启动任何大模型生成任务。
    如果 broadcaster 在线，则听取实时流；
    如果不在线（已完成或进程崩溃过），直接从 event_log 播放录像并结束。
    """
    from app.service.stream_broadcaster import get_broadcaster
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

    broadcaster = get_broadcaster(session_id)

    if broadcaster:
        # 广播器在线：证明是当前进程刚 POST 创建的、真正在跑的会话
        logger.info("广播器在线，接入监听: %s (Last-Event-ID=%s)", session_id, last_event_id)

        async def sse_listener_live() -> AsyncGenerator[str, None]:
            async for event in broadcaster.listen():
                yield event

        return StreamingResponse(sse_listener_live(), media_type="text/event-stream", headers=SSE_HEADERS)

    # 广播器不在线：说明会话要么已完成，要么是历史死会话（比如进程重启、断网等导致的僵尸记录）
    if current_status in ("pending", "running"):
        # 对这种因为没跑完而阴魂不散的僵尸，静默超度为 error，禁止其未来任何复苏企图
        async def _fix_ghost_session() -> None:
            from app.db.database import AsyncSessionFactory as ASF
            async with ASF() as fix_db:
                await session_repo.update_session_status(fix_db, session_id, "error")
                logger.info("自动将孤儿运行态超度为 error（禁止重新生成）: %s", session_id)
        asyncio.create_task(_fix_ghost_session(), name=f"fix-ghost-{session_id[:8]}")

    async def _replay_from_eventlog() -> AsyncGenerator[str, None]:
        """纯只读回放，绝不会等待未来事件，放完就关。"""
        from app.db.database import AsyncSessionFactory
        events = []
        try:
            async with AsyncSessionFactory() as replay_db:
                events = await event_repo.fetch_since(replay_db, session_id, resume_seq)
        except Exception as e:
            # NOTE: 兜底容错——如果 agent_events 表不存在或查询失败，
            # 直接降级到 DB 快照路径，确保刷新后图片不丢失
            logger.warning("event_log 查询失败，降级走快照回放: %s (%s)", session_id, e)
            events = []

        if events:
            for ev in events:
                yield f"id: {ev.seq}\n{ev.raw_sse}"
                if not ev.raw_sse.endswith("\n\n"):
                    yield "\n"
        else:
            # 降级：event_log 无记录，从 DB 快照强行塞入
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
            _session_paused: bool = False  # NOTE: 追踪是否因战略追问而挂起（非正常完成）

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
                                        # NOTE: 彻底干掉 agent_chunk 的全过程写库！
                                        # 包括不写 sessions，也不写 event_log！
                                        # 因为快照和前端重连完全依靠基于内存的 _history 压缩重建。
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
                    # NOTE: 已彻底移除在此处高频同步调用 sessions 表 update 的逻辑！
                    # 频繁修改 JSONB 会导致严重的行锁竞争（写库超时），甚至会毒化数据库连接，
                    # 牵连整个 LLM 异步生成流出现长达 3.0s 的挂起延迟。
                    # 全量内容完全由 _history 提供前端恢复，后端仅需在完成时落库一次即可。
                    pass

                if "event: agent_output" in event:
                    for line in event.split("\n"):
                        if line.startswith("data: "):
                            try:
                                payload = _json.loads(line[6:])
                                aid = payload.get("id", "")
                                content = payload.get("content", "")
                                merged = payload.get("merged_content")
                                
                                if aid and content:
                                    _chunk_buffers[aid] = content
                                    await session_repo.update_agent_output(
                                        gen_db, session_id, aid, content, status="completed"
                                    )
                                    if merged:
                                        # 隐藏写入：后端树使用完整的文档，但不渲染给前端
                                        await session_repo.update_agent_output(
                                            gen_db, session_id, f"{aid}_merged", merged, status="completed"
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

                if "event: agent_asset_recommendations" in event:
                    for line in event.split("\n"):
                        if line.startswith("data: "):
                            try:
                                payload = _json.loads(line[6:])
                                aid = payload.get("id")
                                recs = payload.get("recommendations", [])
                                if aid:
                                    await session_repo.set_asset_recommendations(gen_db, session_id, aid, recs)
                                    if session_id in _session_cache:
                                        if "asset_recommendations" not in _session_cache[session_id]:
                                            _session_cache[session_id]["asset_recommendations"] = {}
                                        _session_cache[session_id]["asset_recommendations"][aid] = recs
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
                    # NOTE: session_pause = 战略追问挂起，等待用户回答。
                    # 必须记录此状态，防止 for 循环正常结束后错误落盘为 completed。
                    _session_paused = True

            # 流结束：写入最终报告，或保持挂起状态
            if final_report is not None:
                # 正常完成：写入 report 并标记 completed
                await session_repo.set_session_report(gen_db, session_id, final_report)
                if session_id in _session_cache:
                    _session_cache[session_id]["report"] = final_report
                if session_id in _session_cache:
                    _session_cache[session_id]["status"] = "completed"
                logger.info("后台任务完成: %s (event_log 已落盘)", session_id)
            elif _session_paused:
                # NOTE: 战略追问挂起 — 维持 running 状态，等待用户通过 PATCH /continue 续写。
                # 不能标记为 completed，否则前端刷新时会误判已完成、停止等待。
                logger.info("后台任务挂起（等待追问回答）: %s", session_id)
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
            "asset_recommendations": getattr(record, "agent_media", {}).get("assetRecommendations", {}),
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
        "asset_recommendations": data.get("asset_recommendations") or {},
        "report": report,
        "selected_agents": data.get("selected_agents") or [],
        "conversation_history": data.get("conversation_history") or [],
    }


# ─── 视觉资产显式生成接口（路径 A：用户主动触发）─────────────────────

class GenerateAssetRequest(BaseModel):
    """用户从 Scher 气泡下方点击按钮触发的图片生成请求体"""
    asset_type: str = "logo"   # "logo" | "poster" | "banner"
    count: int = 1             # 生成数量，限 1-4 张


@router.post("/{session_id}/generate-asset")
async def generate_asset(
    session_id: str,
    body: GenerateAssetRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    路径 A 视觉资产生成接口：用户主动触发，返回生成后的图片 URL 列表。

    NOTE: 从该 session 的 agent_outputs 中提取品牌上下文，
          自动拼接高品质英文生图 prompt，避免用户手动填提示词。
    """
    session_data = await _load_session_from_db(session_id, db)
    if not session_data:
        raise HTTPException(status_code=404, detail="会话不存在")

    agent_outputs: dict = session_data.get("agent_outputs") or {}
    brand_context = " ".join([
        v[:400] for k, v in agent_outputs.items()
        if isinstance(v, str) and len(v) > 20
    ])
    context_hint = brand_context[:120].replace("\n", " ").strip()

    asset_type = body.asset_type
    base_prompts = {
        "logo": (
            "Minimalist professional brand logo design, clean geometric shapes, "
            "scalable vector style, white background, modern typography, high contrast, award-winning design"
        ),
        "poster": (
            "Premium brand poster design, bold visual hierarchy, sophisticated color palette, "
            "professional layout, print-ready quality, contemporary aesthetic"
        ),
        "banner": (
            "Modern brand banner design, wide format, clean composition, "
            "strong brand identity, digital advertising quality"
        ),
    }
    base_prompt = base_prompts.get(asset_type, base_prompts["logo"])
    final_prompt = f"{base_prompt}. Brand context: {context_hint}" if context_hint else base_prompt
    aspect_ratio = {"logo": "1:1", "poster": "9:16", "banner": "16:9"}.get(asset_type, "1:1")
    count = max(1, min(body.count, 4))

    from app.service.image_generator import generate_brand_images
    import asyncio

    tasks = [generate_brand_images(asset_type, final_prompt, aspect_ratio) for _ in range(count)]
    results_list = await asyncio.gather(*tasks, return_exceptions=True)

    images = []
    for result in results_list:
        if isinstance(result, list):
            images.extend(result)
        elif isinstance(result, Exception):
            logger.error("图片生成任务失败: %s", result)

    if not images:
        raise HTTPException(status_code=500, detail="图片生成失败，请稍后重试")

    async with AsyncSessionFactory() as media_db:
        for img in images:
            await session_repo.update_agent_media(
                media_db, session_id, "agentImages",
                {"id": "visual", "type": asset_type, "data_url": img.get("data_url", "")}
            )

    logger.info("Session %s 成功生成 %d 张 %s 资产", session_id[:8], len(images), asset_type)
    return {"images": images}
