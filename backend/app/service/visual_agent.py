"""
美术指导 Agent — Scher

工作流（原生真流式 三车道架构）：
  - 预调度路线（静默）：解析用户意图，如果需要反问则打回；如果需要出图出视频，则抓取 prompt。
  - 物理媒体路线（异步）：将大模型拆解出的生图/生视频任务抛入后台异步并发。
  - 纯文本路线（流式）：彻底摆脱工具链束缚，直接调用原生流式接口生成充满色彩、排版、字体的视觉指导规范。
"""
from __future__ import annotations

import logging
import json
import asyncio
from typing import Any
from collections.abc import AsyncGenerator

from app.config import settings
from app.service.llm_provider import call_llm_with_tools, call_llm_stream
from app.service.prompt_loader import load_agent_prompt
from app.service.skills.scher_skills import execute_clarify_visual_requirement

logger = logging.getLogger(__name__)

AGENT_CLARIFY_MARKER = "__AGENT_CLARIFY__:"
PROGRESS_MARKER = "\x00WACKSMAN_PROGRESS\x00"
IMAGE_MARKER = "\x00AGENT_IMAGE\x00"
VIDEO_TASK_MARKER = "\x00AGENT_VIDEO_TASK\x00"

def _make_progress(step: str, label: str = "") -> str:
    payload = {"step": step, "label": label, "detail": ""}
    return f"{PROGRESS_MARKER}{json.dumps(payload, ensure_ascii=False)}"

async def _worker_generate_image(queue: asyncio.Queue, task_def: dict[str, Any]):
    """独立车道：生成图片"""
    try:
        from app.service.image_generator import generate_brand_images
        image_type = task_def.get("image_type", "poster")
        prompt = task_def.get("midjourney_prompt", "")
        aspect_ratio = task_def.get("aspect_ratio", "16:9")
        
        images_info = await generate_brand_images(image_type, prompt, aspect_ratio)
        if images_info:
            await queue.put(f"{IMAGE_MARKER}{json.dumps(images_info[0])}")
    except Exception as e:
        logger.error("图片引擎生成失败: %s", e)
    finally:
        await queue.put({"type": "worker_done", "lane": "image"})

async def _worker_generate_video(queue: asyncio.Queue, task_def: dict[str, Any]):
    """独立车道：生成视频"""
    try:
        from app.service.video_generator import submit_jimeng_video
        prompt = task_def.get("cinematic_prompt", "")
        task_id = submit_jimeng_video(prompt)
        if task_id:
            await queue.put(f"{VIDEO_TASK_MARKER}{task_id}")
    except Exception as e:
        logger.error("视频引擎生成失败: %s", e)
    finally:
        await queue.put({"type": "worker_done", "lane": "video"})

