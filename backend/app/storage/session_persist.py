"""会话 JSON 落盘，供分享链接在进程重启后仍能拉取报告。"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

SESSIONS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "sessions"
_SESSION_ID_RE = re.compile(r"^[0-9a-fA-F-]{8,}$")


def _safe_session_path(session_id: str) -> Path | None:
    if not session_id or not _SESSION_ID_RE.match(session_id):
        return None
    if ".." in session_id or "/" in session_id or "\\" in session_id:
        return None
    return SESSIONS_DIR / f"{session_id}.json"


def ensure_sessions_dir() -> None:
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)


def save_session_disk(session_id: str, data: dict) -> None:
    path = _safe_session_path(session_id)
    if not path:
        return
    try:
        ensure_sessions_dir()
        tmp = path.with_suffix(".json.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        tmp.replace(path)
    except OSError as e:
        logger.warning("会话落盘失败 %s: %s", session_id, e)


def load_session_disk(session_id: str) -> dict | None:
    path = _safe_session_path(session_id)
    if not path or not path.is_file():
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("读取会话文件失败 %s: %s", session_id, e)
        return None


def extract_report_from_sse_chunk(chunk: str) -> str | None:
    """从 orchestrator 产出的 SSE 片段中解析 session_complete 的 report 字段。"""
    if "event: session_complete" not in chunk:
        return None
    for line in chunk.split("\n"):
        if line.startswith("data: "):
            raw = line[6:]
            try:
                payload = json.loads(raw)
                if isinstance(payload, dict):
                    r = payload.get("report")
                    return r if isinstance(r, str) else None
            except json.JSONDecodeError:
                return None
    return None
