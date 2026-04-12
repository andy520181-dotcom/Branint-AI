"""
内容策划 Agent — Lois

三车道工作流架构：
  ① Micro-Task 车道（is_micro_task=True，轻量直接任务）：
     - 纯 LLM 对话直出（写标题 / 建议话题 / 改一句文案等）
     - 依赖 content.md 中的信息充分性指令，缺信息 → AGENT_CLARIFY_MARKER 挂起

  ② Execution 车道（单兵执行任务，is_micro_task=True 但携带重量级诉求）：
     - Tool Calling 第一轮：LLM 判断调用哪个执行工具（短视频/直播/活动/标题）
     - 若信息不足：调用 clarify_content_requirement → 挂起
     - 若信息充分：工具提炼结构化参数 → 第二轮 LLM 流式生成完整内容
     NOTE: Micro-Task 和 Execution 共享同一个 is_micro_task=True 入口，
           由 LLM 的工具调用决策自动分流（调了执行工具 = Execution 车道）

  ③ Full-Plan 车道（is_micro_task=False，全案品牌内容策略）：
     - 接收 market + strategy handoff
     - 多轮工具调用循环：define_brand_voice → draft_brand_story → brainstorm_slogans
       → build_social_matrix → design_kol_koc_strategy → synthesize_content_report
     - 最终流式生成品牌内容策略完整报告
"""
from __future__ import annotations

import json
import logging
from collections.abc import AsyncGenerator

from app.service.llm_provider import call_llm, call_llm_stream, call_llm_with_tools
from app.service.prompt_loader import load_agent_prompt
from app.service.skills.lois_skills import (
    LOIS_EXECUTION_TOOLS,
    LOIS_TOOL_EXECUTORS,
    LOIS_TOOLS,
    dispatch_lois_tool,
)

logger = logging.getLogger(__name__)

# NOTE: orchestrator 捕获此前缀后，emit agent_clarify SSE + session_pause SSE
AGENT_CLARIFY_MARKER = "__AGENT_CLARIFY__:"

# NOTE: lois_skills.py 内部约定的追问信号
_CLARIFY_REQUIRED_PREFIX = "__CLARIFY_REQUIRED__:"

# NOTE: 进度标记格式，与 market_agent 共用相同格式
PROGRESS_MARKER = "\x00WACKSMAN_PROGRESS\x00"

# NOTE: 全案工具调用循环的最大轮次，防止模型失控
_MAX_TOOL_ROUNDS = 8

# NOTE: 触发完整报告生成流的标记
_SYNTHESIZE_TRIGGER = "synthesize_content_report"


def _make_progress(step: str, label: str = "") -> str:
    """构造进度 token，供 orchestrator 转发为 SSE 事件。"""
    payload = {"step": step, "label": label, "detail": ""}
    return f"{PROGRESS_MARKER}{json.dumps(payload, ensure_ascii=False)}"


def _build_lois_system_prompt(handoff_context: str) -> str:
    """
    组装 Lois 的完整 System Prompt：
    Base Prompt + 上游 handoff 注入（仅在有上游数据时附加）
    """
    base = load_agent_prompt("content")
    if handoff_context:
        base += (
            "\n\n---\n"
            "## 上游 Agent 交接背景（由市场研究 Wacksman 和品牌战略 Trout 传递）\n"
            f"{handoff_context}\n"
            "---\n"
            "以上信息已通过前期研究确认，你可以直接作为内容创作的输入，无需重复询问。"
        )
    return base


async def run_content_agent(
    user_prompt: str,
    handoff_context: str,
) -> str:
    """
    内容策划 Agent（非流式）
    用于 orchestrator 同步获取内容输出结果
    """
    messages = [
        {"role": "system", "content": _build_lois_system_prompt(handoff_context)},
        {"role": "user", "content": f"品牌内容策划诉求：\n{user_prompt}\n\n请制定全面的品牌内容策划方案。"},
    ]
    return await call_llm(messages)


