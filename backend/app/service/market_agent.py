"""
市场研究 Agent — Wacksman（增强型联网 Agent + 实时进度反馈）

工作流（中型检索模式，5-7 次 API 调用）：
  Phase 1: 研究循环（async generator，边检索边 yield 进度事件）
  Phase 2: 流式生成最终报告
"""
from __future__ import annotations

import json
import logging
import re
from collections.abc import AsyncGenerator
from typing import Union

from app.service.llm_provider import call_llm, call_llm_stream, call_llm_with_tools
from app.service.prompt_loader import load_agent_prompt
from app.service.skills.wacksman_skills import (
    WACKSMAN_TOOLS,
    execute_tavily_search,
    execute_jina_scrape,
    execute_social_review_search,
    format_search_result_for_llm,
    format_jina_result_for_llm,
    parse_wacksman_tool_calls,
    execute_mine_consumer_persona,
    execute_analyze_semantic_sentiment,
    execute_identify_opportunities,
    execute_generate_data_visualization,
)

logger = logging.getLogger(__name__)

# NOTE: 中型检索模式的最大轮次限制，防止无限递归调用
MAX_RESEARCH_ROUNDS = 7

# NOTE: 进度事件特殊前缀，Orchestrator 通过此前缀识别并转发为独立 SSE 事件
# 不会被当作报告文本内容累积到 agent output 中
PROGRESS_MARKER = "\x00WACKSMAN_PROGRESS\x00"

# 各 Tool action 对应的人类可读进度描述
_ACTION_LABELS: dict[str, str] = {
    "clarify_research_scope": "🔍 分析研究范围与边界定义…",
    "web_search_market_data": "📊 联网检索市场规模与消费趋势数据…",
    "search_competitor_intel": "🏆 搜集竞品情报与对标核心维度…",
    "scrape_review_url": "🕷️ 抓取目标商品或帖子评论数据…",
    "search_social_reviews": "💬 抽取全网社媒与口碑真实数据…",
    "mine_consumer_persona": "🧑‍🤝‍🧑 挖掘并结构化目标群体画像…",
    "analyze_semantic_sentiment": "🧠 融合计算语义情感倾向分布…",
    "identify_opportunities": "🎯 识别空白痛点并锚定市场机会…",
    "generate_data_visualization": "📈 综合计算并生成多维数据图表字典…",
    "synthesize_research_report": "✅ 数据大盘收集完毕，正在渲染报告…",
}


def _strip_tool_xml(content: str | None) -> str:
    """清理 DeepSeek XML tool call 内容，防止泄漏或干扰下一步生成"""
    if not content:
        return ""
    # 移除 <|function_calls|>...</|function_calls|> 或 <function_calls>...</function_calls> 块
    content = re.sub(r'<\|?function_calls\|?>.*?</\|?function_calls\|?>', '', content, flags=re.DOTALL)
    # 也清理可能存在的单独的 XML 残留
    content = re.sub(r'<\|?DSML\|?.*?>', '', content)
    return content.strip()

def _make_progress(step: str, detail: str = "") -> str:
    """
    构造进度 token。格式：MARKER + JSON。
    Orchestrator 读取此格式后转发为 agent_research_progress SSE 事件。
    """
    payload = {"step": step, "detail": detail}
    return f"{PROGRESS_MARKER}{json.dumps(payload, ensure_ascii=False)}"


