"""
市场研究 Agent — Wacksman（增强型联网 Agent）

工作流（中型检索模式，5-7 次 API 调用）：
  Round 1: 判断是否需要澄清研究范围
  Round 2-3: 检索市场宏观数据（规模/趋势/消费者）
  Round 4-5: 检索竞品情报（2-3个主要竞品）
  Round 6: 汇总所有检索结果，生成最终研究报告
"""
from __future__ import annotations

import json
import logging
from collections.abc import AsyncGenerator

from app.service.llm_provider import call_llm, call_llm_stream, call_llm_with_tools
from app.service.prompt_loader import load_agent_prompt
from app.service.skills.wacksman_skills import (
    WACKSMAN_TOOLS,
    execute_tavily_search,
    format_search_result_for_llm,
    parse_wacksman_tool_calls,
)

logger = logging.getLogger(__name__)

# NOTE: 中型检索模式的最大轮次限制，防止无限递归调用
MAX_RESEARCH_ROUNDS = 7


async def _run_research_loop(user_prompt: str, handoff_context: str) -> tuple[list[dict], list[dict]]:
    """
    核心研究循环（非流式）：
    驱动 LLM 多轮调用 Wacksman 工具，收集市场数据。
    
    返回: (messages 历史记录, search_citations 检索来源列表)
    """
    system_prompt = load_agent_prompt("market")
    
    context_block = ""
    if handoff_context:
        context_block = f"\n\n## 品牌顾问移交的项目背景\n{handoff_context}\n"
    
    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": (
                f"请对以下品牌需求进行深度市场研究：\n\n{user_prompt}"
                f"{context_block}"
                "\n\n请从分析研究范围开始，必要时使用联网搜索工具收集真实数据，"
                "最后调用 synthesize_research_report 生成最终报告。"
            )
        }
    ]
    
    search_citations: list[dict] = []  # 记录所有搜索来源，供前端 MarketRenderer 展示
    
    for round_num in range(MAX_RESEARCH_ROUNDS):
        logger.info("Wacksman 研究循环 Round %d/%d", round_num + 1, MAX_RESEARCH_ROUNDS)
        
        content, tool_calls = await call_llm_with_tools(
            messages=messages,
            tools=WACKSMAN_TOOLS,
        )
        
        # ── 没有 tool_calls：模型直接输出内容，视为提前完成 ─────────
        if not tool_calls:
            logger.info("Wacksman 未触发 Tool Call，提前输出完整报告。")
            # 将模型的自然语言输出追加到 messages 中
            messages.append({"role": "assistant", "content": content})
            break
        
        parsed = parse_wacksman_tool_calls(tool_calls)
        if not parsed:
            break
        
        action = parsed["action"]
        args = parsed["args"]
        logger.info("Wacksman 调用技能: %s, args preview: %s", action, str(args)[:100])
        
        # 将模型的tool_call意图追加到 messages（符合 LLM 多轮对话规范）
        messages.append({
            "role": "assistant",
            "content": content or None,
            "tool_calls": [
                {
                    "id": tool_calls[0].get("id", f"call_{round_num}"),
                    "type": "function",
                    "function": {
                        "name": action,
                        "arguments": json.dumps(args, ensure_ascii=False),
                    }
                }
            ]
        })
        
        # ── 执行各工具技能 ─────────────────────────────────────────────
        tool_result = ""
        
        if action == "clarify_research_scope":
            # NOTE: 澄清范围与 Ogilvy 不同：Wacksman 不中断流程
            # 它会继续用 LLM 内置知识做合理假设，并在报告中注明
            question = args.get("question", "")
            logger.info("Wacksman 需要澄清范围，但继续基于合理假设推进研究: %s", question)
            tool_result = (
                f"[系统] 研究范围需要澄清：{question}\n"
                "由于无法中断咨询流程，Wacksman 将基于最常见的市场假设继续研究，"
                "并在报告结尾注明此假设。请继续调用搜索工具收集数据。"
            )
        
        elif action == "web_search_market_data":
            query = args.get("query", "")
            research_angle = args.get("research_angle", "market_size")
            logger.info("Wacksman 执行市场数据检索: %s [%s]", query, research_angle)
            
            search_result = await execute_tavily_search(query, max_results=5)
            tool_result = format_search_result_for_llm(search_result)
            
            # 记录来源（供前端展示引用卡片）
            for r in search_result.get("results", []):
                search_citations.append({
                    "type": "market_data",
                    "angle": research_angle,
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "snippet": r.get("content", "")[:200],
                })
        
        elif action == "search_competitor_intel":
            brand_name = args.get("brand_name", "")
            query = args.get("query", "")
            logger.info("Wacksman 执行竞品情报检索: %s — %s", brand_name, query)
            
            search_result = await execute_tavily_search(query, max_results=4)
            tool_result = f"## 竞品情报：{brand_name}\n" + format_search_result_for_llm(search_result)
            
            for r in search_result.get("results", []):
                search_citations.append({
                    "type": "competitor",
                    "brand": brand_name,
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "snippet": r.get("content", "")[:200],
                })
        
        elif action == "synthesize_research_report":
            # NOTE: synthesize 是终止信号——模型准备好汇总所有数据生成最终报告
            research_summary = args.get("research_summary", "")
            logger.info("Wacksman 进入最终报告生成阶段")
            tool_result = (
                f"[系统] 数据收集完毕。请基于以下研究摘要和上述所有搜索结果，"
                f"生成完整的市场研究报告（Markdown 格式），并附上 <handoff> 交接摘要块。\n\n"
                f"研究摘要：\n{research_summary}"
            )
            
            # 将 tool result 注回 messages，然后让 LLM 生成最终报告
            messages.append({
                "role": "tool",
                "tool_call_id": tool_calls[0].get("id", f"call_{round_num}"),
                "content": tool_result,
            })
            break  # synthesize 后跳出循环，让后续流式生成最终报告
        
        else:
            tool_result = f"[系统] 未知技能: {action}"
        
        # 将 tool 执行结果注回 messages
        messages.append({
            "role": "tool",
            "tool_call_id": tool_calls[0].get("id", f"call_{round_num}"),
            "content": tool_result,
        })
    
    return messages, search_citations


