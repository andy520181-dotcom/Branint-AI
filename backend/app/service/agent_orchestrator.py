from __future__ import annotations

import json
import logging
from collections.abc import AsyncGenerator
from typing import Literal

from app.service.consultant_agent import AgentKey, run_planning_phase, run_quality_review
from app.service.market_agent import run_market_agent
from app.service.strategy_agent import run_strategy_agent
from app.service.content_agent import run_content_agent
from app.service.visual_agent import run_visual_agent

logger = logging.getLogger(__name__)

AgentId = Literal["consultant_plan", "market", "strategy", "content", "visual", "consultant_review"]


def _sse(event: str, data: str) -> str:
    """格式化单条 SSE 事件，换行符转义避免破坏协议格式"""
    return f"event: {event}\ndata: {data.replace(chr(10), chr(92) + 'n')}\n\n"


class AgentOrchestrator:
    """
    品牌咨询 Agent 编排器（动态路由版）

    工作流：
      品牌顾问（需求分析 + 路由决策）
        → 动态选择并运行所需专业 Agent
        → 品牌顾问（质量审核 + 最终报告）

    NOTE: 并非所有请求都走完整 4 步流程，
          顾问根据用户输入智能决定只调用必要的 Agent。
    """

    # 专业 Agent 的执行函数映射
    # 每个函数接受 (user_prompt, **所需上游 context) → str
    _AGENT_RUNNERS = {
        "market":   lambda p, ctx: run_market_agent(p),
        "strategy": lambda p, ctx: run_strategy_agent(p, ctx.get("market", "")),
        "content":  lambda p, ctx: run_content_agent(p, ctx.get("market", ""), ctx.get("strategy", "")),
        "visual":   lambda p, ctx: run_visual_agent(
            p, ctx.get("market", ""), ctx.get("strategy", ""), ctx.get("content", "")
        ),
    }

    async def run_session(
        self,
        user_prompt: str,
    ) -> AsyncGenerator[str, None]:
        """
        执行完整品牌咨询工作流（动态路由）
        yield 每条符合 text/event-stream 规范的 SSE 事件字符串
        """
        context: dict[str, str] = {}

        # ─── 品牌顾问：需求分析 & 路由决策 ──────────────────
        yield _sse("agent_start", "consultant_plan")
        logger.info("品牌顾问 — 开始需求分析，制定执行计划")

        selected_agents, plan_text = await run_planning_phase(user_prompt)

        # NOTE: 将路由决策通知前端，前端据此动态渲染 Agent 步骤列表
        yield _sse("routing_decided", json.dumps(selected_agents))
        yield _sse("consultant_plan", plan_text)
        yield _sse("agent_complete", "consultant_plan")
        logger.info("路由决策完成：%s", selected_agents)

        # ─── 动态执行选定的专业 Agent ────────────────────────
        for agent_key in selected_agents:
            runner = self._AGENT_RUNNERS.get(agent_key)
            if not runner:
                logger.warning("未知 Agent key: %s，跳过", agent_key)
                continue

            yield _sse("agent_start", agent_key)
            logger.info("启动 Agent: %s（由顾问调度）", agent_key)

            output = await runner(user_prompt, context)
            context[agent_key] = output

            yield _sse("agent_output", json.dumps({"id": agent_key, "content": output}))
            yield _sse("agent_complete", agent_key)
            logger.info("Agent %s 完成，输出: %d 字", agent_key, len(output))

        # ─── 品牌顾问：质量审核 & 最终综合报告 ───────────────
        yield _sse("agent_start", "consultant_review")
        logger.info("品牌顾问 — 开始质量审核，生成最终报告")

        final_report = await run_quality_review(
            user_prompt=user_prompt,
            selected_agents=selected_agents,
            context=context,
        )

        yield _sse("consultant_review", final_report)
        yield _sse("agent_complete", "consultant_review")
        logger.info("品牌顾问审核完成，最终报告: %d 字", len(final_report))

        # ─── 会话完成 ─────────────────────────────────────────
        yield _sse("session_complete", json.dumps({"report": final_report}))
        logger.info("品牌咨询全流程完成，共执行 Agent: %s", selected_agents)
