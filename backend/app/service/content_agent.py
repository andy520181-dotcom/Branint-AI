from __future__ import annotations
from collections.abc import AsyncGenerator
from app.service.llm_provider import call_llm, call_llm_stream
from app.service.prompt_loader import load_agent_prompt


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
) -> AsyncGenerator[str, None]:
    """
    内容策划 Agent（流式）
    yield 每个 token，供 orchestrator 实时推送给前端
    """
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