async def _run_research_loop(
    user_prompt: str,
    handoff_context: str,
) -> AsyncGenerator[Union[str, tuple[list[dict], list[dict]]], None]:
    """
    核心研究循环（async generator 版本）：
    边执行工具调用，边 yield 实时进度 token（以 PROGRESS_MARKER 为前缀）。
    循环结束后 yield 一个 tuple 作为最终数据包，供外层提取。

    yield 类型：
      - str（以 PROGRESS_MARKER 开头）：进度事件，由 Orchestrator 转成 SSE
      - tuple[list[dict], list[dict]]：(messages, search_citations)，研究完成的最终数据
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

    search_citations: list[dict] = []

    # 初始进度：开始研究
    yield _make_progress("start", "Wacksman 启动研究引擎，准备调用联网工具…")

    for round_num in range(MAX_RESEARCH_ROUNDS):
        logger.info("Wacksman 研究循环 Round %d/%d", round_num + 1, MAX_RESEARCH_ROUNDS)

        content, tool_calls = await call_llm_with_tools(
            messages=messages,
            tools=WACKSMAN_TOOLS,
        )

        if not tool_calls:
            logger.info("Wacksman 未触发 Tool Call，提前结束研究循环。")
            messages.append({"role": "assistant", "content": content})
            break

        parsed = parse_wacksman_tool_calls(tool_calls)
        if not parsed:
            break

        action = parsed["action"]
        args = parsed["args"]

        # ── 在执行工具前 yield 进度事件 ──
        action_label = _ACTION_LABELS.get(action, f"执行 {action}…")
        detail = ""
        if action == "web_search_market_data":
            detail = args.get("query", "")
        elif action == "search_competitor_intel":
            detail = f"竞品：{args.get('brand_name', '')}"
        elif action == "scrape_review_url":
            detail = f"平台：{args.get('platform', '')} · {args.get('focus', '')}"
        elif action == "search_social_reviews":
            detail = f"{args.get('platform_focus', '')} · {args.get('sentiment_focus', '')} 情感过滤"
        elif action == "mine_consumer_persona":
            detail = f"人群：{args.get('target_audience', '')}"
        elif action == "analyze_semantic_sentiment":
            detail = "提取正负口碑与痛点"
        elif action == "identify_opportunities":
            detail = "计算未满足缺口"
        elif action == "generate_data_visualization":
            detail = f"构建：{args.get('chart_type', 'chart')}"

        yield _make_progress(action, f"{action_label}{'  |  ' + detail if detail else ''}")

        # 将模型的 tool_call 意图追加到 messages
        # NOTE: content 中可能包含 DeepSeek 的 XML 工具调用格式，需要清理
        # 避免这些 XML 片段污染后续的 LLM 上下文，导致最终报告中出现工具调用代码
        clean_content = _strip_tool_xml(content) or None
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
            question = args.get("question", "")
            logger.info("Wacksman 澄清研究范围（基于假设继续）: %s", question)
            tool_result = (
                f"[系统] 研究范围需要澄清：{question}\n"
                "由于无法中断咨询流程，Wacksman 将基于最常见的市场假设继续研究，"
                "并在报告结尾注明此假设。请继续调用搜索工具收集数据。"
            )

        elif action == "web_search_market_data":
            query = args.get("query", "")
            research_angle = args.get("research_angle", "market_size")
            search_result = await execute_tavily_search(query, max_results=5)
            tool_result = format_search_result_for_llm(search_result)
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

        elif action == "scrape_review_url":
            url = args.get("url", "")
            platform = args.get("platform", "other")
            focus = args.get("focus", "")
            jina_result = await execute_jina_scrape(url, platform, focus)
            tool_result = format_jina_result_for_llm(jina_result)
            if jina_result.get("success"):
                search_citations.append({
                    "type": "user_review",
                    "platform": platform,
                    "title": f"{platform.upper()} 用户评价页面",
                    "url": url,
                    "snippet": jina_result.get("content", "")[:200],
                })

        elif action == "search_social_reviews":
            query = args.get("query", "")
            platform_focus = args.get("platform_focus", "cross_platform")
            sentiment_focus = args.get("sentiment_focus", "all")
            search_result = await execute_social_review_search(query, platform_focus, sentiment_focus, max_results=5)
            tool_result = (
                f"## 用户声音检索结果（平台: {platform_focus}，情感倾向: {sentiment_focus}）\n"
                + format_search_result_for_llm(search_result)
            )
            for r in search_result.get("results", []):
                search_citations.append({
                    "type": "social_review",
                    "platform": platform_focus,
                    "sentiment": sentiment_focus,
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "snippet": r.get("content", "")[:200],
                })

        elif action == "mine_consumer_persona":
            target_audience = args.get("target_audience", "")
            core_pain_points = args.get("core_pain_points", [])
            res = await execute_mine_consumer_persona(target_audience, core_pain_points)
            tool_result = json.dumps(res, ensure_ascii=False)

        elif action == "analyze_semantic_sentiment":
            sentiment_summary = args.get("sentiment_summary", "")
            positive_topics = args.get("positive_topics", [])
            negative_topics = args.get("negative_topics", [])
            res = await execute_analyze_semantic_sentiment(sentiment_summary, positive_topics, negative_topics)
            tool_result = json.dumps(res, ensure_ascii=False)

        elif action == "identify_opportunities":
            opportunities_list = args.get("opportunities_list", [])
            res = await execute_identify_opportunities(opportunities_list)
            tool_result = json.dumps(res, ensure_ascii=False)

        elif action == "generate_data_visualization":
            chart_type = args.get("chart_type", "bar")
            intent_description = args.get("intent_description", "")
            res = await execute_generate_data_visualization(chart_type, intent_description)
            tool_result = json.dumps(res, ensure_ascii=False)

        elif action == "synthesize_research_report":
            research_summary = args.get("research_summary", "")
            logger.info("Wacksman 进入最终报告生成阶段")
            tool_result = (
                f"[系统] 数据收集完毕。请基于以下研究摘要和上述所有搜索结果，"
                f"生成完整的市场研究报告（Markdown 格式），并附上 <handoff> 交接摘要块。\n\n"
                f"研究摘要：\n{research_summary}"
            )
            messages.append({
                "role": "tool",
                "tool_call_id": tool_calls[0].get("id", f"call_{round_num}"),
                "content": tool_result,
            })
            break

        else:
            tool_result = f"[系统] 未知技能: {action}"

        messages.append({
            "role": "tool",
            "tool_call_id": tool_calls[0].get("id", f"call_{round_num}"),
            "content": tool_result,
        })

    # NOTE: 研究循环结束后，将最终数据通过 tuple yield 给外层提取
    yield (messages, search_citations)


async def run_market_agent(user_prompt: str, handoff_context: str = "") -> str:
    """
    市场研究 Agent（非流式，用于上下文传递）
    """
    messages: list[dict] = []
    search_citations: list[dict] = []

    async for item in _run_research_loop(user_prompt, handoff_context):
        if isinstance(item, tuple):
            messages, search_citations = item

    final_report = await call_llm(messages)
    return final_report


async def run_market_agent_stream(
    user_prompt: str, handoff_context: str = ""
) -> AsyncGenerator[str, None]:
    """
    市场研究 Agent（流式 + 实时进度反馈）

    流程：
    1. 研究循环 gen：边检索边 yield 进度 token（PROGRESS_MARKER 前缀）
    2. 循环结束，取出 (messages, citations) 数据包
    3. 追加明确的「生成报告」指令，防止 DeepSeek 继续调工具
    4. 流式生成最终报告 token（过滤 XML 工具调用泄漏）
    5. 追加 <market_citations> 引用数据块
    """
    logger.info("Wacksman 开始研究循环（中型模式，最多 %d 轮）...", MAX_RESEARCH_ROUNDS)

    messages: list[dict] = []
    search_citations: list[dict] = []

    async for item in _run_research_loop(user_prompt, handoff_context):
        if isinstance(item, tuple):
            messages, search_citations = item
        else:
            yield item

    logger.info("Wacksman 研究循环完成，来源: %d 条。开始流式生成报告...", len(search_citations))

    # NOTE: 关键修复——在最终流式生成前，追加一条明确的 user 指令
    # DeepSeek 看到 tool_calls 历史后会倾向于继续调工具，
    # 显式 user 消息能打断这一惯性，强制进入报告生成模式
    messages.append({
        "role": "user",
        "content": (
            "所有市场数据已收集完毕。请现在立即根据上述所有研究数据，"
            "用中文撰写完整的市场研究报告（Markdown 格式）。"
            "直接输出报告正文，不要调用任何工具，不要输出 XML 标签，"
            "在报告末尾附上 <handoff> 品牌战略交接摘要块。"
        )
    })

    # 构建引用数据块
    citations_json = ""
    if search_citations:
        citations_json = (
            f"\n\n<market_citations>{json.dumps(search_citations, ensure_ascii=False)}</market_citations>"
        )

    # NOTE: 流式生成时过滤 DeepSeek 工具调用 XML 泄漏
    # 当 buffer 中发现 <|function 或 <function_calls 等标记时，丢弃直到闭合标签
    _xml_buf = ""
    _in_xml = False
    _xml_open_tags = ("<|function_calls|>", "<function_calls>")
    _xml_close_tags = ("<|/function_calls|>", "</function_calls>")

    async for chunk in call_llm_stream(messages):
        if _in_xml:
            # 正在缓冲 XML 块，检查是否已到闭合标签
            _xml_buf += chunk
            if any(tag in _xml_buf for tag in _xml_close_tags):
                _in_xml = False
                _xml_buf = ""
                logger.warning("Wacksman 流式输出中检测并过滤了工具调用 XML 块")
            continue

        # 检测开放标签
        if any(tag in chunk for tag in _xml_open_tags):
            _in_xml = True
            _xml_buf = chunk
            logger.warning("Wacksman 流式输出检测到 XML 工具调用泄漏，开始过滤")
            continue

        yield chunk

    if citations_json:
        yield citations_json
