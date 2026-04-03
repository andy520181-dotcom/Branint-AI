import uuid
import logging
from collections.abc import AsyncGenerator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.schema.session import CreateSessionRequest, CreateSessionResponse
from app.service.agent_orchestrator import AgentOrchestrator
from app.storage.session_persist import (
    extract_report_from_sse_chunk,
    load_session_disk,
    save_session_disk,
    update_session_agent_output,
)

router = APIRouter(prefix="/api/sessions", tags=["sessions"])
logger = logging.getLogger(__name__)

# NOTE: 内存索引；会话正文同时落盘到 data/sessions，便于分享链接在重启后仍可拉取
# FIXME: Phase 2 可替换为 Supabase 数据库持久化
_sessions: dict[str, dict] = {}


def _ensure_session_loaded(session_id: str) -> bool:
    if session_id in _sessions:
        return True
    data = load_session_disk(session_id)
    if not data:
        return False
    _sessions[session_id] = data
    return True


@router.post("", response_model=CreateSessionResponse)
async def create_session(body: CreateSessionRequest) -> CreateSessionResponse:
    """
    创建新的品牌咨询会话
    返回 session_id 供前端连接 SSE 流
    """
    session_id = str(uuid.uuid4())
    _sessions[session_id] = {
        "user_id": body.user_id,
        "user_prompt": body.user_prompt,
        "conversation_history": [r.model_dump() for r in body.conversation_history],
        "attachments": body.attachments,
        "status": "pending",
        "report": None,
    }
    save_session_disk(session_id, _sessions[session_id])
    logger.info("创建新会话: %s, 用户: %s, 历史轮次: %d, 附件: %d", session_id, body.user_id, len(body.conversation_history), len(body.attachments))
    return CreateSessionResponse(session_id=session_id)



@router.get("/{session_id}/stream")
async def stream_session(session_id: str) -> StreamingResponse:
    """
    SSE 流式接口：连接后自动开始执行 4 个 Agent
    前端使用 EventSource 连接此接口接收实时输出
    """
    if not _ensure_session_loaded(session_id):
        raise HTTPException(status_code=404, detail="会话不存在")

    session = _sessions[session_id]
    user_prompt = session["user_prompt"]
    conversation_history = session.get("conversation_history", [])
    attachments = session.get("attachments", [])

    # NOTE: 加载 checkpoint：已落盘的 agent 输出 + 状态 + 路由顺序
    # Orchestrator 会跳过已完成的 Agent，直接重放存档输出
    checkpoint = {
        "agent_outputs": session.get("agent_outputs", {}),
        "agent_statuses": session.get("agent_statuses", {}),
        "selected_agents": session.get("selected_agents", []),
    }
    # 如果没有任何落盘数据（全新会话），不传 checkpoint
    if not any(checkpoint.values()):
        checkpoint = None

    orchestrator = AgentOrchestrator()


    async def event_generator() -> AsyncGenerator[str, None]:
        import time as _time
        import json as _json
        # NOTE: 在内存中追踪每个 agent 的流式输出缓冲，
        # 这样可以在 agent 完成前就知道已经生成了多少内容
        _chunk_buffers: dict[str, str] = {}
        _last_persist_ts: dict[str, float] = {}
        THROTTLE_SECS = 3.0  # 每个 agent 最多每 3 秒写一次磁盘

        try:
            final_report: str | None = None
            async for event in orchestrator.run_session(user_prompt, conversation_history, checkpoint=checkpoint, attachments=attachments):

                # 拦截 routing_decided：保存本次路由顺序，断点续传时用
                if "event: routing_decided" in event:
                    for line in event.split("\n"):
                        if line.startswith("data: "):
                            try:
                                agents_list = _json.loads(line[6:])
                                if isinstance(agents_list, list):
                                    _sessions[session_id]["selected_agents"] = agents_list
                                    save_session_disk(session_id, _sessions[session_id])
                            except Exception:
                                pass

                # 拦截 agent_chunk：追加到内存缓冲，并节流落盘（防止磁盘 I/O 过频）
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
                                        update_session_agent_output(session_id, aid, _chunk_buffers[aid], status="running")
                                        _last_persist_ts[aid] = now
                            except Exception:
                                pass

                # 拦截 agent_output：agent 完整输出到达，立即最终落盘
                if "event: agent_output" in event:
                    for line in event.split("\n"):
                        if line.startswith("data: "):
                            try:
                                payload = _json.loads(line[6:])
                                aid = payload.get("id", "")
                                content = payload.get("content", "")
                                if aid and content:
                                    # 用 agent_output 覆盖流式缓冲，确保内容最准确
                                    _chunk_buffers[aid] = content
                                    update_session_agent_output(session_id, aid, content, status="completed")
                            except Exception:
                                pass

                r = extract_report_from_sse_chunk(event)
                if r is not None:
                    final_report = r
                yield event
            _sessions[session_id]["status"] = "completed"
            if final_report is not None:
                _sessions[session_id]["report"] = final_report
            save_session_disk(session_id, _sessions[session_id])
        except Exception as e:
            logger.error("会话执行失败: %s, 错误: %s", session_id, e)
            yield f"event: error\ndata: {str(e)}\n\n"
            _sessions[session_id]["status"] = "error"
            save_session_disk(session_id, _sessions[session_id])

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
async def get_report(session_id: str) -> dict:
    """获取已完成会话的报告（用于分享链接只读访问）"""
    if not _ensure_session_loaded(session_id):
        raise HTTPException(status_code=404, detail="会话不存在")
    session = _sessions[session_id]
    if session["status"] != "completed":
        raise HTTPException(status_code=202, detail="报告尚未生成完成")
    return {"session_id": session_id, "report": session.get("report")}


@router.get("/{session_id}/snapshot")
async def get_snapshot(session_id: str) -> dict:
    """
    获取会话的实时快照（无论是否完成）。
    前端刷新后优先调用此接口恢复 UI 状态，而不依赖 localStorage。
    返回：已完成的 agent 输出、各 Agent 状态、用户原始 prompt、session 整体状态。
    """
    # 先从磁盘加载，保证进程重启后依然能读到
    data = load_session_disk(session_id)
    if not data:
        # 再检查内存（万一磁盘还没来得及初始化）
        if session_id not in _sessions:
            raise HTTPException(status_code=404, detail="会话不存在")
        data = _sessions[session_id]

    agent_outputs: dict = data.get("agent_outputs") or {}
    agent_statuses: dict = data.get("agent_statuses") or {}
    report: str | None = data.get("report")

    # NOTE: 兼容旧版会话数据格式：
    # 早期版本只落盘了 report 字段，没有写 agent_outputs / agent_statuses。
    # 为了让旧会话在 Feed 中能正常渲染，把 report 注入到 consultant_review 的输出位置。
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
    }
