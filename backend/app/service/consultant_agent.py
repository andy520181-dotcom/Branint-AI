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

from app.service.llm_provider import call_llm, call_llm_stream

logger = logging.getLogger(__name__)

AgentKey = Literal["market", "strategy", "content", "visual"]

# ── 智能路由 Prompt ────────────────────────────────────────────────────────
ROUTING_SYSTEM_PROMPT = """你是 Brandclaw AI 的首席品牌顾问，负责根据客户需求灵活调度专业智能体。

可调用的专业智能体：
- market   : 市场研究 Agent（竞品分析、消费者画像、市场机会）
- strategy : 品牌战略 Agent（品牌定位、命名、MVV、USP）
- content  : 内容策划 Agent（品牌故事、Slogan、内容矩阵）
- visual   : 视觉设计 Agent（色板、字体、Logo 方向、VI 规范）

**调度原则**：
1. 只选择用户真正需要的智能体，不多不少
2. 若用户只需视觉设计 → 只调用 visual
3. 若用户需要内容与视觉 → 调用 content + visual
4. 若是完整品牌项目 → 调用全部四个
5. 若需要战略但没有市场数据做支撑 → 同时调用 market + strategy
6. 若用户已有明确定位只需内容落地 → 只调用 content（可选 visual）

**输出格式（严格按此格式，不加任何多余内容）**：
第一行：ROUTING:<JSON数组，只含上述 agent key>
第二行：---
之后：执行计划文本（Markdown）

执行计划文本结构：
## 🧑‍💼 需求理解
（2-3句精准概括核心诉求与关键挑战）

## 📋 调度安排
（说明为何调用这些 Agent，以及协作逻辑）

## 🎯 关键成功指标
（3-5条，简洁有力）"""


# ── 质量审核 & 最终报告 Prompt ────────────────────────────────────────────
QUALITY_REVIEW_SYSTEM_PROMPT = """你是 Brandclaw AI 的首席品牌顾问，拥有 15 年以上顶级品牌咨询经验。

专业 Agent 已完成各自的分析工作。现在你需要：
1. 以品牌顾问的专业视角，审核各份报告的质量与一致性
2. 提炼最核心的战略洞察
3. 整合输出一份完整、连贯的最终品牌策略报告（只包含本次实际执行的部分）

最终报告要求：
- 以品牌顾问的口吻撰写，有观点、有温度，不是机械拼接
- 确保各模块逻辑自洽，相互支撑
- 末尾给出「顾问建议」：3 条最重要的优先行动建议

输出格式（Markdown）：

# 品牌策略综合报告

> 品牌需求：{user_prompt}

---

## 顾问前言
（2-3句，点出核心战略方向）

---

{sections}

---

## 顾问建议 · 优先行动清单
（3 条最重要、需立即启动的行动建议，每条附简短理由）

---

*本报告由 Brandclaw AI 品牌顾问智能体审核输出*"""


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
            # 过滤无效 key，保持原始顺序
            selected = [a for a in agents_raw if a in valid_agents]  # type: ignore[misc]
        except (json.JSONDecodeError, TypeError):
            selected = list(valid_agents)  # 解析失败，fallback 全部
    else:
        selected = list(valid_agents)  # 找不到路由，fallback 全部

    # 提取计划文本（--- 分割线之后）
    parts = re.split(r"^---\s*$", raw, maxsplit=1, flags=re.MULTILINE)
    plan_text = parts[1].strip() if len(parts) > 1 else raw.strip()

    logger.info("路由决策：选定 Agent = %s", selected)
    return selected, plan_text  # type: ignore[return-value]


def _build_review_sections(
    context: dict[str, str],
    selected_agents: list[AgentKey],
) -> str:
    """根据实际运行的 Agent 构建审核提示词中的 sections 描述"""
    section_map = {
        "market":   "【市场研究 Agent 输出】",
        "strategy": "【品牌战略 Agent 输出】",
        "content":  "【内容策划 Agent 输出】",
        "visual":   "【视觉设计 Agent 输出】",
    }
    parts = []
    for key in selected_agents:
        if key in context and context[key]:
            parts.append(f"{section_map[key]}：\n{context[key]}")
    return "\n\n---\n\n".join(parts)