async def run_visual_agent_stream(
    user_prompt: str,
    handoff_context: str,
    is_micro_task: bool = False,
) -> AsyncGenerator[str, None]:
    system_prompt = load_agent_prompt("visual")
    context_block = f"\n\n## 上游交接背景\n{handoff_context}\n" if handoff_context else ""
    
    # 【车道 1：静默预调度判别】
    yield _make_progress("start", label="Scher 拉取视觉交接档案，构思全局方案…")

    dispatch_tool = {
        "type": "function",
        "function": {
            "name": "dispatch_visual_intent",
            "description": "评估当前的视觉需求，决定是否需要生成图片、生成视频或发起反问。你只能从背景档案中提取生成所需的prompt！如果无需生成，则让tasks为空数组。",
            "parameters": {
                "type": "object",
                "properties": {
                    "need_clarify": {"type": "boolean", "description": "如果缺少极度关键的品牌调性导致完全无法作业，设为true"},
                    "clarify_question": {"type": "string", "description": "需要向用户抛出的核心反问问题"},
                    "image_tasks": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "image_type": {"type": "string", "enum": ["logo", "banner", "poster"]},
                                "midjourney_prompt": {"type": "string", "description": "全英文，不要夹带任何汉字。包含极致细节、灯光、材质。"},
                                "aspect_ratio": {"type": "string", "enum": ["1:1", "16:9", "9:16", "4:3"]}
                            },
                        }
                    },
                    "video_tasks": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "cinematic_prompt": {"type": "string", "description": "全英文视频运镜提示词，极致描述动态过程。"}
                            },
                        }
                    }
                },
                "required": ["need_clarify", "image_tasks", "video_tasks"]
            }
        }
    }

    preflight_messages = [
        {"role": "system", "content": system_prompt + "\n\n【隐秘提示】：你当前处于底层前置意图探测阶段，请务必只调用 dispatch_visual_intent 工具。绝对不要直接用文字回答。"},
        {"role": "user", "content": f"用户执行诉求：\n{user_prompt}{context_block}"}
    ]

    _, tool_calls = await call_llm_with_tools(
        messages=preflight_messages,
        tools=[dispatch_tool],
        tool_choice={"type": "function", "function": {"name": "dispatch_visual_intent"}},
        model=settings.default_model,
    )

    args = {}
    if tool_calls:
        try:
            args = json.loads(tool_calls[0]["function"]["arguments"])
        except Exception:
            pass

    if args.get("need_clarify") and args.get("clarify_question"):
        yield f"{AGENT_CLARIFY_MARKER}{args['clarify_question']}"
        return

    # 【车道 2：物理媒体异步执行】
    queue = asyncio.Queue()
    active_workers = 0

    image_tasks = args.get("image_tasks", [])
    video_tasks = args.get("video_tasks", [])
    
    # 若 MicroTask 请求图像且未抽取到，主动加上保底兜底，防止 preflight 失效
    if is_micro_task and (not image_tasks and not video_tasks):
        image_tasks = [{"image_type": "poster", "midjourney_prompt": "Minimalist modern branding design, high quality", "aspect_ratio": "16:9"}]

    if image_tasks:
        yield _make_progress("generating", label="Scher 派发云端节点进行图像渲染…")
        for img in image_tasks:
            asyncio.create_task(_worker_generate_image(queue, img))
            active_workers += 1

    if video_tasks:
        yield _make_progress("generating", label="Scher 将运镜推流发射至视频矩阵…")
        for vid in video_tasks:
            asyncio.create_task(_worker_generate_video(queue, vid))
            active_workers += 1

    # 【车道 3：纯净流式主文案生成】
    yield _make_progress("typing", label="Scher 正在亲笔书写全案视觉准则…")

    if is_micro_task:
        sys_directive = "你处于单兵作战模式，直接用富有魅力的资深的美术指导口吻输出，不用写 Markdown 全案长文，只写几十个字的寄语即可。"
    else:
        sys_directive = "请你作为顶尖美术指导，基于交接文档，用极其优雅专业的文字，直接输出关于该品牌的色彩定义、排版和视觉总结。请保持真人的流式诉说节奏，绝不能显得像一个机器人在汇报。不要提及图片/视频已经生成了，只要专注视觉概念设计。"

    stream_messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"{context_block}\n\n请求：{user_prompt}\n\n【核心约束】{sys_directive}"}
    ]

    llm_generator = call_llm_stream(stream_messages, model=settings.default_model)

    async def _consume_llm(q: asyncio.Queue):
        try:
            async for chunk in llm_generator:
                await q.put({"type": "chunk", "data": chunk})
        except Exception as e:
            logger.error("Scher 文本流生成异常: %s", e)
        finally:
            await q.put({"type": "llm_done"})

    asyncio.create_task(_consume_llm(queue))

    llm_active = True
    while llm_active or active_workers > 0:
        msg = await queue.get()
        if isinstance(msg, dict):
            if msg["type"] == "chunk":
                yield msg["data"]
            elif msg["type"] == "llm_done":
                llm_active = False
            elif msg["type"] == "worker_done":
                active_workers -= 1
        elif isinstance(msg, str):
            yield msg

    logger.info("Scher 完全体三车道并行宣告圆满收官！")

async def run_visual_agent(user_prompt: str, handoff_context: str) -> str:
    return "Scher 三车道系统必须使用流式调用。"
