"""
品牌顾问 Agent（Brand Consultant Agent）— 工作流总控

职责：
  1. run_planning_phase  — 分析用户需求，决定启用哪些专业 Agent，并制定执行计划
                          返回：(selected_agents, plan_text)
  2. run_quality_review  — 整合专业 Agent 的输出，以顾问视角进行质量审核，
                           输出最终综合品牌策略报告
"""
from __future__ import annotations

import json
import logging
import re
from collections.abc import AsyncGenerator
from typing import Literal

from app.service.llm_provider import call_llm, call_llm_stream, call_llm_with_tools
from app.service.prompt_loader import load_agent_prompt
from app.service.skills.ogilvy_skills import OGILVY_TOOLS, parse_ogilvy_tool_calls

logger = logging.getLogger(__name__)

AgentKey = Literal["market", "strategy", "content", "visual"]


def _parse_routing_response(raw: str) -> tuple[list[AgentKey], str]:
    """
    解析顾问的结构化输出，提取选定的 Agent 列表和计划文本
    格式：
        ROUTING:["market","strategy"]
        ---
        ## 需求理解...
    """
    valid_agents: set[AgentKey] = {"market", "strategy", "content", "visual"}

    # 提取 ROUTING 行
    match = re.search(r"ROUTING:\s*(\[.*?\])", raw, re.IGNORECASE)
    if match:
        try:
            agents_raw: list[str] = json.loads(match.group(1))
            selected = [a for a in agents_raw if a in valid_agents]  # type: ignore[misc]
        except (json.JSONDecodeError, TypeError):
            selected = list(valid_agents)
    else:
        selected = list(valid_agents)

    # 提取计划文本（--- 分割线之后）
    parts = re.split(r"^---\s*$", raw, maxsplit=1, flags=re.MULTILINE)
    plan_text = parts[1].strip() if len(parts) > 1 else raw.strip()

    logger.info("路由决策：选定 Agent = %s", selected)
    return selected, plan_text  # type: ignore[return-value]


def _build_history_context(conversation_history: list[dict]) -> str:
    """
    将多轮对话历史构建为可注入 Prompt 的上下文文本。
    每轮包含用户原始输入和各 Agent 的完整输出，
    使品牌顾问在后续轮次中理解之前的分析内容。
    """
    if not conversation_history:
        return ""

    agent_label = {
        "consultant_plan": "品牌顾问（执行计划）",
        "market": "市场研究 Agent",
        "strategy": "品牌战略 Agent",
        "content": "内容策划 Agent",
        "visual": "美术指导 Agent",
        "consultant_review": "品牌顾问（综合报告）",
    }

    parts: list[str] = []
    for i, round_data in enumerate(conversation_history, 1):
        round_text = f"\n====== 第{i}轮对话 ======\n"
        round_text += f"用户需求：{round_data.get('user_prompt', '')}"

        agent_outputs = round_data.get("agent_outputs", {})
        for agent_id, output in agent_outputs.items():
            label = agent_label.get(agent_id, agent_id)
            round_text += f"\n\n【{label} 输出】：\n{output}"

        parts.append(round_text)

    return "\n".join(parts)


def _build_review_sections(
    project_context: dict,
    selected_agents: list[AgentKey],
) -> str:
    """
    为审核阶段构建双层注入内容：
    第一层：所有 Agent 的 handoff 交接摘要（快速总览）
    第二层：各 Agent 的完整输出（深度审核引用）
    """
    agent_label = {
        "market": "市场研究 Agent",
        "strategy": "品牌战略 Agent",
        "content": "内容策划 Agent",
        "visual": "美术指导 Agent",
    }

    handoffs = project_context.get("handoffs", {})
    full_outputs = project_context.get("full_outputs", {})

    # 第一层：handoff 总览
    handoff_parts: list[str] = []
    for key in selected_agents:
        if key in handoffs and handoffs[key]:
            handoff_parts.append(f"【{agent_label.get(key, key)} · 交接摘要】：\n{handoffs[key]}")
    handoff_summary = "\n\n".join(handoff_parts)

    # 第二层：完整输出
    full_parts: list[str] = []
    for key in selected_agents:
        if key in full_outputs and full_outputs[key]:
            full_parts.append(f"【{agent_label.get(key, key)} · 完整输出】：\n{full_outputs[key]}")
    full_text = "\n\n---\n\n".join(full_parts)

    return (
        "═══ 第一层：交接摘要（快速总览） ═══\n\n"
        f"{handoff_summary}\n\n"
        "═══ 第二层：完整输出（深度审核引用） ═══\n\n"
        f"{full_text}"
    )


async def run_planning_phase(
    user_prompt: str,
    conversation_history: list[dict] | None = None,
) -> tuple[list[AgentKey], str]:
    """
    品牌顾问 — 需求分析 & 路由决策阶段
    """
    history_text = _build_history_context(conversation_history or [])

    if history_text:
        user_content = (
            f"【历史对话上下文】\n{history_text}\n\n"
            f"====== 本轮用户输入 ======\n{user_prompt}\n\n"
            "请基于以上历史上下文和本轮用户输入，分析需求，选择合适的智能体并制定执行计划。"
        )
    else:
        user_content = f"客户品牌需求：{user_prompt}\n\n请分析需求，选择合适的智能体并制定执行计划。"

    messages = [
        {"role": "system", "content": load_agent_prompt("consultant_plan")},
        {"role": "user", "content": user_content},
    ]
    raw = await call_llm(messages)
    return _parse_routing_response(raw)


