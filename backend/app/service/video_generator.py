"""
品牌概念视频生成服务（支持即梦 Jimeng + Kling AI 双引擎）

引擎优先级：
  1. Kling AI（快手可图）     → 需配置 KLING_API_KEY
  2. 即梦（火山引擎）         → 需配置 VOLC_ACCESSKEY / VOLC_SECRETKEY（已有）

两个 API 均采用：提交任务 → 异步轮询 → 返回视频 URL 的模式。
"""
from __future__ import annotations

import asyncio
import logging
import os

import httpx

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  引擎 1：Kling AI（快手可图）
# ═══════════════════════════════════════════════════════════════

KLING_BASE_URL = "https://api.klingai.com"
KLING_POLL_INTERVAL = 6   # 秒
KLING_MAX_WAIT = 180       # 秒


def _kling_headers() -> dict[str, str]:
    api_key = os.getenv("KLING_API_KEY", "")
    if not api_key:
        raise RuntimeError("KLING_API_KEY 未设置")
    return {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}


async def _generate_video_kling(
    cinematic_prompt: str,
    aspect_ratio: str = "16:9",
    duration: int = 5,
) -> dict | None:
    """
    Kling AI 文生视频：提交 → 轮询 → 返回结果 dict。

    Args:
        cinematic_prompt: 英文运镜提示词
        aspect_ratio:     "16:9" | "9:16" | "1:1"
        duration:         5 或 10（秒）

    Returns:
        {'type': 'video', 'mime': 'video/mp4', 'data_url': OSS_URL}
        失败返回 None
    """
    headers = _kling_headers()
    payload = {
        "model_name": "kling-v1",
        "prompt": cinematic_prompt,
        "duration": str(duration),
        "aspect_ratio": aspect_ratio,
        "cfg_scale": 0.5,
        "mode": "std",
    }

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            resp = await client.post(
                f"{KLING_BASE_URL}/v1/videos/text2video",
                headers=headers,
                json=payload,
            )
            resp.raise_for_status()
            task_id = resp.json().get("data", {}).get("task_id", "")
        except Exception as e:
            logger.error("Kling AI 提交视频任务失败: %s", e)
            return None

    if not task_id:
        logger.error("Kling AI 未返回 task_id")
        return None

    logger.info("Kling AI 任务已提交，task_id=%s，开始轮询…", task_id)
    elapsed = 0

    async with httpx.AsyncClient(timeout=30) as client:
        while elapsed < KLING_MAX_WAIT:
            await asyncio.sleep(KLING_POLL_INTERVAL)
            elapsed += KLING_POLL_INTERVAL

            try:
                poll = await client.get(
                    f"{KLING_BASE_URL}/v1/videos/text2video/{task_id}",
                    headers=headers,
                )
                poll.raise_for_status()
                data = poll.json().get("data", {})
            except Exception as e:
                logger.warning("轮询 Kling 状态失败(%ds): %s", elapsed, e)
                continue

            status = data.get("task_status", "")
            logger.debug("Kling %s → %s (%ds)", task_id, status, elapsed)

            if status == "succeed":
                video_url = (
                    data.get("task_result", {}).get("videos", [{}])[0].get("url", "")
                )
                if not video_url:
                    logger.error("Kling 任务成功但无 URL，data=%s", data)
                    return None
                return await _upload_or_forward(video_url)

            if status in ("failed", "error"):
                logger.error("Kling 任务失败: %s", data.get("task_status_msg", ""))
                return None

    logger.error("Kling 视频任务超时 (>%ds)", KLING_MAX_WAIT)
    return None


# ═══════════════════════════════════════════════════════════════
#  引擎 2：即梦（火山引擎）—— 沿用原有逻辑，重构接口保持一致
# ═══════════════════════════════════════════════════════════════

VIDEO_REQ_KEY = "jimeng_t2v_v30_1080p"
JIMENG_POLL_INTERVAL = 8
JIMENG_MAX_WAIT = 600


