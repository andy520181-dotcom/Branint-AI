from __future__ import annotations
from collections.abc import AsyncGenerator
from app.service.llm_provider import call_llm, call_llm_stream
from app.service.prompt_loader import load_agent_prompt


async def run_strategy_agent(user_prompt: str, handoff_context: str) -> str:
    """
    品牌战略 Agent（非流式）
    接收市场研究的 handoff 交接摘要，而非全文
    """
    # NOTE: handoff_context 是 market Agent 的精炼交接摘要（~200字），非全文（~4000字）
    user_content = f"品牌需求：\n{user_prompt}"
    if handoff_context:
        user_content += f"\n\n{handoff_context}"
    user_content += "\n\n请基于以上交接信息，为品牌制定完整的战略方向。"

    messages = [
        {"role": "system", "content": load_agent_prompt("strategy")},
        {"role": "user", "content": user_content},
    ]
    return await call_llm(messages)


async def run_strategy_agent_stream(
    user_prompt: str,
    handoff_context: str,
) -> AsyncGenerator[str, None]:
    """
    品牌战略 Agent（流式）
    yield 每个 token，供 orchestrator 实时推送给前端
    """
    user_content = f"品牌需求：\n{user_prompt}"
    if handoff_context:
        user_content += f"\n\n{handoff_context}"
    user_content += "\n\n请基于以上交接信息，为品牌制定完整的战略方向。"

    messages = [
        {"role": "system", "content": load_agent_prompt("strategy")},
        {"role": "user", "content": user_content},
    ]
    async for chunk in call_llm_stream(messages):
        yield chunk