async def run_ogilvy_decision(
    user_prompt: str,
    conversation_history: list[dict] | None = None,
) -> dict:
    """
    品牌顾问 — 调用 Tool Calling 做出决策
    返回:
       {"action": "clarify_requirement", "args": {"question": "..."}}
     或
       {"action": "generate_workflow_dag", "args": {"routing_sequence": [...], "plan_explanation": "..."}}
     或
       {"action": "none", "content": "..."}
    """
    history_text = _build_history_context(conversation_history or [])

    if history_text:
        user_content = (
            f"【历史对话上下文】\n{history_text}\n\n"
            f"====== 本轮用户输入 ======\n{user_prompt}\n\n"
            "请基于以上历史上下文和本轮用户输入，调用合适的工具来推进流程。"
        )
    else:
        user_content = f"客户品牌需求：{user_prompt}\n\n请调用工具处理此需求。"

    messages = [
        {"role": "system", "content": load_agent_prompt("consultant_plan")},
        {"role": "user", "content": user_content},
    ]
    
    # 强制模型在此阶段必须使用工具
    content, tool_calls = await call_llm_with_tools(
        messages=messages, 
        tools=OGILVY_TOOLS,
    )
    
    parsed_tool = parse_ogilvy_tool_calls(tool_calls) if tool_calls else None
    
    if parsed_tool:
        return parsed_tool
        
    return {
        "action": "none",
        "content": content
    }


async def run_planning_phase_stream(
    plan_explanation: str,
) -> AsyncGenerator[str, None]:
    """
    不再走一次大模型，直接流式回显已经决定好的解释文本，
    保持前端打字机效果。
    """
    # 模拟流式输出
    chunk_size = 5
    for i in range(0, len(plan_explanation), chunk_size):
        yield plan_explanation[i:i+chunk_size]


async def run_direct_response_stream(
    user_prompt: str,
    response_prompt: str,
    conversation_history: list[dict] | None = None,
) -> AsyncGenerator[str, None]:
    """
    品牌顾问 — 直接回复（Direct Response）模式。
    适用于命名建议、概念探讨、递交语言优化等轻量咋询。
    不启动任何下游专业 Agent，直接调用 DeepSeek 流式作答。
    """
    history_text = _build_history_context(conversation_history or [])

    # NOTE: 将 response_prompt（模型对自己回答规划的描述）与用户原始问题合并，
    # 让模型以一首品牌顾问的角色流式生成回复
    if history_text:
        user_content = (
            f"【历史对话上下文】\n{history_text}\n\n"
            f"====== 本轮用户输入 ======\n{user_prompt}\n\n"
            f"回答指引：{response_prompt}"
        )
    else:
        user_content = (
            f"用户咋询：{user_prompt}\n\n"
            f"回答指引：{response_prompt}"
        )

    messages = [
        {"role": "system", "content": load_agent_prompt("consultant_plan")},
        {"role": "user", "content": user_content},
    ]
    async for chunk in call_llm_stream(messages):
        yield chunk


async def run_quality_review(
    user_prompt: str,
    selected_agents: list[AgentKey],
    project_context: dict,
) -> str:
    """
    品牌顾问 — 质量审核 & 最终报告阶段
    使用双层注入：handoff 总览（快速理解）+ 全文引用（深度审核）
    """
    review_content = _build_review_sections(project_context, selected_agents)

    user_message = (
        f"用户品牌需求：\n{user_prompt}\n\n"
        f"本次执行的 Agent：{', '.join(selected_agents)}\n\n"
        f"---\n\n{review_content}\n\n"
        "---\n请以首席品牌顾问的身份，审核以上报告，输出最终品牌策略综合报告。"
    )

    messages = [
        {"role": "system", "content": load_agent_prompt("consultant_review")},
        {"role": "user", "content": user_message},
    ]
    return await call_llm(messages)


async def run_quality_review_stream(
    user_prompt: str,
    selected_agents: list[AgentKey],
    project_context: dict,
) -> AsyncGenerator[str, None]:
    """
    品牌顾问 — 质量审核 & 最终报告（流式版）
    """
    review_content = _build_review_sections(project_context, selected_agents)

    user_message = (
        f"用户品牌需求：\n{user_prompt}\n\n"
        f"本次执行的 Agent：{', '.join(selected_agents)}\n\n"
        f"---\n\n{review_content}\n\n"
        "---\n请以首席品牌顾问的身份，审核以上报告，输出最终品牌策略综合报告。"
    )

    messages = [
        {"role": "system", "content": load_agent_prompt("consultant_review")},
        {"role": "user", "content": user_message},
    ]
    async for chunk in call_llm_stream(messages):
        yield chunk
