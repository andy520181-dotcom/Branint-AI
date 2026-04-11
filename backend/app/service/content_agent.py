"""
内容策划 Agent — Lois

工作流（双车道架构）：
  Micro-Task 车道（is_micro_task=True）：
    - 信息充分性评估 → 缺信息则 __AGENT_CLARIFY__ 挂起
    - 信息充分 → 直接以资深内容策划师口吻简洁输出结论
  Full-Plan 车道（is_micro_task=False，默认）：
    - 接收 market + strategy handoff 交接摘要
    - 制定全面的品牌内容策划方案
"""
from __future__ import annotations

import logging
from collections.abc import AsyncGenerator

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


async def run_content_agent(
    user_prompt: str,
    handoff_context: str,
) -> str:
    """
    内容策划 Agent（非流式）
    接收 market + strategy 的 handoff 交接摘要
    """
    user_content = f"品牌需求：\n{user_prompt}"
    if handoff_context:
        user_content += f"\n\n{handoff_context}"
    user_content += "\n\n请基于以上交接信息，制定全面的品牌内容策划方案。"

    messages = [
        {"role": "system", "content": load_agent_prompt("content")},
        {"role": "user", "content": user_content},
    ]
    return await call_llm(messages)


async def run_content_agent_stream(
    user_prompt: str,
    handoff_context: str,
    is_micro_task: bool = False,
) -> AsyncGenerator[str, None]:
    """
    内容策划 Agent（流式）

    is_micro_task=False: 全流程深度内容策划（默认）
    is_micro_task=True:  单点微缩任务车道，支持自适应追问 + 简洁输出
    """
    # ─── Micro-Task 车道 ───────────────────────────────────────
    if is_micro_task:
        logger.info("Lois Micro-Task 车道启动")
        yield _make_progress("start", label="Lois 收到单点内容指令，准备精准作业…")

        system_prompt = load_agent_prompt("content")
        context_block = f"\n\n## 上游交接背景\n{handoff_context}\n" if handoff_context else ""

        micro_directive = (
            "\n\n[执行指令] 本次属于【单点微缩任务 (Micro-Task)】，你作为资深内容策划师 Lois 独立作业。\n\n"
            "## 信息充分性原则（最优先）\n"
            "在输出任何内容之前，请先评估用户的诉求是否包含完成任务所必需的关键信息。\n"
            "如果缺少关键信息（例如：品牌调性/目标人群/核心卖点/渠道平台/内容目标等），\n"
            "你必须以 `__AGENT_CLARIFY__:` 作为回复的第一字符，紧跟一段简洁的追问文字，然后立刻停止。\n"
            "不要在追问之后继续输出任何内容！\n\n"
            "## 输出原则\n"
            "如果信息充分，请直接以资深内容策划师的口吻（简练、有创意、直击痛点），\n"
            "针对用户诉求给出具体可执行的内容策划结论或方案。\n"
            "绝对禁止：输出完整的内容策划长报告 / 走全案策划路径。"
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"内容策划诉求：\n\n{user_prompt}{context_block}{micro_directive}"},
        ]

        # NOTE: 采用非工具 LLM 调用，Lois 无独立工具箱，依赖 LLM 自身创意能力
        full_response = ""
        async for chunk in call_llm_stream(messages):
            full_response += chunk
            yield chunk

        # 检测是否触发追问信号（由于是流式，直接 yield 即可，orchestrator 会识别）
        logger.info(
            "Lois Micro-Task 完成，是否追问: %s",
            full_response.startswith(AGENT_CLARIFY_MARKER)
        )
        return

    # ─── Full-Plan 车道（全流程内容策划）────────────────────────
    logger.info("Lois Full-Plan 车道启动")
    yield _make_progress("start", label="Lois 启动全案内容策划引擎，构建内容矩阵…")

    user_content = f"品牌需求：\n{user_prompt}"
    if handoff_context:
        user_content += f"\n\n{handoff_context}"
    user_content += "\n\n请基于以上交接信息，制定全面的品牌内容策划方案。"

    messages = [
        {"role": "system", "content": load_agent_prompt("content")},
        {"role": "user", "content": user_content},
    ]
    async for chunk in call_llm_stream(messages):
        yield chunk
