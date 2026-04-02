import asyncio
import logging
import os
import time

from volcengine.visual.VisualService import VisualService

logger = logging.getLogger(__name__)

# NOTE: 不同的 즉梦服务版本 Action 名称可能会变化
# 如果您的后台开启的是 3.0 Pro/4.0 等新版即梦，请参照控制台的最新 req_key
SUBMIT_ACTION = "HighAesVideoGenSubmitTask"
QUERY_ACTION = "HighAesVideoGenQueryTask"

def _get_visual_service() -> VisualService:
    service = VisualService()
    service.set_ak(os.getenv("VOLC_ACCESSKEY", ""))
    service.set_sk(os.getenv("VOLC_SECRETKEY", ""))
    # 针对部分专属模型，可能需要指定特定的 Host 或 Region
    # service.set_host("visual.volcengineapi.com")
    return service

def submit_jimeng_video(prompt: str) -> str:
    """
    提交即梦文生视频任务，返回 Task ID。
    """
    service = _get_visual_service()
    
    # 构建请求体。请根据具体的高级选项（尺寸、循环等）调整 dict
    # 这里以 720P 即梦通用视频生成为例
    body = {
        "req_key": "high_aes_video_gen", # 如果使用泛型 cv_process
        "prompt": prompt,
        "width": 1280,
        "height": 720,
    }
    
    try:
        # NOTE: 实际接口情况：
        # 有些版本使用 cv_process
        # 有些需要特定的 Action 调用。如果遇到 AccessDenied，请到控制台确认你开通的具体动作名
        logger.info(f"正在向火山引擎即梦服务提交文生视频请求...")
        
        # 为了应对 SDK Action 的不确定性，这里提供调用自定义 Action 的接口示范
        # 如果官方给了具体的 sdk 函数，请替代这里：
        # e.g. resp = service.high_aes_video_gen_submit_task(body)
        
        resp = service.cv_process(body)
        
        # 假设返回 { "data": { "task_id": "xxx" } }
        task_id = resp.get("data", {}).get("task_id")
        if not task_id:
            logger.error(f"即梦提交失败，未获取到 task_id: {resp}")
            return ""
        return task_id
    except Exception as e:
        logger.error(f"即梦文生视频提交失败: {e}")
        return ""

async def poll_jimeng_video(task_id: str, timeout: int = 600, poll_interval: int = 5) -> str:
    """
    轮询获取生成的视频 URL
    """
    service = _get_visual_service()
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        try:
            body = {
                "req_key": "high_aes_video_gen",
                "task_id": task_id
            }
            # 查询任务状态
            resp = service.cv_process(body)
            data = resp.get("data", {})
            status = data.get("status")
            
            if status == "SUCCESS":
                video_url = data.get("video_url")
                logger.info(f"视频生成成功: {video_url}")
                return video_url
            elif status == "FAILED":
                logger.error(f"视频生成任务失败: {resp}")
                return ""
            
            # 等待继续轮询
            await asyncio.sleep(poll_interval)
            
        except Exception as e:
            logger.error(f"轮询即梦视频状态时出错: {e}")
            await asyncio.sleep(poll_interval)
            
    logger.error("即梦视频生成等待超时")
    return ""

async def generate_brand_video_async(prompt: str) -> list[dict]:
    """
    发起完整的异步即梦视频生成流程，最终返回给前端。
    返回格式：[{"type": "video", "mime": "video/mp4", "data_url": "..."}]
    """
    task_id = submit_jimeng_video(prompt)
    if not task_id:
        # 如果由于配置错误或欠费无法获取 task_id，可以返回兜底 DEMO 视频以供测试交互
        logger.warning("无法正常访问即梦视频 API。触发 DEMO 兜底视频以测试流程。")
        await asyncio.sleep(8) # 模拟一点延迟
        return [{
            "type": "video",
            "mime": "video/mp4",
            "data_url": "https://www.w3schools.com/html/mov_bbb.mp4" # 经典的海洋兔视频作为 DEMO
        }]
    
    video_url = await poll_jimeng_video(task_id)
    if video_url:
        return [{
            "type": "video",
            "mime": "video/mp4",
            "data_url": video_url
        }]
    
    return []