async def run_market_agent(user_prompt: str, handoff_context: str = "") -> str:
    """
    市场研究 Agent（非流式，用于上下文传递）
    """
    messages, _ = await _run_research_loop(user_prompt, handoff_context)
    
    # NOTE: 执行最终报告生成，传入完整的研究历史
    final_report = await call_llm(messages)
    return final_report


async def run_market_agent_stream(
    user_prompt: str, handoff_context: str = ""
) -> AsyncGenerator[str, None]:
    """
    市场研究 Agent（流式）
    
    流程：
    1. 非流式多轮 Tool Call 循环（数据收集阶段，不含实时 token 推送）
    2. 收集完毕后，流式生成最终报告（实时 token 推送）
    
    NOTE: 数据收集阶段（步骤1）不流式，约 15-30 秒静默期属正常现象
    """
    logger.info("Wacksman 开始研究循环（中型模式，最多 %d 轮）...", MAX_RESEARCH_ROUNDS)
    
    messages, search_citations = await _run_research_loop(user_prompt, handoff_context)
    
    logger.info("Wacksman 研究循环完成，检索来源数量: %d。开始流式生成最终报告...", len(search_citations))
    
    # NOTE: 如果有检索来源，在报告后追加引用块
    # 通过特殊标记传递给前端 MarketRenderer 渲染引用卡片
    citations_json = ""
    if search_citations:
        import json as _json
        citations_json = (
            f"\n\n<market_citations>{_json.dumps(search_citations, ensure_ascii=False)}</market_citations>"
        )
    
    # 流式生成最终报告
    async for chunk in call_llm_stream(messages):
        yield chunk
    
    # 追加引用数据块（非流式，一次性发送）
    if citations_json:
        yield citations_json
