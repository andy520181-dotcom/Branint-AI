"""
美术指导 Agent — Scher

工作流（双车道架构）：
  Micro-Task 车道（is_micro_task=True）：
    - 信息充分性评估 → 缺信息则 __AGENT_CLARIFY__ 挂起
    - 信息充分 → 直接以资深美术指导口吻简洁输出视觉结论
  Full-Plan 车道（is_micro_task=False，默认）：
    - 接收 market + strategy + content 的 handoff 交接摘要
    - 制定完整的品牌视觉识别系统方案
"""
from __future__ import annotations

import logging
from collections.abc import AsyncGenerator

from app.config import settings
from app.service.llm_provider import call_llm, call_llm_stream
from app.service.prompt_loader import load_agent_prompt

logger = logging.getLogger(__name__)

# NOTE: orchestrator 捕获此前缀后，emit agent_clarify SSE + session_pause SSE
AGENT_CLARIFY_MARKER = "__AGENT_CLARIFY__:"

# NOTE: 进度标记，与 market_agent 共用相同格式
PROGRESS_MARKER = "\x00WACKSMAN_PROGRESS\x00"


def _make_progress(step: str, label: str = "") -> str:
    """构造进度 token，供 orchestrator 转发为 SSE 事件。"""
    import json
    payload = {"step": step, "label": label, "detail": ""}
    return f"{PROGRESS_MARKER}{json.dumps(payload, ensure_ascii=False)}"


import json

IMAGE_MARKER = "\x00AGENT_IMAGE\x00"
VIDEO_TASK_MARKER = "\x00AGENT_VIDEO_TASK\x00"


async def run_visual_agent_stream(
    user_prompt: str,
    handoff_context: str,
    is_micro_task: bool = False,
) -> AsyncGenerator[str, None]:
    """
    美术指导 Agent (Scher) 流式主循环（Tool-Chain Driven）
    """
    from app.service.skills.scher_skills import (
        SCHER_TOOLS,
        SCHER_EXECUTION_TOOLS,
        execute_clarify_visual_requirement,
        execute_define_color_system,
        execute_define_typography_system,
        execute_synthesize_visual_report,
    )
    from app.service.image_generator import generate_brand_images
    from app.service.video_generator import submit_jimeng_video
    from app.service.llm_provider import call_llm_with_tools

    system_prompt = load_agent_prompt("visual")
    
    context_block = f"\n\n## 上游交接背景\n{handoff_context}\n" if handoff_context else ""
    
    if is_micro_task:
        logger.info("Scher Micro-Task 车道启动")
        yield _make_progress("start", label="Scher 收到单点视觉指令，准备精准作业…")
        micro_directive = (
            "\n\n[执行指令] 本次属于【单点微缩任务 (Micro-Task)】，你作为顶级美术指导 Scher 独立作业。\n"
            "直接调用底层的生图/视频 API 执行请求。绝对禁止输出完整 VIS 报告。"
        )
        task_prompt = f"视觉设计诉求：\n\n{user_prompt}{context_block}{micro_directive}"
        enabled_tools = SCHER_EXECUTION_TOOLS
    else:
        logger.info("Scher Full-Plan 车道启动")
        yield _make_progress("start", label="Scher 启动全案视觉引擎，构建品牌 VIS 体系…")
        full_directive = "\n\n请严格依据工具链执行：定义色彩 -> 定义字体 -> (可选生图生视频) -> 结案汇总。"
        task_prompt = f"品牌诉求：\n\n{user_prompt}{context_block}{full_directive}"
        enabled_tools = SCHER_TOOLS

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": task_prompt},
    ]

    # Tool Execution Loop
    for loop_idx in range(5):
        logger.info("Scher 执行轮次 %d", loop_idx + 1)
        text_content, tool_calls = await call_llm_with_tools(
            messages=messages,
            tools=enabled_tools,
            model=settings.default_model,
        )

        if text_content:
            yield text_content

        messages.append({
            "role": "assistant",
            "content": text_content,
            "tool_calls": tool_calls if tool_calls else None,
        })

        if not tool_calls:
            logger.info("Scher 完毕 (未调用新工具)")
            break

        should_break = False
        for tc in tool_calls:
            func_name = tc.get("function", {}).get("name")
            raw_args = tc.get("function", {}).get("arguments", "{}")
            logger.info("Scher 调用工具: %s", func_name)

            try:
                args = json.loads(raw_args)
            except json.JSONDecodeError:
                args = {}

            tool_result_str = ""

            # ────────────────────────────────────────────────────────
            # 物理层执行拦截 (Image & Video APIs)
            # ────────────────────────────────────────────────────────
            if func_name == "generate_brand_image":
                yield _make_progress(func_name, label="渲染品牌主视觉画面中…")
                image_type = args.get("image_type", "poster")
                prompt = args.get("midjourney_prompt", "")
                aspect_ratio = args.get("aspect_ratio", "16:9")
                
                # Directly execute image generation and await
                images_info = await generate_brand_images(image_type, prompt, aspect_ratio)
                
                if images_info:
                    # Emit OSS URL to LLM tool result to acknowledge success
                    tool_result_str = f"生成成功！文件已上传至: {images_info[0]['data_url']}"
                    # YIELD special marker for orchestrator to push to frontend
                    yield f"{IMAGE_MARKER}{json.dumps(images_info[0])}"
                else:
                    tool_result_str = "图像生成失败，底层API可能发生超时。"

            elif func_name == "generate_concept_video":
                yield _make_progress(func_name, label="发送火山引擎视频生成任务…")
                cinematic_prompt = args.get("cinematic_prompt", "")
                task_id = submit_jimeng_video(cinematic_prompt)
                
                if task_id:
                    tool_result_str = f"任务已提交，Task ID: {task_id}"
                    # Yield task marker for orchestrator to poll in background
                    yield f"{VIDEO_TASK_MARKER}{task_id}"
                else:
                    tool_result_str = "视频任务提交失败"

            # ────────────────────────────────────────────────────────
            # 虚拟定义层拦截 (Text definitions)
            # ────────────────────────────────────────────────────────
            elif func_name == "clarify_visual_requirement":
                yield _make_progress(func_name, label="发现缺失核心品牌指导，发起反问…")
                tool_result_str = execute_clarify_visual_requirement(args)
                should_break = True
            elif func_name == "define_color_system":
                yield _make_progress(func_name, label="配置品牌色彩矩阵与规范…")
                tool_result_str = execute_define_color_system(args)
            elif func_name == "define_typography_system":
                yield _make_progress(func_name, label="定义品牌主次字体与阅读体验…")
                tool_result_str = execute_define_typography_system(args)
            elif func_name == "synthesize_visual_report":
                yield _make_progress(func_name, label="渲染视觉系统识别总结规范…")
                tool_result_str = execute_synthesize_visual_report(args)
                should_break = True
            else:
                tool_result_str = "未知的工具指令"

            messages.append({
                "role": "tool",
                "tool_call_id": tc.get("id", "unknown"),
                "name": func_name,
                "content": tool_result_str,
            })

            # 如果触发了挂起信号 (如 clarify 或 report ready)，立刻返回前端解析
            if tool_result_str.startswith("__CLARIFY_REQUIRED__:"):
                q = tool_result_str.split(":", 1)[1]
                yield f"{AGENT_CLARIFY_MARKER}{q}"
                return

        if should_break:
            break

    logger.info("Scher 流程完成")

async def run_visual_agent(user_prompt: str, handoff_context: str) -> str:
    # 纯备用的同步代理口，实际不使用
    return "Scher 必须使用流式系统开启工具链。"
