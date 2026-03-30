from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncGenerator
from typing import Literal

from app.service.market_agent import run_market_agent
from app.service.strategy_agent import run_strategy_agent
from app.service.content_agent import run_content_agent
from app.service.visual_agent import run_visual_agent

logger = logging.getLogger(__name__)

AgentId = Literal["market", "strategy", "content", "visual"]

# NOTE: SSE 事件格式严格遵循 text/event-stream 规范
# 前端 EventSource 通过 event 字段区分不同类型的消息
def _sse_event(event: str, data: str) -> str:
    """格式化单条 SSE 事件"""
    # 数据中的换行符需要转义，避免破坏 SSE 协议格式
    safe_data = data.replace("\n", "\\n")
    return f"event: {event}\ndata: {safe_data}\n\n"


class AgentOrchestrator:
    """
    品牌咨询 Agent 编排器（核心）
    按顺序调用 4 个专业 Agent，每个 Agent 的输出作为下一个 Agent 的上下文
    通过 SSE 实时将进度和内容推流给前端
    """

    async def run_session(
        self,
        user_prompt: str,
    ) -> AsyncGenerator[str, None]:
        """
        执行完整的品牌咨询工作流
        yield 的每条字符串都是一个符合 SSE 规范的事件字符串
        """
        context: dict[AgentId, str] = {}

        # ─── Agent 1：市场研究 ───────────────────────────
        yield _sse_event("agent_start", "market")
        logger.info("开始执行 市场研究 Agent")

        market_output = await run_market_agent(user_prompt)
        context["market"] = market_output

        yield _sse_event("agent_output", json.dumps({"id": "market", "content": market_output}))
        yield _sse_event("agent_complete", "market")
        logger.info("市场研究 Agent 完成，输出长度: %d", len(market_output))

        # ─── Agent 2：品牌战略 ───────────────────────────
        yield _sse_event("agent_start", "strategy")
        logger.info("开始执行 品牌战略 Agent")

        strategy_output = await run_strategy_agent(user_prompt, context["market"])
        context["strategy"] = strategy_output

        yield _sse_event("agent_output", json.dumps({"id": "strategy", "content": strategy_output}))
        yield _sse_event("agent_complete", "strategy")
        logger.info("品牌战略 Agent 完成，输出长度: %d", len(strategy_output))

        # ─── Agent 3：内容策划 ───────────────────────────
        yield _sse_event("agent_start", "content")
        logger.info("开始执行 内容策划 Agent")

        content_output = await run_content_agent(
            user_prompt, context["market"], context["strategy"]
        )
        context["content"] = content_output

        yield _sse_event("agent_output", json.dumps({"id": "content", "content": content_output}))
        yield _sse_event("agent_complete", "content")
        logger.info("内容策划 Agent 完成，输出长度: %d", len(content_output))

        # ─── Agent 4：视觉设计 ───────────────────────────
        yield _sse_event("agent_start", "visual")
        logger.info("开始执行 视觉设计 Agent")

        visual_output = await run_visual_agent(
            user_prompt,
            context["market"],
            context["strategy"],
            context["content"],
        )
        context["visual"] = visual_output

        yield _sse_event("agent_output", json.dumps({"id": "visual", "content": visual_output}))
        yield _sse_event("agent_complete", "visual")
        logger.info("视觉设计 Agent 完成，输出长度: %d", len(visual_output))

        # ─── 全部完成，推送汇总报告 ──────────────────────
        final_report = self._assemble_report(user_prompt, context)
        yield _sse_event(
            "session_complete",
            json.dumps({"report": final_report}),
        )
        logger.info("品牌咨询工作流全部完成")

    def _assemble_report(
        self,
        user_prompt: str,
        context: dict[AgentId, str],
    ) -> str:
        """
        将 4 个 Agent 的输出汇总为完整品牌战略报告
        """
        return f"""# 品牌战略报告

> 品牌需求：{user_prompt}

---

# 一、市场研究报告

{context.get("market", "")}

---

# 二、品牌战略手册

{context.get("strategy", "")}

---

# 三、内容策划手册

{context.get("content", "")}

---

# 四、视觉识别系统规范

{context.get("visual", "")}

---

*本报告由 Woloong AI 品牌咨询平台生成*
"""
