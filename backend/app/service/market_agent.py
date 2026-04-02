from __future__ import annotations

from collections.abc import AsyncGenerator

from app.service.llm_provider import call_llm, call_llm_stream
from app.service.prompt_loader import load_agent_prompt


async def run_market_agent(user_prompt: str) -> str:
    """
    市场研究 Agent（非流式，用于上下文传递）
    输入：用户原始品牌需求描述
    输出：结构化市场研究报告 + handoff 交接摘要
    """
    messages = [
        {"role": "system", "content": load_agent_prompt("market")},
        {"role": "user", "content": f"请对以下品牌需求进行深度市场研究分析：\n\n{user_prompt}"},
    ]
    return await call_llm(messages)


async def run_market_agent_stream(user_prompt: str) -> AsyncGenerator[str, None]:
    """
    市场研究 Agent（流式）
    yield 每个 token，供 orchestrator 实时推送给前端
    """
    messages = [
        {"role": "system", "content": load_agent_prompt("market")},
        {"role": "user", "content": f"请对以下品牌需求进行深度市场研究分析：\n\n{user_prompt}"},
    ]
    async for chunk in call_llm_stream(messages):
        yield chunk