async def run_planning_phase(user_prompt: str) -> tuple[list[AgentKey], str]:
    """
    品牌顾问 — 需求分析 & 路由决策阶段
    返回：(selected_agents, plan_text)
      - selected_agents: 需要运行的 Agent key 列表（有序）
      - plan_text:       人类可读的执行计划文本（Markdown）
    """
    messages = [
        {"role": "system", "content": ROUTING_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"客户品牌需求：{user_prompt}\n\n请分析需求，选择合适的智能体并制定执行计划。",
        },
    ]
    raw = await call_llm(messages)
    return _parse_routing_response(raw)


async def run_planning_phase_stream(
    user_prompt: str,
) -> AsyncGenerator[str, None]:
    """
    品牌顾问 — 需求分析 & 路由决策（流式版）
    逐 token yield，供 orchestrator 实时推送给前端
    orchestrator 需自行累积完整文本后调用 _parse_routing_response 解析
    """
    messages = [
        {"role": "system", "content": ROUTING_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"客户品牌需求：{user_prompt}\n\n请分析需求，选择合适的智能体并制定执行计划。",
        },
    ]
    async for chunk in call_llm_stream(messages):
        yield chunk


async def run_quality_review(
    user_prompt: str,
    selected_agents: list[AgentKey],
    context: dict[str, str],
) -> str:
    """
    品牌顾问 — 质量审核 & 最终报告阶段
    只整合本次实际运行的 Agent 输出，以顾问视角审核并生成综合品牌策略报告
    """
    section_names = {
        "market":   "市场研究 · 核心洞察",
        "strategy": "品牌战略 · 定位框架",
        "content":  "内容策略 · 传播规划",
        "visual":   "视觉识别 · 设计方向",
    }
    sections_template = "\n\n---\n\n".join(
        f"## {i + 1}、{section_names[a]}\n（基于 {section_names[a].split('·')[0].strip()} Agent 成果提炼）"
        for i, a in enumerate(selected_agents)
    )

    agent_outputs = _build_review_sections(context, selected_agents)

    system_prompt = QUALITY_REVIEW_SYSTEM_PROMPT.replace(
        "{sections}", sections_template
    )

    user_message = (
        f"用户品牌需求：\n{user_prompt}\n\n"
        f"本次执行的 Agent：{', '.join(selected_agents)}\n\n"
        f"---\n\n{agent_outputs}\n\n"
        "---\n请以首席品牌顾问的身份，审核以上报告，输出最终品牌策略综合报告。"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]
    return await call_llm(messages)


async def run_quality_review_stream(
    user_prompt: str,
    selected_agents: list[AgentKey],
    context: dict[str, str],
) -> AsyncGenerator[str, None]:
    """
    品牌顾问 — 质量审核 & 最终报告（流式版）
    逐 token yield，供 orchestrator 实时推送给前端
    """
    section_names = {
        "market":   "市场研究 · 核心洞察",
        "strategy": "品牌战略 · 定位框架",
        "content":  "内容策略 · 传播规划",
        "visual":   "视觉识别 · 设计方向",
    }
    sections_template = "\n\n---\n\n".join(
        f"## {i + 1}、{section_names[a]}\n（基于 {section_names[a].split('·')[0].strip()} Agent 成果提炼）"
        for i, a in enumerate(selected_agents)
    )

    agent_outputs = _build_review_sections(context, selected_agents)

    system_prompt = QUALITY_REVIEW_SYSTEM_PROMPT.replace(
        "{sections}", sections_template
    )

    user_message = (
        f"用户品牌需求：\n{user_prompt}\n\n"
        f"本次执行的 Agent：{', '.join(selected_agents)}\n\n"
        f"---\n\n{agent_outputs}\n\n"
        "---\n请以首席品牌顾问的身份，审核以上报告，输出最终品牌策略综合报告。"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]
    async for chunk in call_llm_stream(messages):
        yield chunk