async def run_content_agent_stream(
    user_prompt: str,
    handoff_context: str,
    is_micro_task: bool = False,
) -> AsyncGenerator[str, None]:
    """
    内容策划 Agent（流式，三车道架构）

    is_micro_task=True:
      - 先通过 Tool Calling 分流：追问 / 执行工具 / 直接回复
      - 若调用执行工具（短视频/直播/活动/标题）→ Execution 车道，完成追问+创作
      - 若无工具调用 → 轻量 Micro-Task 直接输出

    is_micro_task=False:
      - Full-Plan 全案内容策划，多轮工具循环
    """

    # ─── ② Micro-Task + Execution 车道 ────────────────────────
    if is_micro_task:
        yield _make_progress("start", label="Lois 收到指令，分析任务类型…")

        system_prompt = _build_lois_system_prompt(handoff_context)

        # NOTE: 先用 Tool Calling 让 LLM 决策：
        # - 信息不足 → 调用 clarify_content_requirement
        # - 重量级执行任务 → 调用对应执行工具（短视频/直播/活动/标题）
        # - 轻量任务 → 不调任何工具，直接出文本（micro-task 直接回复）
        decision_messages: list[dict] = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    f"用户诉求：\n\n{user_prompt}\n\n"
                    "[执行指令] 你是资深内容创意总监 Lois，请先评估当前诉求：\n"
                    "1. 如果关键信息严重缺失（产品卖点/目标人群/调性/平台），立刻调用 "
                    "`clarify_content_requirement` 追问，追问后立刻停止，不要继续。\n"
                    "2. 如果诉求是写短视频脚本/直播脚本/活动策划/标题，且信息基本充分，"
                    "则调用对应的执行工具整理参数（`write_short_video_script` / "
                    "`write_live_streaming_script` / `plan_marketing_event` / "
                    "`write_content_titles`），然后等待系统注入后续创作指令。\n"
                    "3. 如果诉求轻量（改一句文案/想3个话题/给点建议），不要调任何工具，"
                    "直接以 Lois 的腔调精准回复即可。"
                ),
            },
        ]

        content, tool_calls = await call_llm_with_tools(
            messages=decision_messages,
            tools=LOIS_EXECUTION_TOOLS,
        )

        # ─── 情况 A：调用了追问工具 ──────────────────────────────
        if tool_calls:
            tool_name = tool_calls[0]["function"]["name"]
            try:
                raw_args = tool_calls[0]["function"].get("arguments", "{}")
                args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
            except json.JSONDecodeError:
                args = {}

            if tool_name == "clarify_content_requirement":
                question = args.get("question", "能告诉我更多业务背景吗？")
                logger.info("Lois Execution 车道：信息不足，追问挂起: %s", question)
                yield f"{AGENT_CLARIFY_MARKER}{question}"
                return

            # ─── 情况 B：调用了执行工具 ─────────────────────────────
            tool_result = dispatch_lois_tool(tool_name, args)

            # NOTE: 执行工具也可能追问（lois_skills 内部约定的 __CLARIFY_REQUIRED__ 标记）
            if tool_result.startswith(_CLARIFY_REQUIRED_PREFIX):
                question = tool_result[len(_CLARIFY_REQUIRED_PREFIX):]
                logger.info("Lois 执行工具追问挂起: %s", question)
                yield f"{AGENT_CLARIFY_MARKER}{question}"
                return

            # 工具参数已结构化确认，进入第二轮：让 LLM 根据参数简报创作完整内容
            action_labels = {
                "write_short_video_script": "撰写短视频脚本",
                "write_live_streaming_script": "创作直播脚本",
                "plan_marketing_event": "制定活动策划案",
                "write_content_titles": "批量生成爆款标题",
            }
            yield _make_progress(tool_name, label=f"Lois 正在{action_labels.get(tool_name, '执行创作任务')}…")

            creation_messages: list[dict] = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"用户诉求：\n\n{user_prompt}"},
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": tool_calls[0].get("id", "tc_001"),
                            "type": "function",
                            "function": {
                                "name": tool_name,
                                "arguments": tool_calls[0]["function"].get("arguments", "{}"),
                            },
                        }
                    ],
                },
                {
                    "role": "tool",
                    "tool_call_id": tool_calls[0].get("id", "tc_001"),
                    "content": tool_result,
                },
                {
                    "role": "user",
                    "content": (
                        "参数已整理完毕，请以 Lois 的口吻和专业水准，"
                        "基于以上参数简报完整创作所要求的内容。"
                        "输出要有实质内容，格式清晰，直接可用。"
                    ),
                },
            ]

            async for chunk in call_llm_stream(creation_messages):
                yield chunk

            logger.info("Lois Execution 车道完成：工具 %s", tool_name)
            return

        # ─── 情况 C：无工具调用，轻量 Micro-Task 直接回复 ──────────
        if content:
            # NOTE: 模型已通过非工具路径直接输出，直接流式推送
            logger.info("Lois Micro-Task 车道：轻量直接回复")
            yield _make_progress("start", label="Lois 直接作答…")
            # 非流式的直接 content 一次性推出
            yield content
            return

        # NOTE: 如果 content 为空且无工具调用（异常边界），走 fallback 流式
        logger.warning("Lois Micro-Task：LLM 返回空 content 且无工具调用，启动 fallback 流式")
        yield _make_progress("start", label="Lois 正在思考…")
        fallback_messages: list[dict] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"内容策划诉求：\n\n{user_prompt}"},
        ]
        async for chunk in call_llm_stream(fallback_messages):
            yield chunk
        return

    # ─── ③ Full-Plan 车道（全案品牌内容策划）────────────────────
    logger.info("Lois Full-Plan 车道启动")
    yield _make_progress("start", label="Lois 启动全案内容策划引擎…")

    system_prompt = _build_lois_system_prompt(handoff_context)

    full_plan_directive = (
        "\n\n[执行指令] 本次属于【全案品牌内容策划】模式，按以下固定顺序调用工具：\n"
        "① define_brand_voice → ② draft_brand_story → ③ brainstorm_slogans "
        "→ ④ build_social_matrix → ⑤ design_kol_koc_strategy → ⑥ synthesize_content_report\n"
        "所有工具必须完整调用，最后以 synthesize_content_report 收尾触发报告生成。"
    )

    messages: list[dict] = [
        {"role": "system", "content": system_prompt + full_plan_directive},
        {
            "role": "user",
            "content": (
                f"品牌内容策划需求：\n{user_prompt}\n\n"
                "请按顺序执行内容策划工具链，完成全案内容策略推演。"
            ),
        },
    ]

    # NOTE: 工具调用循环（最多 _MAX_TOOL_ROUNDS 轮，防止失控循环）
    action_label_map = {
        "define_brand_voice":        "建立品牌语感系统",
        "draft_brand_story":         "创作品牌故事",
        "brainstorm_slogans":        "推敲核心 Slogan",
        "build_social_matrix":       "搭建社交媒体矩阵",
        "design_kol_koc_strategy":   "设计 KOL/KOC 策略",
        "synthesize_content_report": "整合全案内容策略报告",
    }
    synthesize_result: dict | None = None

    for round_idx in range(_MAX_TOOL_ROUNDS):
        content, tool_calls = await call_llm_with_tools(
            messages=messages,
            tools=LOIS_TOOLS,
        )

        if not tool_calls:
            # 无工具调用，可能是 LLM 直接返回结论或出现异常
            logger.warning("Lois Full-Plan 第 %d 轮无工具调用", round_idx)
            if content:
                yield content
            break

        for tc in tool_calls:
            tool_name = tc["function"]["name"]
            try:
                raw_args = tc["function"].get("arguments", "{}")
                args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
            except json.JSONDecodeError:
                args = {}

            label = action_label_map.get(tool_name, f"执行 {tool_name}")
            yield _make_progress(tool_name, label=f"Lois 正在{label}…")

            tool_result = dispatch_lois_tool(tool_name, args)

            # 检测是否到达最终报告触发点
            if tool_name == _SYNTHESIZE_TRIGGER:
                try:
                    synthesize_result = json.loads(tool_result)
                except Exception:
                    synthesize_result = None

            # 注入工具结果到消息历史
            messages.append(
                {
                    "role": "assistant",
                    "content": content or None,
                    "tool_calls": [
                        {
                            "id": tc.get("id", f"tc_{round_idx}_{tool_name}"),
                            "type": "function",
                            "function": {
                                "name": tool_name,
                                "arguments": tc["function"].get("arguments", "{}"),
                            },
                        }
                    ],
                }
            )
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.get("id", f"tc_{round_idx}_{tool_name}"),
                    "content": tool_result,
                }
            )

        # synthesize_content_report 工具触发后退出循环，进入最终报告生成
        if synthesize_result:
            break

    # ─── Phase 2：流式生成最终品牌内容策略完整报告 ────────────────
    yield _make_progress("report_generating", label="Lois 正在执笔，整合全案内容策略报告…")

    report_directive = (
        "请以内容创意总监 Lois 的专业视角，基于以上所有工具的策划成果，"
        "用流畅、有感染力的完整报告呈现本次品牌内容策略全案。\n"
        "报告结构：\n"
        "① 品牌语感系统  ② 品牌故事（含电梯演讲版）③ 核心 Slogan 推荐  "
        "④ 社交媒体矩阵  ⑤ KOL/KOC 策略与关键词防线  ⑥ 首月内容日历框架\n"
        "最后以 <handoff> 标签内嵌交接信息，供 Scher 视觉 Agent 对接使用。"
    )

    if synthesize_result:
        handoff_data = synthesize_result
        report_directive += (
            f"\n\n交接核心（已提炼）：\n"
            f"- 首选 Slogan：{handoff_data.get('handoff_slogan', '')}\n"
            f"- 调性关键词：{' / '.join(handoff_data.get('handoff_brand_voice_keywords', []))}\n"
            f"- 主力渠道：{' / '.join(handoff_data.get('handoff_top_channels', []))}\n"
            f"- 视觉方向指令：{handoff_data.get('handoff_visual_style_direction', '')}\n"
            f"- 首月主题：{handoff_data.get('handoff_content_theme_month1', '')}"
        )

    messages.append({"role": "user", "content": report_directive})

    async for chunk in call_llm_stream(messages):
        yield chunk

    logger.info("Lois Full-Plan 车道完成")
