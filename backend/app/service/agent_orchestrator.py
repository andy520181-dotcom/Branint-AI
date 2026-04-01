from __future__ import annotations

import json
import logging
from collections.abc import AsyncGenerator
from typing import Literal

from app.service.consultant_agent import (
    AgentKey,
    run_planning_phase_stream,
    run_quality_review_stream,
    _parse_routing_response,
)
from app.service.market_agent import run_market_agent_stream
from app.service.strategy_agent import run_strategy_agent_stream
from app.service.content_agent import run_content_agent_stream
from app.service.visual_agent import run_visual_agent_stream

logger = logging.getLogger(__name__)

AgentId = Literal["consultant_plan", "market", "strategy", "content", "visual", "consultant_review"]


def _sse(event: str, data: str) -> str:
    """格式化单条 SSE 事件，换行符转义避免破坏协议格式"""
    return f"event: {event}\ndata: {data.replace(chr(10), chr(92) + 'n')}\n\n"


def _sse_raw(event: str, data: str) -> str:
    """原始 SSE（chunk 内容不做换行转义，直接流式推送）"""
    return f"event: {event}\ndata: {data}\n\n"


class AgentOrchestrator:
    """
    品牌咨询 Agent 编排器（动态路由 + 流式输出版）

    工作流：
      品牌顾问（需求分析 + 路由决策）
        → 动态选择并运行所需专业 Agent（流式 token 推送）
        → 品牌顾问（质量审核 + 最终报告）

    NOTE: 并非所有请求都走完整 4 步流程，
          顾问根据用户输入智能决定只调用必要的 Agent。
    """

    async def run_session(
        self,
        user_prompt: str,
    ) -> AsyncGenerator[str, None]:
        """
        执行完整品牌咨询工作流（动态路由 + 实时流式输出）
        yield 每条符合 text/event-stream 规范的 SSE 事件字符串
        """
        context: dict[str, str] = {}

        # ─── 品牌顾问：需求分析 & 路由决策（流式） ──────────────
        yield _sse("agent_start", "consultant_plan")
        logger.info("品牌顾问 — 开始需求分析，制定执行计划")

        # NOTE: 逐 token 推送顾问思考过程，前端实时显示
        plan_accumulated = ""
        async for chunk in run_planning_phase_stream(user_prompt):
            plan_accumulated += chunk
            yield _sse_raw(
                "agent_chunk",
                json.dumps({"id": "consultant_plan", "chunk": chunk}, ensure_ascii=False),
            )

        # 累积完成后解析路由决策
        selected_agents, plan_text = _parse_routing_response(plan_accumulated)

        # NOTE: 将路由决策通知前端，前端据此动态渲染 Agent 步骤列表
        yield _sse("routing_decided", json.dumps(selected_agents))
        # 发送解析后的计划文本作为最终 agent_output（覆盖累积文本中的 ROUTING 行）
        yield _sse("agent_output", json.dumps({"id": "consultant_plan", "content": plan_text}))
        yield _sse("agent_complete", "consultant_plan")
        logger.info("路由决策完成：%s", selected_agents)

        # ─── 动态执行选定的专业 Agent（流式推送 token）────────
        for agent_key in selected_agents:
            yield _sse("agent_start", agent_key)
            logger.info("启动 Agent: %s（流式模式）", agent_key)

            accumulated = ""

            # 根据 agent_key 选择对应的流式生成器，并传入已有上下文
            if agent_key == "market":
                stream = run_market_agent_stream(user_prompt)
            elif agent_key == "strategy":
                stream = run_strategy_agent_stream(user_prompt, context.get("market", ""))
            elif agent_key == "content":
                stream = run_content_agent_stream(
                    user_prompt,
                    context.get("market", ""),
                    context.get("strategy", ""),
                )
            elif agent_key == "visual":
                stream = run_visual_agent_stream(
                    user_prompt,
                    context.get("market", ""),
                    context.get("strategy", ""),
                    context.get("content", ""),
                )
            else:
                logger.warning("未知 Agent key: %s，跳过", agent_key)
                continue

            # NOTE: 逐 token 推送 agent_chunk，前端实时累积显示思考过程
            async for chunk in stream:
                accumulated += chunk
                yield _sse_raw(
                    "agent_chunk",
                    json.dumps({"id": agent_key, "chunk": chunk}, ensure_ascii=False),
                )

            # 全部 chunk 推完后，发送完整输出供前端最终渲染（保留 Markdown 结构）
            context[agent_key] = accumulated
            yield _sse("agent_output", json.dumps({"id": agent_key, "content": accumulated}))
            yield _sse("agent_complete", agent_key)
            logger.info("Agent %s 完成，输出: %d 字", agent_key, len(accumulated))

        # ─── 品牌顾问：质量审核 & 最终综合报告（流式） ─────────
        yield _sse("agent_start", "consultant_review")
        logger.info("品牌顾问 — 开始质量审核，生成最终报告")

        # NOTE: 逐 token 推送审核过程，前端实时显示
        review_accumulated = ""
        async for chunk in run_quality_review_stream(
            user_prompt=user_prompt,
            selected_agents=selected_agents,
            context=context,
        ):
            review_accumulated += chunk
            yield _sse_raw(
                "agent_chunk",
                json.dumps({"id": "consultant_review", "chunk": chunk}, ensure_ascii=False),
            )

        # 发送完整审核报告作为 agent_output
        yield _sse("agent_output", json.dumps({"id": "consultant_review", "content": review_accumulated}))
        yield _sse("agent_complete", "consultant_review")
        logger.info("品牌顾问审核完成，最终报告: %d 字", len(review_accumulated))

        # ─── 会话完成 ─────────────────────────────────────────
        yield _sse("session_complete", json.dumps({"report": review_accumulated}))
        logger.info("品牌咨询全流程完成，共执行 Agent: %s", selected_agents)