async def _generate_video_jimeng(cinematic_prompt: str) -> dict | None:
    """
    即梦（火山引擎）文生视频：适配原有 VisualService SDK。
    """
    import time
    try:
        from volcengine.visual.VisualService import VisualService
    except ImportError:
        logger.error("volcengine SDK 未安装，无法调用即梦 API")
        return None

    def _submit() -> str:
        svc = VisualService()
        svc.set_ak(os.getenv("VOLC_ACCESSKEY", ""))
        svc.set_sk(os.getenv("VOLC_SECRETKEY", ""))
        body = {"req_key": VIDEO_REQ_KEY, "prompt": cinematic_prompt, "seed": -1,
                "frames": 121, "aspect_ratio": "16:9"}
        try:
            resp = svc.cv_sync2async_submit_task(body)
            import json
            if isinstance(resp, bytes):
                resp = json.loads(resp)
            if resp.get("code") != 10000:
                logger.error("即梦提交失败: %s", resp)
                return ""
            return resp.get("data", {}).get("task_id", "")
        except Exception as e:
            logger.error("即梦提交异常: %s", e)
            return ""

    task_id = await asyncio.to_thread(_submit)
    if not task_id:
        return None

    logger.info("即梦任务已提交，task_id=%s", task_id)

    def _poll() -> str:
        svc = VisualService()
        svc.set_ak(os.getenv("VOLC_ACCESSKEY", ""))
        svc.set_sk(os.getenv("VOLC_SECRETKEY", ""))
        start = time.time()
        while time.time() - start < JIMENG_MAX_WAIT:
            import json, time as _t
            _t.sleep(JIMENG_POLL_INTERVAL)
            try:
                resp = svc.cv_sync2async_get_result({"req_key": VIDEO_REQ_KEY, "task_id": task_id})
                if isinstance(resp, bytes):
                    resp = json.loads(resp)
                data = resp.get("data", {}) or {}
                status = data.get("status", "")
                if status == "done":
                    return (data.get("video_url") or data.get("url")
                            or (data.get("videos") or [{}])[0].get("url", ""))
                if status in ("failed", "error"):
                    logger.error("即梦任务失败: %s", data)
                    return ""
            except Exception as e:
                logger.warning("轮询即梦状态异常: %s", e)
        logger.error("即梦任务超时")
        return ""

    video_url = await asyncio.to_thread(_poll)
    if not video_url:
        return None
    return await _upload_or_forward(video_url)


# ═══════════════════════════════════════════════════════════════
#  公共辅助：下载→上传 OSS，失败则直接用原 URL
# ═══════════════════════════════════════════════════════════════

async def _upload_or_forward(video_url: str) -> dict:
    """下载视频→上传阿里云 OSS；失败时直接返回原 URL（给前端用临时链接）。"""
    from app.storage.oss_service import upload_file
    try:
        async with httpx.AsyncClient(timeout=60) as dl:
            r = await dl.get(video_url)
            r.raise_for_status()
            video_bytes = r.content

        oss_url = await upload_file(
            content=video_bytes,
            original_name="brand_concept_video.mp4",
            content_type="video/mp4",
        )
        logger.info("视频已上传 OSS，大小=%d bytes", len(video_bytes))
        return {"type": "video", "mime": "video/mp4", "data_url": oss_url}
    except Exception as e:
        logger.warning("OSS 上传失败，使用原始 URL: %s", e)
        return {"type": "video", "mime": "video/mp4", "data_url": video_url}


# ═══════════════════════════════════════════════════════════════
#  统一对外接口
# ═══════════════════════════════════════════════════════════════

async def generate_brand_video(
    cinematic_prompt: str,
    aspect_ratio: str = "16:9",
    duration: int = 5,
) -> dict | None:
    """
    统一视频生成接口：优先 Kling AI，若未配置密钥则回落到即梦。

    Args:
        cinematic_prompt: 英文运镜描述
        aspect_ratio:     比例，"16:9" / "9:16" / "1:1"
        duration:         时长（秒），Kling 支持 5/10

    Returns:
        {'type': 'video', 'mime': 'video/mp4', 'data_url': '...'} 或 None
    """
    if os.getenv("KLING_API_KEY"):
        logger.info("使用 Kling AI 引擎生成品牌视频…")
        return await _generate_video_kling(cinematic_prompt, aspect_ratio, duration)

    if os.getenv("VOLC_ACCESSKEY") and os.getenv("VOLC_SECRETKEY"):
        logger.info("使用即梦（火山引擎）引擎生成品牌视频…")
        return await _generate_video_jimeng(cinematic_prompt)

    logger.error("未配置任何视频 API 密钥（KLING_API_KEY 或 VOLC_ACCESSKEY），跳过视频生成")
    return None


# NOTE: 保持向后兼容——原来 orchestrator 中可能有调用此名称
async def generate_brand_video_async(cinematic_prompt: str) -> list[dict]:
    result = await generate_brand_video(cinematic_prompt)
    return [result] if result else []
