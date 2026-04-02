import asyncio
import logging
import os
import time

from volcengine.visual.VisualService import VisualService

logger = logging.getLogger(__name__)

# NOTE: 即梦视频生成 req_key，不同服务版本可能不同
# 如遇 AccessDenied，请到火山引擎控制台确认已开通的服务对应的 req_key
VIDEO_REQ_KEY = "high_aes_video_gen"


def _get_visual_service() -> VisualService:
    """获取火山引擎视觉服务客户端（懒加载）"""
    service = VisualService()
    service.set_ak(os.getenv("VOLC_ACCESSKEY", ""))
    service.set_sk(os.getenv("VOLC_SECRETKEY", ""))
    return service


def submit_jimeng_video(prompt: str) -> str:
    """
    向即梦服务提交文生视频任务，返回 Task ID。
    失败时返回空字符串。
    """
    service = _get_visual_service()
    body = {
        "req_key": VIDEO_REQ_KEY,
        "prompt": prompt,
        "width": 1280,
        "height": 720,
    }
    try:
        logger.info("正在向火山引擎即梦服务提交文生视频请求...")
        resp = service.cv_process(body)
        task_id = resp.get("data", {}).get("task_id")
        if not task_id:
            logger.error("即梦提交失败，未获取到 task_id: %s", resp)
            return ""
        logger.info("即梦视频任务已提交，task_id: %s", task_id)
        return task_id
    except Exception as e:
        logger.error("即梦文生视频提交失败: %s", e)
        return ""


async def poll_jimeng_video(task_id: str, timeout: int = 600, poll_interval: int = 5) -> str:
    """
    轮询获取即梦视频生成结果，返回视频 URL。
    超时或失败时返回空字符串。
    """
    service = _get_visual_service()
    start_time = time.time()

    while time.time() - start_time < timeout:
        try:
            body = {"req_key": VIDEO_REQ_KEY, "task_id": task_id}
            resp = service.cv_process(body)
            data = resp.get("data", {})
            status = data.get("status")

            if status == "SUCCESS":
                video_url = data.get("video_url", "")
                logger.info("视频生成成功: %s", video_url)
                return video_url
            elif status == "FAILED":
                logger.error("视频生成任务失败: %s", resp)
                return ""

            await asyncio.sleep(poll_interval)

        except Exception as e:
            logger.error("轮询即梦视频状态时出错: %s", e)
            await asyncio.sleep(poll_interval)

    logger.error("即梦视频生成等待超时（task_id: %s）", task_id)
    return ""


async def generate_brand_video_async(visual_output: str) -> list[dict]:
    """
    发起完整的即梦文生视频流程，返回可供 SSE 推送的视频结果列表。

    返回格式：[{"type": "video", "mime": "video/mp4", "data_url": "https://..."}]
    如果生成失败，返回空列表，不做任何兜底。
    """
    task_id = submit_jimeng_video(visual_output[:500])  # 截取前500字作为分镜描述
    if not task_id:
        # NOTE: 无法提交任务时静默失败，前端不显示视频区域
        logger.warning("即梦视频 API 不可用（权限未开通或账号余额不足），跳过视频生成。")
        return []

    video_url = await poll_jimeng_video(task_id)
    if not video_url:
        return []

    return [{
        "type": "video",
        "mime": "video/mp4",
        "data_url": video_url,
    }]
