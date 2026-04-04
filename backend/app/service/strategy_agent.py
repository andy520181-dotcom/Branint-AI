"""
品牌战略 Agent — Trout（智能框架自适应版）

工作流：
  Round 0: select_applicable_frameworks → 分析场景，输出 framework_sequence（元路由）
  Round 1-N: 按 framework_sequence 依次调用品牌框架工具（动态选用，非全量固定）
  Phase 2: 流式生成完整 Markdown 品牌战略报告

关键设计：
  - 第一轮必须调用 select_applicable_frameworks，确定本次需要哪些框架
  - 后续循环只执行 framework_sequence 中的工具，跳过不需要的框架
  - synthesize_strategy_report 触发后结束循环，进入流式报告生成
"""
from __future__ import annotations

import json
import logging
from collections.abc import AsyncGenerator

from app.service.llm_provider import call_llm_stream, call_llm_with_tools
from app.service.prompt_loader import load_agent_prompt
from app.service.skills.trout_skills import (
    TROUT_TOOLS,
    execute_trout_tool,
    parse_trout_tool_calls,
)

logger = logging.getLogger(__name__)

# 安全上限：防止 LLM 无限循环调用工具（最多10轮，覆盖所有6个框架+预选+合成）
MAX_TOOL_ROUNDS = 10
# 报告输出触发词
SYNTHESIS_TRIGGER = "synthesize_strategy_report"
# 元路由工具名
FRAMEWORK_SELECTOR = "select_applicable_frameworks"


async def run_strategy_agent_stream(
    user_prompt: str,
    handoff_context: str,
) -> AsyncGenerator[str, None]:
    """
    品牌战略 Agent 主入口（流式输出）。

    Phase 1: 智能框架选择 + 多轮工具调用循环
      - 第一轮：LLM 调用 select_applicable_frameworks 分析场景，返回 framework_sequence
      - 后续轮：LLM 按 framework_sequence 顺序依次调用各品牌框架工具
      - 直到 synthesize_strategy_report 被调用，循环结束

    Phase 2: 流式生成 Markdown 品牌战略报告

    Args:
        user_prompt:    用户的品牌需求原文
        handoff_context: 市场研究 Agent（Wacksman）的 handoff 交接摘要
    """
    system_prompt = load_agent_prompt("strategy")

    # 初始消息：包含用户需求 + Wacksman 交接摘要
    user_content = f"品牌需求：\n{user_prompt}"
    if handoff_context:
        user_content += f"\n\n{handoff_context}"
    user_content += (
        "\n\n【第一步必须】请调用 select_applicable_frameworks 分析本次品牌项目场景，"
        "智能选择需要执行哪些战略框架，然后按选定顺序逐步完成分析。"
    )

    messages: list[dict] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]

    # NOTE: framework_sequence 由 select_applicable_frameworks 决定
    # 这是让 agent 按照 LLM「选定的框架清单」执行的关键机制
    framework_plan: list[str] = []
    executed_frameworks: list[str] = []

    # ─── Phase 1: 智能框架选择 + 工具调用循环 ──────────────────────────────
    for round_idx in range(1, MAX_TOOL_ROUNDS + 1):
        logger.info(
            "Trout 工具循环 Round %d/%d | 已执行: %s | 计划序列: %s",
            round_idx, MAX_TOOL_ROUNDS,
            executed_frameworks or "无",
            framework_plan or "待选",
        )

        response = await call_llm_with_tools(
            messages=messages,
            tools=TROUT_TOOLS,
        )

        tool_calls = response.get("tool_calls") or []
        text_content = (response.get("content") or "").strip()

        # 情形 A：LLM 调用了工具
        if tool_calls:
            parsed = parse_trout_tool_calls(tool_calls)

            messages.append({
                "role": "assistant",
                "content": text_content or None,
                "tool_calls": tool_calls,
            })

            synthesis_triggered = False
            for tool_name, args in parsed:
                logger.info("Trout 调用工具: %s", tool_name)
                result_str = execute_trout_tool(tool_name, args)
                executed_frameworks.append(tool_name)

                # NOTE: 元路由工具执行完成后，从结果中提取 framework_sequence
                # 这个序列将作为后续轮次的「路径图」，在 system 追加 context 时注入
                if tool_name == FRAMEWORK_SELECTOR:
                    try:
                        plan_result = json.loads(result_str)
                        framework_plan = plan_result.get("framework_sequence", [])
                        logger.info("Trout 框架计划已确定: %s", framework_plan)
                    except (json.JSONDecodeError, AttributeError):
                        logger.warning("Trout 框架计划解析失败，将由 LLM 自主决定")

                messages.append({
                    "role": "tool",
                    "tool_call_id": next(
                        (tc.get("id", "") for tc in tool_calls
                         if tc.get("function", {}).get("name") == tool_name),
                        f"tool_call_{round_idx}",
                    ),
                    "content": result_str,
                })

                if tool_name == SYNTHESIS_TRIGGER:
                    synthesis_triggered = True

            if synthesis_triggered:
                logger.info(
                    "Trout 所有框架工具执行完毕。执行序列: %s",
                    " → ".join(executed_frameworks),
                )
                break

            # NOTE: 若 framework_plan 已确定，在每轮工具结果后注入「当前进度」提示，
            # 帮助 LLM 清楚知道下一步调用哪个工具（避免遗漏或重复调用）
            if framework_plan:
                remaining = [f for f in framework_plan if f not in executed_frameworks]
                if remaining:
                    next_tool = remaining[0]
                    progress_hint = (
                        f"[执行进度] 已完成: {', '.join(executed_frameworks)} | "
                        f"下一步: {next_tool} | "
                        f"剩余: {' → '.join(remaining)}"
                    )
                    messages.append({
                        "role": "user",
                        "content": progress_hint,
                    })

        # 情形 B：LLM 直接返回文本（跳过工具调用）
        elif text_content:
            logger.info("Trout Round %d 直接返回文本，结束循环进入报告生成", round_idx)
            messages.append({"role": "assistant", "content": text_content})
            break

        # 情形 C：空响应，异常退出
        else:
            logger.warning("Trout Round %d 空响应，终止循环", round_idx)
            break

    # ─── Phase 2: 流式生成最终战略报告 ────────────────────────────────────
    # 构建报告生成指令，只报告本次实际执行的框架章节（跳过未执行的）
    executed_display = [f for f in executed_frameworks if f not in (FRAMEWORK_SELECTOR, SYNTHESIS_TRIGGER)]
    chapter_map = {
        "apply_positioning_framework": "① 品牌定位",
        "build_brand_house": "② 品牌屋",
        "design_brand_architecture": "③ 品牌架构",
        "apply_brand_archetypes": "④ 品牌原型系统",
        "generate_naming_candidates": "⑤ 命名方案",
    }
    chapters = [chapter_map[f] for f in executed_display if f in chapter_map]
    chapters.append("⑥ 落地建议与 Handoff 摘要")

    messages.append({
        "role": "user",
        "content": (
            f"请现在根据以上框架分析结果，生成完整的品牌战略 Markdown 报告。"
            f"本次需要输出的章节：{' | '.join(chapters)}。"
            "请严格按照 strategy.md 中定义的报告结构，每个章节均需详尽展开，"
            "最后附上 <handoff> 标签数据供下游 Agent 读取。"
        ),
    })

    logger.info("Trout 开始流式生成品牌战略报告（章节: %s）...", " | ".join(chapters))
    async for chunk in call_llm_stream(messages):
        yield chunk

    logger.info("Trout 品牌战略报告生成完成（总工具调用: %d 次）", len(executed_frameworks))
