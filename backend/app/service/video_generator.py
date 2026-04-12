"""
即梦文生视频服务（Jimeng Text-to-Video 3.0 1080P）

使用火山引擎即梦 3.0 1080P 视频生成模型，通过异步任务轮询获取视频 URL。

接口文档：https://www.volcengine.com/docs/85621/1792711
Action: CVSync2AsyncSubmitTask（提交）/ CVSync2AsyncGetResult（查询）
"""
import asyncio
import logging
import os
import time

from volcengine.visual.VisualService import VisualService

logger = logging.getLogger(__name__)

# 即梦视频生成 3.0 1080P（纯文生视频，控制台已开通）
VIDEO_REQ_KEY = "jimeng_t2v_v30_1080p"


def _get_visual_service() -> VisualService:
    """获取火山引擎视觉服务客户端（懒加载）"""
    service = VisualService()
    service.set_ak(os.getenv("VOLC_ACCESSKEY", ""))
    service.set_sk(os.getenv("VOLC_SECRETKEY", ""))
    return service


def submit_jimeng_video(prompt: str) -> str:
    """
    向即梦服务提交文生视频任务，返回 Task ID。
    使用 CVSync2AsyncSubmitTask 接口（异步提交）。
    失败时返回空字符串。
    """
    service = _get_visual_service()
    body = {
        "req_key": VIDEO_REQ_KEY,
        "prompt": prompt,
        "seed": -1,
        "frames": 121,        # 约 5 秒（24fps）
        "aspect_ratio": "16:9",
    }
    try:
        logger.info("正在向即梦服务提交文生视频任务...")
        resp = service.cv_sync2async_submit_task(body)

        # 响应格式：{"code": 10000, "data": {"task_id": "xxx"}, ...}
        if isinstance(resp, dict):
            if resp.get("code") != 10000:
                logger.error("即梦提交失败，响应: %s", resp)
                return ""
            task_id = resp.get("data", {}).get("task_id", "")
        else:
            import json
            parsed = json.loads(resp)
            if parsed.get("code") != 10000:
                logger.error("即梦提交失败，响应: %s", parsed)
                return ""
            task_id = parsed.get("data", {}).get("task_id", "")

        if not task_id:
            logger.error("即梦提交成功但未返回 task_id，响应: %s", resp)
            return ""

        logger.info("即梦视频任务已提交，task_id: %s", task_id)
        return task_id
    except Exception as e:
        logger.error("即梦文生视频提交失败: %s", e)
        return ""


async def poll_jimeng_video(task_id: str, timeout: int = 600, poll_interval: int = 8) -> str:
    """
    轮询获取即梦视频生成结果，返回视频 URL。
    使用 CVSync2AsyncGetResult 接口。
    超时或失败时返回空字符串。
    """
    service = _get_visual_service()
    start_time = time.time()

    while time.time() - start_time < timeout:
        try:
            body = {"req_key": VIDEO_REQ_KEY, "task_id": task_id}
            resp = service.cv_sync2async_get_result(body)

            if isinstance(resp, bytes):
                import json
                resp = json.loads(resp)

            code = resp.get("code")
            data = resp.get("data", {}) or {}
            status = data.get("status")

            logger.info("轮询状态 [task_id=%s] code=%s status=%s", task_id, code, status)

            # 成功：status == "done" 且有 video_url
            if status == "done":
                # 不同版本返回字段可能不同
                video_url = (
                    data.get("video_url")
                    or data.get("url")
                    or (data.get("videos") or [{}])[0].get("url", "")
                )
                if video_url:
                    logger.info("即梦视频生成成功: %s", video_url)
                    return video_url
                # status done 但没有 url，任务异常
                logger.error("即梦任务 done 但未返回视频 URL，data: %s", data)
                return ""

            # 失败状态
            if status in ("failed", "error"):
                logger.error("即梦视频生成任务失败，data: %s", data)
                return ""

            # 还在生成中，等待后重试
            await asyncio.sleep(poll_interval)

        except Exception as e:
            logger.error("轮询即梦视频状态时出错: %s", e)
            await asyncio.sleep(poll_interval)

    logger.error("即梦视频生成等待超时（task_id: %s）", task_id)
    return ""


async def generate_brand_video_async(cinematic_prompt: str) -> list[dict]:
    """
    发起完整的即梦文生视频流程，返回可供 SSE 推送的视频结果列表。

    返回格式：[{"type": "video", "mime": "video/mp4", "data_url": "https://..."}]
    如果生成失败，返回空列表（静默失败，不影响主流程）。
    """
    if not cinematic_prompt:
        logger.warning("即梦视频 Prompt 为空，跳过生成。")
        return []

    task_id = submit_jimeng_video(cinematic_prompt)
    if not task_id:
        logger.warning("即梦视频 API 调用失败，跳过视频生成。")
        return []

    video_url = await poll_jimeng_video(task_id)
    if not video_url:
        return []

    return [{
        "type": "video",
        "mime": "video/mp4",
        "data_url": video_url,
    }]
