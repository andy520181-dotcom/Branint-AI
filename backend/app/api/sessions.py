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
        "status": "pending",
        "report": None,
    }
    save_session_disk(session_id, _sessions[session_id])
    logger.info("创建新会话: %s, 用户: %s, 历史轮次: %d", session_id, body.user_id, len(body.conversation_history))
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

    orchestrator = AgentOrchestrator()

    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            final_report: str | None = None
            async for event in orchestrator.run_session(user_prompt, conversation_history):
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
