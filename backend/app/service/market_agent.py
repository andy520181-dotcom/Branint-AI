"""
市场研究 Agent — Wacksman（增强型联网 Agent + 实时进度反馈）

三车道工作流架构：
  ① Full-Research 车道（is_micro_task=False，默认）：
     完整深度研究，5-10 次 API 工具调用，输出完整 Markdown 市场报告 + handoff

  ② Execution 单议题快报车道（is_execution_brief=True）：
     针对单一议题（如某竞品分析/某平台口碑/某赛道机会）精准调1-3个工具，
     输出结构化「单议题快报」（含标题/核心数据/洞察/引用），而非全套研究报告。
     支持信息不足时 AGENT_CLARIFY_MARKER 追问挂起。

  ③ Micro-Task 车道（is_micro_task=True）：
     快速数据查询或轻量研究问题，工具调用后以简洁分析师口吻直接作答，
     不产出正式格式报告。
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
MAX_RESEARCH_ROUNDS = 10

# NOTE: 进度事件特殊前缀，Orchestrator 通过此前缀识别并转发为独立 SSE 事件
# 不会被当作报告文本内容累积到 agent output 中
PROGRESS_MARKER = "\x00WACKSMAN_PROGRESS\x00"

# 各 Tool action 对应的人类可读进度描述
_ACTION_LABELS: dict[str, str] = {
    "clarify_research_scope": "分析研究范围与边界定义…",
    "web_search_market_data": "联网检索市场规模与消费趋势数据…",
    "search_competitor_intel": "搜集竞品情报与对标核心维度…",
    "scrape_review_url": "抓取目标商品或帖子评论数据…",
    "search_social_reviews": "抽取全网社媒与口碑真实数据…",
    "mine_consumer_persona": "挖掘并结构化目标群体画像…",
    "analyze_semantic_sentiment": "融合计算语义情感倾向分布…",
    "identify_opportunities": "识别空白痛点并锚定市场机会…",
    "generate_data_visualization": "综合计算并生成多维数据图表字典…",
    "synthesize_research_report": "数据大盘收集完毕，正在渲染报告…",
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

def _make_progress(step: str, label: str = "", detail: str = "") -> str:
    """
    构造进度 token。格式：MARKER + JSON。
    Orchestrator 读取此格式后转发为 agent_research_progress SSE 事件。

    Args:
        step:   工具 action 名称（用于标识步骤类型）
        label:  步骤标题，对应 _ACTION_LABELS 中的人类可读描述
        detail: 步骤具体细节，如搜索关键词、竞品名称等（可为空）
    """
    payload = {"step": step, "label": label, "detail": detail}
    return f"{PROGRESS_MARKER}{json.dumps(payload, ensure_ascii=False)}"


# NOTE: 社交平台引用质量过滤器，避免 Tavily 返回垃圾结果显示到引用卡片
# 如果搜索结果明显不是有效用户声音页面，则不入库。
_BAD_EXTENSIONS = (".txt", ".pdf", ".csv", ".zip", ".json", ".xml", ".rss", ".atom")
_BAD_TITLE_SIGNALS = ("dict_", "vocab.", "__", "Rss", ".txt", ".pdf")


def _is_valid_social_citation(result: dict) -> bool:
    """
    判断一条 Tavily 搜索结果是否适合作为社交平台引用展示。
    宁缺勿濮：不满足任何一条则返回 False。
    """
    url: str = result.get("url", "").lower()
    title: str = result.get("title", "")
    snippet: str = result.get("content", "")
    score: float = result.get("score", 0.0)

    # 过滤文件类链接（字典、文档、压缩包等）
    if any(url.endswith(ext) for ext in _BAD_EXTENSIONS):
        logger.debug("[Citation过滤] 文件类链接跳过: %s", url)
        return False

    # 过滤标题中包含明显垃圾信号的结果
    if any(sig in title for sig in _BAD_TITLE_SIGNALS):
        logger.debug("[Citation过滤] 垃圾标题跳过: %s", title)
        return False

    # Tavily 相关性分过低说明结果与搜索意图偏差过大
    if score and score < 0.3:
        logger.debug("[Citation过滤] 相关性过低（0.3以下）跳过: %s", url)
        return False

    # snippet 过短或为空（无法呈现有效内容）
    if not snippet or len(snippet.strip()) < 20:
        logger.debug("[Citation过滤] snippet 过短或为空，跳过: %s", url)
        return False

    return True


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
    yield _make_progress("start", label="Wacksman 启动研究引擎，准备调用联网工具…")

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

        yield _make_progress(action, action_label, detail)

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
            logger.info("Wacksman 发起全流程研究范围追问挂起: %s", question)
            # 真正的挂起：使用与 micro_task 一致的挂起标识，供 orchestrator 捕获并中断流程
            yield f"{AGENT_CLARIFY_MARKER}{question}"
            return

        elif action == "web_search_market_data":
            query = args.get("query", "")
            research_angle = args.get("research_angle", "market_size")
            search_result = await execute_tavily_search(query, max_results=15)
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
            search_result = await execute_tavily_search(query, max_results=10)
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
            search_result = await execute_social_review_search(query, platform_focus, sentiment_focus, max_results=15)
            tool_result = (
                f"## 用户声音检索结果（平台: {platform_focus}，情感倾向: {sentiment_focus}）\n"
                + format_search_result_for_llm(search_result)
            )
            for r in search_result.get("results", []):
                # NOTE: 必须通过质量过滤，否则 Tavily 可能返回字典文件、RSS、乱码内容
                if not _is_valid_social_citation(r):
                    continue
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


# NOTE: orchestrator 捕获此前缀后，emit agent_clarify SSE + session_pause SSE
AGENT_CLARIFY_MARKER = "__AGENT_CLARIFY__:"


async def run_market_agent_stream(
    user_prompt: str,
    handoff_context: str = "",
    is_micro_task: bool = False,
    is_execution_brief: bool = False,
) -> AsyncGenerator[str, None]:
    """
    市场研究 Agent（流式 + 实时进度反馈）

    is_micro_task=False, is_execution_brief=False: 全流程深度研究（默认）
    is_execution_brief=True: 单议题快报车道，精准工具调用 + 结构化快报输出
    is_micro_task=True: 轻量微缩任务车道，简洁分析师口吻直接作答
    """
    # ─── Execution 单议题快报车道 ─────────────────────────────
    # NOTE: 优先于 Micro-Task 判断，is_execution_brief 是更重量级的执行路径
    if is_execution_brief:
        logger.info("Wacksman 单议题快报车道启动")
        yield _make_progress("start", label="Wacksman 收到单议题研究指令，准备精准快报作业…")

        system_prompt = load_agent_prompt("market")
        context_block = f"\n\n## 品牌顾问移交的项目背景\n{handoff_context}\n" if handoff_context else ""

        brief_directive = (
            "\n\n[执行指令] 本次属于【单议题快报 (Execution Brief)】任务模式。\n\n"
            "## 信息充分性原则（最优先）\n"
            "在执行工具之前，请先评估是否包含完成快报所必需的关键信息。\n"
            "缺少关键信息时（如议题对象/品类/平台/竞品名称等），"
            "你必须以 `__AGENT_CLARIFY__:` 开头追问，然后立刻停止，不得继续创作。\n\n"
            "## 执行原则\n"
            "如果信息充分，精准调用 1-3 个最相关的工具收集数据，禁止走全流程研究路径。\n"
            "工具调用完成后，以结构化「单议题快报」格式输出，包含：\n"
            "  **📋 [议题名称] 快报** | 研究维度 | 核心数据亮点（3条） | 洞察结论（2-3句）| 数据引用来源\n"
            "快报篇幅控制在 400-600 字，语气：资深研究分析师，克制专业。\n"
            "禁止：输出完整深度研究报告 / 调用 synthesize_research_report 工具。"
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"单议题研究诉求：\n\n{user_prompt}{context_block}{brief_directive}"},
        ]

        search_citations: list[dict] = []
        MAX_BRIEF_ROUNDS = 4  # NOTE: 快报最多调 4 轮工具，控制成本

        for round_num in range(MAX_BRIEF_ROUNDS):
            content, tool_calls = await call_llm_with_tools(
                messages=messages,
                tools=WACKSMAN_TOOLS,
            )
            text_content = (content or "").strip()

            # 情形 A：直接返回文本（追问 or 快报已完成）
            if not tool_calls:
                if text_content.startswith(AGENT_CLARIFY_MARKER):
                    logger.info("Wacksman 单议题快报：信息不足，追问挂起")
                    yield text_content
                else:
                    logger.info("Wacksman 单议题快报 Round %d 文本直出", round_num + 1)
                    yield text_content
                    if search_citations:
                        yield f"\n\n<market_citations>{json.dumps(search_citations, ensure_ascii=False)}</market_citations>"
                return

            # 情形 B：工具调用
            parsed = parse_wacksman_tool_calls(tool_calls)
            if not parsed:
                break

            action = parsed["action"]
            args = parsed["args"]

            # synthesize 是全流程收尾协议，快报车道不触发
            if action == "synthesize_research_report":
                break

            # 处理追问工具
            if action == "clarify_research_scope":
                question = args.get("question", "")
                logger.info("Wacksman 快报：clarify_research_scope 追问 %s", question)
                yield f"{AGENT_CLARIFY_MARKER}{question}"
                return

            action_label = _ACTION_LABELS.get(action, f"执行 {action}…")
            yield _make_progress(action, action_label)

            clean_content = _strip_tool_xml(content) or None
            messages.append({
                "role": "assistant",
                "content": clean_content,
                "tool_calls": [{
                    "id": tool_calls[0].get("id", f"brief_{round_num}"),
                    "type": "function",
                    "function": {"name": action, "arguments": json.dumps(args, ensure_ascii=False)},
                }],
            })

            tool_result = await _execute_single_tool(action, args, round_num, search_citations)
            messages.append({
                "role": "tool",
                "tool_call_id": tool_calls[0].get("id", f"brief_{round_num}"),
                "content": tool_result,
            })

        # 工具循环结束，要求 LLM 输出结构化快报
        messages.append({
            "role": "user",
            "content": (
                "调研数据已收集完画。请现在按「单议题快报」格式，"
                "输出一份结构化、专业的快报文件（400-600字）。\n"
                "格式：**📋 [议题名称] 快报** → 研究维度 → 核心数据亮点（3条）→ 洞察结论（2-3句）→ 数据来源。"
            ),
        })

        async for chunk in call_llm_stream(messages):
            yield chunk

        if search_citations:
            yield f"\n\n<market_citations>{json.dumps(search_citations, ensure_ascii=False)}</market_citations>"
        return

    # ─── Micro-Task 车道 ───────────────────────────────────────
    if is_micro_task:
        logger.info("Wacksman Micro-Task 车道启动")
        yield _make_progress("start", label="Wacksman 收到单点研究指令，准备精准作业…")

        system_prompt = load_agent_prompt("market")
        context_block = f"\n\n## 品牌顾问移交的项目背景\n{handoff_context}\n" if handoff_context else ""

        micro_directive = (
            "\n\n[执行指令] 本次属于【单点微缩任务 (Micro-Task)】。\n\n"
            "## 信息充分性原则（最优先）\n"
            "在执行任何工具或输出任何内容之前，请先评估用户诉求是否包含完成任务所必需的关键信息。\n"
            "如果缺少关键信息（例如：品牌名称/行业赛道/目标市场/竞品名称/关键词等），\n"
            "你必须以 `__AGENT_CLARIFY__:` 作为回复的第一个字符，紧跟一段简洁的追问文字，然后立刻停止。\n"
            "不要在追问之后继续输出任何分析或结论！\n\n"
            "## 工具调用原则\n"
            "如果信息充分，请根据用户诉求的意图选择并调用「直接相关」的工具（可多个），禁止走全流程深度研究路径：\n"
            "- 市场规模/趋势/行业数据 → web_search_market_data\n"
            "- 竞品情报/对标分析 → search_competitor_intel\n"
            "- 用户口碑/社媒声音 → search_social_reviews\n"
            "- 抓取指定页面评论 → scrape_review_url\n"
            "- 目标用户画像/人群画像 → mine_consumer_persona\n"
            "- 情感分析/语义分析 → analyze_semantic_sentiment\n"
            "- 市场机会/空白分析 → identify_opportunities\n"
            "- 数据可视化图表 → generate_data_visualization\n"
            "结果用簡洁专业的市场研究分析师口吻输出，不需要完整深度研究报告。"
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"请对以下诉求进行市场研究分析：\n\n{user_prompt}{context_block}{micro_directive}"},
        ]

        search_citations: list[dict] = []

        # NOTE: micro-task 也允许多轮工具调用，但将轮数设为 5（远小于全流程）
        MAX_MICRO_ROUNDS = 5
        for round_num in range(MAX_MICRO_ROUNDS):
            content, tool_calls = await call_llm_with_tools(
                messages=messages,
                tools=WACKSMAN_TOOLS,
            )
            text_content = (content or "").strip()

            # 情形 A：直接返回文本（追问信号 or 直接对话）
            if not tool_calls:
                if text_content.startswith(AGENT_CLARIFY_MARKER):
                    logger.info("Wacksman Micro-Task 发起追问，会话挂起")
                    yield text_content
                else:
                    logger.info("Wacksman Micro-Task Round %d 直接返回文本", round_num + 1)
                    yield text_content
                return

            # 情形 B：工具调用
            parsed = parse_wacksman_tool_calls(tool_calls)
            if not parsed:
                break

            action = parsed["action"]
            args = parsed["args"]

            # synthesize 工具就是全流程的收皮协议，微缩车道无需调用
            if action == "synthesize_research_report":
                break

            action_label = _ACTION_LABELS.get(action, f"执行 {action}…")
            yield _make_progress(action, action_label)

            clean_content = _strip_tool_xml(content) or None
            messages.append({
                "role": "assistant",
                "content": clean_content,
                "tool_calls": [{
                    "id": tool_calls[0].get("id", f"call_{round_num}"),
                    "type": "function",
                    "function": {"name": action, "arguments": json.dumps(args, ensure_ascii=False)},
                }],
            })

            # 将工具执行结果注入消息历史（复用全流程的执行逻辑）
            tool_result = await _execute_single_tool(action, args, round_num, search_citations)
            messages.append({
                "role": "tool",
                "tool_call_id": tool_calls[0].get("id", f"call_{round_num}"),
                "content": tool_result,
            })

        # NOTE: 微缩任务工具完成后，询问 LLM 直接给出简洁分析结论
        messages.append({
            "role": "user",
            "content": (
                "所需数据已收集完成。请以资深市场研究分析师的口吻，"
                "直接针对用户诉求给出简洁、有价值的分析结论或数据。"
                "不要输出完整的深度研究报告。"
            ),
        })

        async for chunk in call_llm_stream(messages):
            yield chunk

        if search_citations:
            citations_json = json.dumps(search_citations, ensure_ascii=False)
            yield f"\n\n<market_citations>{citations_json}</market_citations>"
        return

    # ─── Full-Research 车道（原有全流程，保持不变）────────────
    logger.info("Wacksman 开始研究循环（中型模式，最多 %d 轮）...", MAX_RESEARCH_ROUNDS)

    messages: list[dict] = []
    search_citations: list[dict] = []

    async for item in _run_research_loop(user_prompt, handoff_context):
        if isinstance(item, tuple):
            messages, search_citations = item
        else:
            yield item

    logger.info("Wacksman 研究循环完成，来源: %d 条。开始流式生成报告...", len(search_citations))

    messages.append({
        "role": "user",
        "content": (
            "所有市场数据已收集完毕。请现在立刻根据上述所有研究数据，"
            "用中文撰写完整的市场研究报告（Markdown 格式）。"
            "直接输出报告正文，不要调用任何工具，不要输出 XML 标签，"
            "在报告末尾附上 <handoff> 品牌战略交接摘要块。"
        )
    })

    citations_json = ""
    if search_citations:
        citations_json = (
            f"\n\n<market_citations>{json.dumps(search_citations, ensure_ascii=False)}</market_citations>"
        )

    _xml_buf = ""
    _in_xml = False
    _xml_open_tags = ("<|function_calls|>", "<function_calls>")
    _xml_close_tags = ("<|/function_calls|>", "</function_calls>")

    async for chunk in call_llm_stream(messages):
        if _in_xml:
            _xml_buf += chunk
            if any(tag in _xml_buf for tag in _xml_close_tags):
                _in_xml = False
                _xml_buf = ""
                logger.warning("Wacksman 流式输出中检测并过滤了工具调用 XML 块")
            continue

        if any(tag in chunk for tag in _xml_open_tags):
            _in_xml = True
            _xml_buf = chunk
            logger.warning("Wacksman 流式输出检测到 XML 工具调用泄漏，开始过滤")
            continue

        yield chunk

    if citations_json:
        yield citations_json


async def _execute_single_tool(
    action: str,
    args: dict,
    round_num: int,
    search_citations: list[dict],
) -> str:
    """
    NOTE: 封装单个工具的执行逻辑，供 Micro-Task 车道复用。
    与 _run_research_loop 中的工具执行逻辑一致，避免重复。
    """
    if action == "web_search_market_data":
        query = args.get("query", "")
        research_angle = args.get("research_angle", "market_size")
        search_result = await execute_tavily_search(query, max_results=15)
        for r in search_result.get("results", []):
            search_citations.append({
                "type": "market_data", "angle": research_angle,
                "title": r.get("title", ""), "url": r.get("url", ""),
                "snippet": r.get("content", "")[:200],
            })
        return format_search_result_for_llm(search_result)

    elif action == "search_competitor_intel":
        brand_name = args.get("brand_name", "")
        query = args.get("query", "")
        search_result = await execute_tavily_search(query, max_results=10)
        for r in search_result.get("results", []):
            search_citations.append({
                "type": "competitor", "brand": brand_name,
                "title": r.get("title", ""), "url": r.get("url", ""),
                "snippet": r.get("content", "")[:200],
            })
        return f"竞品情报：{brand_name}\n" + format_search_result_for_llm(search_result)

    elif action == "search_social_reviews":
        query = args.get("query", "")
        platform_focus = args.get("platform_focus", "cross_platform")
        sentiment_focus = args.get("sentiment_focus", "all")
        search_result = await execute_social_review_search(query, platform_focus, sentiment_focus, max_results=15)
        for r in search_result.get("results", []):
            if _is_valid_social_citation(r):
                search_citations.append({
                    "type": "social_review", "platform": platform_focus, "sentiment": sentiment_focus,
                    "title": r.get("title", ""), "url": r.get("url", ""),
                    "snippet": r.get("content", "")[:200],
                })
        return f"用户声音（{platform_focus}）\n" + format_search_result_for_llm(search_result)

    elif action == "scrape_review_url":
        url = args.get("url", "")
        platform = args.get("platform", "other")
        focus = args.get("focus", "")
        jina_result = await execute_jina_scrape(url, platform, focus)
        if jina_result.get("success"):
            search_citations.append({
                "type": "user_review", "platform": platform,
                "title": f"{platform.upper()} 用户评价页面",
                "url": url, "snippet": jina_result.get("content", "")[:200],
            })
        return format_jina_result_for_llm(jina_result)

    elif action == "mine_consumer_persona":
        res = await execute_mine_consumer_persona(
            args.get("target_audience", ""), args.get("core_pain_points", [])
        )
        return json.dumps(res, ensure_ascii=False)

    elif action == "analyze_semantic_sentiment":
        res = await execute_analyze_semantic_sentiment(
            args.get("sentiment_summary", ""),
            args.get("positive_topics", []),
            args.get("negative_topics", []),
        )
        return json.dumps(res, ensure_ascii=False)

    elif action == "identify_opportunities":
        res = await execute_identify_opportunities(args.get("opportunities_list", []))
        return json.dumps(res, ensure_ascii=False)

    elif action == "generate_data_visualization":
        res = await execute_generate_data_visualization(
            args.get("chart_type", "bar"), args.get("intent_description", "")
        )
        return json.dumps(res, ensure_ascii=False)

    elif action == "clarify_research_scope":
        question = args.get("question", "")
        # 单独工具调用时（如被 patch 触发），返回真正的挂起标志
        return f"{AGENT_CLARIFY_MARKER}{question}"

    return f"[未知工具] {action}"
