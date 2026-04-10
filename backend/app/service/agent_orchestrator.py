from __future__ import annotations

import asyncio
import json
import logging
import re
from collections.abc import AsyncGenerator
from typing import Literal

from app.service.consultant_agent import (
    AgentKey,
    run_ogilvy_decision,
    run_planning_phase_stream,
    run_direct_response_stream,
    run_quality_review_stream,
    _parse_routing_response,
    _build_history_context,
)
from app.service.market_agent import run_market_agent_stream, PROGRESS_MARKER
from app.service.strategy_agent import run_strategy_agent_stream
from app.service.content_agent import run_content_agent_stream
from app.service.visual_agent import run_visual_agent_stream
from app.service.skills.wacksman_skills import execute_tavily_search

logger = logging.getLogger(__name__)

AgentId = Literal["consultant_plan", "market", "strategy", "content", "visual", "consultant_review"]

AGENT_CLARIFY_MARKER = "__AGENT_CLARIFY__:"

# ── 防线 1：@提及 显式路由拦截映射表 ──────────────────────────────────────
# NOTE: 用户在输入中使用 @角色名 时，系统跳过 Ogilvy 的推理判断，
# 直接锁死路由到指定 Agent，并强制开启 Micro-Task Lock
_AT_MENTION_MAP: dict[str, str] = {
    # 英文角色名
    "wacksman": "market",
    "trout": "strategy",
    "lois": "content",
    "scher": "visual",
    "ogilvy": "consultant_plan",
    # 中文角色名（即职能名）
    "品牌顾问": "consultant_plan",
    "顾问": "consultant_plan",
    "市场研究": "market",
    "市场": "market",
    "品牌战略": "strategy",
    "战略": "strategy",
    "内容策划": "content",
    "内容": "content",
    "美术指导": "visual",
    "视觉": "visual",
    "美术": "visual",
    # 英文职能名
    "market": "market",
    "strategy": "strategy",
    "content": "content",
    "visual": "visual",
}

# NOTE: 编译正则——匹配 @xxx 格式的显式指令（支持中英文角色名）
_AT_MENTION_RE = re.compile(
    r"@(" + "|".join(re.escape(k) for k in _AT_MENTION_MAP.keys()) + r")(?:\b|\s|$)",
    re.IGNORECASE,
)


def _parse_at_mentions(prompt: str) -> list[str]:
    """
    从用户输入中提取 @提及 的 Agent ID 列表（去重、保序）。
    如果没有 @提及则返回空列表。
    """
    matches = _AT_MENTION_RE.findall(prompt)
    seen: set[str] = set()
    result: list[str] = []
    for m in matches:
        agent_id = _AT_MENTION_MAP.get(m.lower(), "")
        if agent_id and agent_id not in seen and agent_id != "consultant_plan":
            seen.add(agent_id)
            result.append(agent_id)
    return result


# ── 防线 2：Micro-Task Lock 降维封条 ──────────────────────────────────────
# NOTE: 当 is_micro_task=True 时，此指令被强制注入下游所有 Agent 的系统提示词首段，
# 彻底压制长文报告模板，逼迫 Agent 只做精准的单点输出
MICRO_TASK_LOCK = (
    "【⚠️ SYSTEM OVERRIDE: MICRO-TASK LOCK ACTIVATED】\n"
    "长官（系统）在此强制褫夺你的所有默认长文输出模板与宏大叙事习惯！\n"
    "当前你正在执行单点微缩任务（Micro-Task），请以绝对的克制，"
    "【仅针对】用户下面本轮输入中的具体诉求作答！ "
    "能少写绝不多写。\n"
    "不管你的默认职责有多全面，现在必须关闭漫长的铺垫、分析和报告格式，"
    "只准就事论事地给出精简、硬核的结果。\n"
)



def _sse(event: str, data: str) -> str:
    """格式化单条 SSE 事件，换行符转义避免破坏协议格式"""
    return f"event: {event}\ndata: {data.replace(chr(10), chr(92) + 'n')}\n\n"


def _sse_raw(event: str, data: str) -> str:
    """原始 SSE（chunk 内容不做换行转义，直接流式推送）"""
    return f"event: {event}\ndata: {data}\n\n"


# ── Handoff 提取工具 ──────────────────────────────────────────────────────

_HANDOFF_RE = re.compile(r"<handoff>(.*?)</handoff>", re.DOTALL | re.IGNORECASE)


def _extract_handoff(output: str) -> str:
    """
    从 Agent 输出中提取 <handoff>...</handoff> 内容。
    如果 Agent 未生成 handoff 标签，则返回输出的最后 500 字作为降级方案。
    """
    match = _HANDOFF_RE.search(output)
    if match:
        return match.group(1).strip()
    # HACK: 降级 — Agent 忘记生成 handoff 时，截取末尾作为上下文保底
    logger.warning("Agent 未生成 <handoff> 标签，使用降级方案（末尾截取）")
    return output[-500:] if len(output) > 500 else output


def _merge_patch(old_output: str, accumulated: str) -> str:
    """
    解析积木化热更新补丁：从 accumulated 提取 <PATCH_BLOCK> 并合并进旧的文档中。
    如果没匹配到结构化规则，则追加在末尾作为补充。
    """
    import re
    patch_match = re.search(r"<PATCH_BLOCK>(.*?)</PATCH_BLOCK>", accumulated, re.DOTALL)
    if not patch_match:
        return old_output

    patch_content = patch_match.group(1).strip()
    
    # 规则 1：如果补丁是完整的 jsonbrandhouse，替换旧的 jsonbrandhouse
    if "```jsonbrandhouse" in patch_content:
        new_json_block = re.search(r"```jsonbrandhouse[\s\S]*?```", patch_content)
        if new_json_block:
            old_output = re.sub(r"```jsonbrandhouse[\s\S]*?```", new_json_block.group(0), old_output)
            return old_output

    # 规则 2：如果补丁是某个标题块的整体修改 (例如 ## 三、核心定位)
    header_match = re.search(r"^(#{2,4})\s+([^\n]+)", patch_content)
    if header_match:
        header_level = header_match.group(1)
        header_title = header_match.group(2)
        # 在旧文本中寻找相同标题
        pattern = re.compile(rf"^({header_level})\s+{re.escape(header_title)}.*?(?=\n{header_level}\s|\Z)", re.DOTALL | re.MULTILINE)
        if pattern.search(old_output):
            return pattern.sub(patch_content, old_output, count=1)
            
    # Fallback：未知结构，追加说明
    return old_output + "\n\n### 局部更新说明（系统自动合并）\n" + patch_content

async def _stream_text_as_chunks(text: str, chunk_size: int = 8, delay: float = 0.01) -> AsyncGenerator[str, None]:
    """
    将已落盘或内置的文本以打字机效果流式推送。
    """
    for i in range(0, len(text), chunk_size):
        yield text[i : i + chunk_size]
        await asyncio.sleep(delay)



def _build_handoff_context(project_context: dict, agent_keys: list[str]) -> str:
    """
    将指定 Agent 的 handoff 摘要构建为可注入 Prompt 的上下文文本。
    下游 Agent 收到的是精炼的交接摘要，而非上游全文。
    """
    agent_label = {
        "consultant_plan": "品牌顾问（执行计划）",
        "market": "市场研究 Agent",
        "strategy": "品牌战略 Agent",
        "content": "内容策划 Agent",
        "visual": "美术指导 Agent",
    }
    parts: list[str] = []
    handoffs = project_context.get("handoffs", {})
    for key in agent_keys:
        if key in handoffs and handoffs[key]:
            label = agent_label.get(key, key)
            parts.append(f"【{label} · 核心交接】：\n{handoffs[key]}")
    return "\n\n".join(parts)


class AgentOrchestrator:
    """
    品牌咨询 Agent 编排器（结构化交接 + 共享上下文版）

    工作流：
      品牌顾问（需求分析 + 路由决策）
        → 动态选择并运行所需专业 Agent（流式 token 推送）
        → 每个 Agent 输出后提取 handoff 交接摘要
        → 下游 Agent 接收精炼的 handoff 而非全文
        → 品牌顾问（质量审核 + 最终报告，基于 handoff 总览 + 全文引用）
    """

    async def run_session(
        self,
        user_prompt: str,
        conversation_history: list[dict] | None = None,
        checkpoint: dict | None = None,
        attachments: list[str] | None = None,
        strategy_clarification_answers: str | None = None,
        strategy_clarify_round: int = 0,
    ) -> AsyncGenerator[str, None]:
        """
        执行完整品牌咋询工作流（结构化交接 + 实时流式输出）
        yield 每条符合 text/event-stream 规范的 SSE 事件字符串

        Args:
            checkpoint: 略过已完成 Agent 的断点续传数据。
                        所需字段：
                          agent_outputs: dict[agent_id, str]   已落盘的完整输出
                          agent_statuses: dict[agent_id, str]  状态 ('completed'|'running')
                          selected_agents: list[str]           原次路由顺序（拣叭则需需次重新评估）
        """
        # 将 checkpoint 数据转为可查表
        ckpt_outputs: dict[str, str] = (checkpoint or {}).get("agent_outputs", {}) or {}
        ckpt_statuses: dict[str, str] = (checkpoint or {}).get("agent_statuses", {}) or {}
        ckpt_selected: list[str] = (checkpoint or {}).get("selected_agents", []) or []

        def _is_completed(agent_id: str) -> bool:
            """判断该 Agent 在 checkpoint 中是否已完成（有落盘内容且状态为 completed）"""
            return ckpt_statuses.get(agent_id) == "completed" and bool(ckpt_outputs.get(agent_id))

        # NOTE: 如果用户上传了附件，将文件名注入到用户输入前缀内容中，
        # 这样 LLM 返回决策时能感知附件存在，并自然地调用 analyze_uploaded_asset 工具
        effective_prompt = user_prompt
        if attachments:
            filenames = ", ".join(attachments)
            effective_prompt = (
                f"[{len(attachments)}个附件随本次消息一起上传：{filenames}]\n"
                f"请优先调用 analyze_uploaded_asset 工具对这些文件进行分析和信息提取。\n"
                f"用户原始说明：{user_prompt}"
            )
            logger.info("用户上传了 %d 个附件，已注入提示词: %s", len(attachments), filenames)

        # NOTE: 共享项目上下文 — 贯穿整个工作流
        project_context: dict = {
            "user_prompt": effective_prompt,
            "handoffs": {},      # 各 Agent 的精炼交接摘要
            "full_outputs": {},  # 各 Agent 的完整输出（供 review 引用）
        }

        # NOTE: 1. 先从对话历史中（过往轮次）提取最近的 Agent 输出，填充上下文
        # 这样能保障多轮对话中，如果本轮只跑子干路任务（如只跑 strategy），能正确继承上轮的 handoff 避免强制重跑前置依赖
        if conversation_history:
            for round_data in conversation_history:
                history_outputs = round_data.get("agent_outputs", {})
                for aid, output in history_outputs.items():
                    if output and not aid.endswith("_merged"):
                        # 如果存在该模块的合并版本（如 strategy_merged），则优先使用合并版本作为历史真实底稿
                        real_output = history_outputs.get(f"{aid}_merged") or output
                        project_context["full_outputs"][aid] = real_output
                        project_context["handoffs"][aid] = _extract_handoff(real_output)

        # NOTE: 2. 再将本轮已落盘的完成输出填充（覆盖历史），支持当前轮次的断点续传
        for aid, output in ckpt_outputs.items():
            if output and not aid.endswith("_merged"):
                real_output = ckpt_outputs.get(f"{aid}_merged") or output
                project_context["full_outputs"][aid] = real_output
                project_context["handoffs"][aid] = _extract_handoff(real_output)

        # ── 防线 1：@提及 显式拦截（优先级最高，直接跳过 Ogilvy 推理）──────
        explicit_agents = _parse_at_mentions(user_prompt)
        is_micro_task = False  # NOTE: 全局降维标记，贯穿整个流水线

        # ─── 品牌顾问：需求分析 & 路由诊断（工具先行） ──────────────
        if explicit_agents:
            # 场景 0：用户使用 @提及 显式指定 Agent，跳过 Ogilvy 大脑
            selected_agents = explicit_agents
            is_micro_task = True  # NOTE: 显式指定 = 默认强制降维
            logger.info("检测到 @提及 显式路由: %s，强制 is_micro_task=True", selected_agents)

            # 生成极简的过渡话术
            agent_names = "、".join(
                {"market": "Wacksman", "strategy": "Trout",
                 "content": "Lois", "visual": "Scher"}.get(a, a)
                for a in selected_agents
            )
            plan_accumulated = f"收到，直接为您接通 {agent_names}。\n\n"
            yield _sse("agent_start", "consultant_plan")
            yield _sse_raw(
                "agent_chunk",
                json.dumps({"id": "consultant_plan", "chunk": plan_accumulated}, ensure_ascii=False),
            )
            yield _sse("agent_output", json.dumps({"id": "consultant_plan", "content": plan_accumulated}))
            yield _sse("routing_decided", json.dumps(selected_agents))
            yield _sse("agent_complete", "consultant_plan")
            project_context["handoffs"]["consultant_plan"] = plan_accumulated
            project_context["full_outputs"]["consultant_plan"] = plan_accumulated

        elif strategy_clarification_answers:
            # 场景 A：战略追问作答（直达路线）
            logger.info("检测到战略追问交互，跳过前期顾问路由，直通 Strategy Agent 续写")
            selected_agents = ["strategy"]
            # NOTE: 已取消强制依赖解析，直接由核心顾问 Ogilvy 路由。

            yield _sse("routing_decided", json.dumps(selected_agents))
            # 我们故意不下发 agent_start consultant_plan，这样前端就会把它隐藏，从而只显示 Trout
        elif _is_completed("consultant_plan"):
            # 场景 B：断点续传（consultant_plan 已落盘）
            plan_accumulated = ckpt_outputs["consultant_plan"]
            selected_agents = ckpt_selected  # 复用上次的路由顺序
            logger.info("[RESUME] consultant_plan 已完成，流式重放存档，路由: %s", selected_agents)
            yield _sse("agent_start", "consultant_plan")
            # NOTE: 瞬间整块下发，关闭续传时的密集打字碎片流以防 React 重新渲染崩溃
            yield _sse_raw(
                "agent_chunk",
                json.dumps({"id": "consultant_plan", "chunk": plan_accumulated}, ensure_ascii=False),
            )
            yield _sse("agent_output", json.dumps({"id": "consultant_plan", "content": plan_accumulated}))
            yield _sse("routing_decided", json.dumps(selected_agents))
            yield _sse("agent_complete", "consultant_plan")
        else:
            # 场景 C：全新对话（正常启动）
            yield _sse("agent_start", "consultant_plan")
            logger.info("品牌顾问 — 开始初步问候与需求诊断...")

            # NOTE: 将高耗时的 JSON 路由决策放进无阻塞的后台 task
            plan_accumulated = ""
            
            while True:
                decision_task = asyncio.create_task(run_ogilvy_decision(effective_prompt, conversation_history))
                decision = await decision_task
                action = decision.get("action", "none")
                args = decision.get("args", {})

                if action == "conduct_brand_diligence":
                    search_query = args.get("search_query", "品牌全景研究")
                    logger.info("品牌顾问 — 触发前置初调: %s", search_query)
                    diligence_text = args.get("intent_statement", "🔎 收到，让我先快速扫一眼这个品牌的基本面...")
                    if not diligence_text.endswith("..."):
                        diligence_text += "..."
                    diligence_text = f"\n> {diligence_text}\n\n"
                    
                    plan_accumulated += diligence_text
                    yield _sse_raw("agent_chunk", json.dumps({"id": "consultant_plan", "chunk": diligence_text}, ensure_ascii=False))
                    try:
                        search_result = await execute_tavily_search(search_query)
                    except Exception as e:
                        logger.error("初调搜索失败: %s", e)
                        search_result = "搜索暂无确切开源结果或网络异常。"
                    dossier = f"\n[核心参谋部·品牌背调档案]\n全网搜索关键词：{search_query}\n情报摘要：\n{search_result}\n\n"
                    project_context["brand_dossier"] = dossier
                    effective_prompt += f"\n\n{dossier}\n(以上为搜集的最新背景资料，请基于此立刻下发路由或流转)"
                    plan_accumulated += "> 📊 基本盘已摸清。\n\n"
                    yield _sse_raw("agent_chunk", json.dumps({"id": "consultant_plan", "chunk": "> 📊 基本盘已摸清。\n\n"}, ensure_ascii=False))
                    continue

                args = decision.get("args", {})

                if action == "direct_response":
                    # NOTE: 轻量咋询直接回复模式：品牌顾问做主语直接流式作答，跳过全部专业 Agent
                    response_prompt = args.get("response_prompt", "以首席品牌顾问身份回答用户咋询。")
                    logger.info("品牌顾问 — Direct Response 模式，跳过专业 Agent 流水线")

                    async for chunk in run_direct_response_stream(user_prompt, response_prompt, conversation_history):
                        plan_accumulated += chunk
                        yield _sse_raw(
                            "agent_chunk",
                            json.dumps({"id": "consultant_plan", "chunk": chunk}, ensure_ascii=False),
                        )

                    yield _sse("agent_output", json.dumps({"id": "consultant_plan", "content": plan_accumulated}))
                    yield _sse("agent_complete", "consultant_plan")
                    # NOTE: 直接回复完成后直接结束会话，无需 review 历程
                    yield _sse("routing_decided", json.dumps([]))
                    yield _sse("session_complete", json.dumps({"report": plan_accumulated}, ensure_ascii=False))
                    logger.info("品牌顾问 Direct Response 完成，输出: %d 字", len(plan_accumulated))
                    return

                elif action == "lightweight_web_search":
                    # NOTE: 轻量级网页搜索
                    query = args.get("query", "品牌 最新资讯")
                    logger.info("品牌顾问 — 触发 Lightweight Web Search: %s", query)
                    yield _sse_raw(
                        "agent_chunk",
                        json.dumps({"id": "consultant_plan", "chunk": f"🔍 正在检索最新资讯：{query}...\n\n"}, ensure_ascii=False),
                    )
                
                    try:
                        search_result = await execute_tavily_search(query)
                    except Exception as e:
                        logger.error("Tavily 搜索失败: %s", e)
                        search_result = "抱歉，由于网络检索服务异常，未能获取最新资讯。"
                
                    response_prompt = f"针对用户的问题，基于以下最新互联网检索结果进行解答：\\n\\n【检索结果】\\n{search_result}"
                    plan_accumulated += f"\n> 已为您检索最新资讯：**{query}**\n\n"
                
                    # 先把新增的前缀推送显示
                    yield _sse_raw("agent_chunk", json.dumps({"id": "consultant_plan", "chunk": f"\n> 已为您检索最新资讯：**{query}**\n\n"}, ensure_ascii=False))

                    async for chunk in run_direct_response_stream(user_prompt, response_prompt, conversation_history):
                        plan_accumulated += chunk
                        yield _sse_raw(
                            "agent_chunk",
                            json.dumps({"id": "consultant_plan", "chunk": chunk}, ensure_ascii=False),
                        )

                    yield _sse("agent_output", json.dumps({"id": "consultant_plan", "content": plan_accumulated}))
                    yield _sse("agent_complete", "consultant_plan")
                    yield _sse("routing_decided", json.dumps([]))
                    yield _sse("session_complete", json.dumps({"report": plan_accumulated}, ensure_ascii=False))
                    return

                elif action == "export_final_deliverable":
                    doc_title = args.get("document_title", "Brand_Consultant_Report")
                    logger.info("品牌顾问 — 触发 Export 动作: %s", doc_title)
                
                    export_msg = (
                        f"✅ **{doc_title}**\\n\\n您所需的全案已处理完毕。作为基于文本的智能体系统，"
                        "物理文件生成目前处于开发阶段，您可以稍后在系统的【下载面板】查收结果。"
                    )
                
                    async for chunk in run_planning_phase_stream(export_msg):
                        plan_accumulated += chunk
                        yield _sse_raw(
                            "agent_chunk",
                            json.dumps({"id": "consultant_plan", "chunk": chunk}, ensure_ascii=False),
                        )

                    yield _sse("agent_output", json.dumps({"id": "consultant_plan", "content": plan_accumulated}))
                    yield _sse("agent_complete", "consultant_plan")
                    yield _sse("routing_decided", json.dumps([]))
                
                    # 推送导出完成伪信号
                    yield _sse("export_ready", json.dumps({"title": doc_title, "url": f"/api/exports/{doc_title}.pdf"}, ensure_ascii=False))
                    yield _sse("session_complete", json.dumps({"report": plan_accumulated}, ensure_ascii=False))
                    return

                elif action == "revert_to_checkpoint":
                    target_round = args.get("target_round", 1)
                    explanation = args.get("explanation", f"好的，系统上下文即将为您回退到历史第 {target_round} 轮的干净状态...")
                    logger.info("品牌顾问 — 触发 Revert 动作: 到 Round %s", target_round)
                
                    async for chunk in run_planning_phase_stream(explanation):
                        plan_accumulated += chunk
                        yield _sse_raw(
                            "agent_chunk",
                            json.dumps({"id": "consultant_plan", "chunk": chunk}, ensure_ascii=False),
                        )
                    
                    yield _sse("agent_output", json.dumps({"id": "consultant_plan", "content": plan_accumulated}))
                    yield _sse("agent_complete", "consultant_plan")
                    yield _sse("routing_decided", json.dumps([]))
                
                    # 给前端发出清空历史的数据指令
                    yield _sse("session_revert", json.dumps({"target_round": target_round}, ensure_ascii=False))
                    yield _sse("session_complete", json.dumps({"report": plan_accumulated}, ensure_ascii=False))
                    return

                elif action == "analyze_uploaded_asset":
                    asset_focus = args.get("asset_focus", "多模态素材")
                    logger.info("品牌顾问 — 触发 Analyze Uploaded Asset 动作: 重点 %s", asset_focus)
                
                    explanation = f"⚠️ [系统截阻：目前前端暂未开放上传通道，但系统已正确识别您意图解析的侧重点 `{asset_focus}`。请尝试用纯文字再次描述。]"
                    async for chunk in run_planning_phase_stream(explanation):
                        plan_accumulated += chunk
                        yield _sse_raw(
                            "agent_chunk",
                            json.dumps({"id": "consultant_plan", "chunk": chunk}, ensure_ascii=False),
                        )
                    
                    yield _sse("agent_output", json.dumps({"id": "consultant_plan", "content": plan_accumulated}))
                    yield _sse("agent_complete", "consultant_plan")
                    yield _sse("routing_decided", json.dumps([]))
                    yield _sse("session_complete", json.dumps({"report": plan_accumulated}, ensure_ascii=False))
                    return

                elif action == "clarify_requirement" or action == "request_human_approval":
                    # 走到此处则说明需要阻断当前流水线，向用户发问
                    question_text = args.get("question", "您好，为了更好地为您提供服务，请问您能提供更多具体的背景信息吗？")
                    logger.info("Ogilvy 中断流水线，发起 %s 动作，发问内容: %s", action, question_text)
                
                    async for chunk in run_planning_phase_stream(question_text):
                        plan_accumulated += chunk
                        yield _sse_raw(
                            "agent_chunk",
                            json.dumps({"id": "consultant_plan", "chunk": chunk}, ensure_ascii=False),
                        )
                
                    yield _sse("agent_output", json.dumps({"id": "consultant_plan", "content": plan_accumulated}))
                    yield _sse("agent_complete", "consultant_plan")
                    # NOTE: 中断执行，等待用户回答
                    yield _sse("session_pause", json.dumps({"reason": action}))
                    logger.info("工作流已挂起，等待用户输入...")
                    return

                elif action == "delegate_agent_patch":
                    target_agent = args.get("agent", "strategy")
                    task_instruction = args.get("task", "")
                    logger.info(f"Ogilvy 隐形路由至 {target_agent} 执行局部热更新任务: {task_instruction}")
                
                    # 设置上下文中的 patch 指令，后续供该 agent 识别
                    project_context["patch_instruction"] = task_instruction
                    selected_agents = [target_agent]
                
                    # 隐形无感转接：Ogilvy 用极短话术交代，不占用过多视觉
                    plan_accumulated = f"没问题，这就为您进行针对性的调整..."
                    yield _sse_raw(
                        "agent_chunk",
                        json.dumps({"id": "consultant_plan", "chunk": plan_accumulated}, ensure_ascii=False),
                    )
                    plan_handoff = plan_accumulated

                elif action == "generate_workflow_dag":
                    # 得到了完整的 DAG 路由规划
                    selected_agents = args.get("routing_sequence", [])
                    # NOTE: 防线 2 — Ogilvy 自主判断是否为微型任务
                    is_micro_task = args.get("is_micro_task", False)
                    logger.info("Ogilvy 输出 DAG: %s, is_micro_task=%s", selected_agents, is_micro_task)

                    # 将选中的 agent 转换成中文名称给大模型参考
                    agent_names = "、".join(
                        {"market": "市场研究", "strategy": "品牌战略",
                         "content": "内容策划", "visual": "视觉设计"}.get(a, a)
                        for a in selected_agents if a in ["market", "strategy", "content", "visual"]
                    )

                    prompt_explain = (
                        f"你决定启动以下智能体团队处理该需求：{agent_names}。\\n"
                        f"要求：严格遵循【90/10 法则】与【非武断调性】。用高级客户总监的口吻，【不要说任何打招呼的话，直接开门见山】给出一句对该赛道或需求的犀利/幽默洞察作为破冰，然后极其从容自信地交代这几个智能体的分工。这段话就是你作为品牌顾问本次服务的最开场白。"
                    )

                    # 使用真实的流式生成，让大模型一边思考一边吐出解释
                    async for chunk in run_direct_response_stream(user_prompt, prompt_explain, conversation_history):
                        plan_accumulated += chunk
                        yield _sse_raw(
                            "agent_chunk",
                            json.dumps({"id": "consultant_plan", "chunk": chunk}, ensure_ascii=False),
                        )
                    # NOTE: generate_workflow_dag 分支没有独立的 plan_text，
                    # 直接使用 plan_accumulated 作为 handoff 上下文
                    plan_handoff = plan_accumulated
                else:
                    # Fallback 降级：走纯旧式的文本输出解析
                    content = decision.get("content", "")
                    logger.info("Ogilvy 回退至文本解析模式。")

                    async for chunk in run_planning_phase_stream(content):
                        plan_accumulated += chunk
                        yield _sse_raw(
                            "agent_chunk",
                            json.dumps({"id": "consultant_plan", "chunk": chunk}, ensure_ascii=False),
                        )
                    selected_agents_from_text, plan_text = _parse_routing_response(plan_accumulated)
                    # NOTE: fallback 解析出的路由优先级低于工具调用，仅在 selected_agents 未赋值时生效
                    if not selected_agents:  # type: ignore[name-defined]
                        selected_agents = selected_agents_from_text
                    plan_handoff = plan_text
                break

            # ── 路由执行（完全遵循 Ogilvy 的决定，不再强制爬树）────────────

            yield _sse("routing_decided", json.dumps(selected_agents))
            yield _sse("agent_output", json.dumps({"id": "consultant_plan", "content": plan_accumulated}))

            # NOTE: 记录 consultant_plan 的决策文本作为初始 handoff，供后续 Agent 了解宏观计划
            project_context["handoffs"]["consultant_plan"] = plan_handoff
            project_context["full_outputs"]["consultant_plan"] = plan_accumulated

            yield _sse("agent_complete", "consultant_plan")
            logger.info("路由决策完成：%s", selected_agents)

        # 用于后台执行高耗时的视频生成任务
        video_task = None

        # NOTE: 构造包含多轮历史对话的全局增强提示词
        # 确保所有下游 Agent 能看到前几轮原始需求（特别是本轮输入仅有“继续”时）
        history_text = _build_history_context(conversation_history or [])
        enriched_user_prompt = user_prompt
        brand_dossier = project_context.get("brand_dossier", "")
        if history_text or brand_dossier:
            enriched_user_prompt = f"【历史多轮对话上下文】\n{history_text}\n\n"
            if brand_dossier:
                enriched_user_prompt += f"{brand_dossier}\n\n"
            enriched_user_prompt += f"====== 本轮用户输入 ======\n{user_prompt}"

        # ── 防线 2：Micro-Task Lock 降维封条注入 ──────────────────────
        # NOTE: 如果当前 DAG 被标记为微型任务，在所有下游 Agent 的用户输入前
        # 强行拼接降维指令，压制长文输出模板
        micro_task_prefix = MICRO_TASK_LOCK if is_micro_task else ""
        if is_micro_task:
            logger.info("🔒 Micro-Task Lock 已激活，下游所有 Agent 将进入精简输出模式")
            enriched_user_prompt = micro_task_prefix + enriched_user_prompt

        # ─── 动态执行选定的专业 Agent（结构化交接）────────────
        for agent_key in selected_agents:

            if _is_completed(agent_key):
                # 断点续传：以流式打字机效果重放存档输出（不调用 LLM）
                saved_output = ckpt_outputs[agent_key]
                logger.info("[RESUME] Agent %s 已完成，流式重放存档（%d 字）", agent_key, len(saved_output))
                yield _sse("agent_start", agent_key)
                # NOTE: 瞬间整块下发，切掉续传时的碎块推送，完全消除"提交后短暂卡死"的 CPU 毛刺
                yield _sse_raw(
                    "agent_chunk",
                    json.dumps({"id": agent_key, "chunk": saved_output}, ensure_ascii=False),
                )
                yield _sse("agent_output", json.dumps({"id": agent_key, "content": saved_output}))
                yield _sse("agent_complete", agent_key)
                continue

            yield _sse("agent_start", agent_key)
            logger.info("启动 Agent: %s（流式模式）", agent_key)

            accumulated = ""

            # NOTE: 构建下游 Agent 需要的交接上下文
            # 每个 Agent 只接收它需要的前序 handoff，而非全文
            handoff_context = ""
            if agent_key == "market":
                # NOTE: 市场研究是第一个专业 Agent，接收品牌顾问的初步分析作为背景
                handoff_context = _build_handoff_context(project_context, ["consultant_plan"])
                stream = run_market_agent_stream(enriched_user_prompt, handoff_context)
            elif agent_key == "strategy":
                handoff_context = _build_handoff_context(project_context, ["market"])
                is_strategy_rerun = "strategy" in project_context["full_outputs"]
                patch_instr = project_context.get("patch_instruction")
                # 如果是 patch 模式，顺便把旧的 outputs 传给 Trout
                old_strategy_output = project_context["full_outputs"].get("strategy", "") if patch_instr else ""
                
                stream = run_strategy_agent_stream(
                    enriched_user_prompt,
                    handoff_context,
                    clarification_answers=strategy_clarification_answers,
                    clarify_round=strategy_clarify_round,
                    skip_clarify=is_strategy_rerun,
                    patch_instruction=patch_instr,
                    old_output=old_strategy_output,
                )
            elif agent_key == "content":
                handoff_context = _build_handoff_context(project_context, ["market", "strategy"])
                stream = run_content_agent_stream(enriched_user_prompt, handoff_context)
            elif agent_key == "visual":
                handoff_context = _build_handoff_context(project_context, ["market", "strategy", "content"])
                stream = run_visual_agent_stream(enriched_user_prompt, handoff_context)
            else:
                logger.warning("未知 Agent key: %s，跳过", agent_key)
                continue

            async for chunk in stream:
                # NOTE: Wacksman 研究循环会 yield 进度 token（以 PROGRESS_MARKER 为前缀）
                if chunk.startswith(PROGRESS_MARKER):
                    progress_data = chunk[len(PROGRESS_MARKER):]
                    yield _sse_raw(
                        "agent_research_progress",
                        json.dumps({"id": agent_key, "progress": progress_data}, ensure_ascii=False),
                    )
                # NOTE: 通用自适应反问信号 — 发出追问 SSE + 挂起会话
                elif chunk.startswith(AGENT_CLARIFY_MARKER):
                    questions_text = chunk[len(AGENT_CLARIFY_MARKER):]
                    logger.info(f"{agent_key} 发起追问，会话挂起...")
                    # 以打字机效果推送追问文本
                    async for q_chunk in _stream_text_as_chunks(questions_text):
                        yield _sse_raw(
                            "agent_chunk",
                            json.dumps({"id": agent_key, "chunk": q_chunk}, ensure_ascii=False),
                        )
                    # NOTE: 必须在 session_pause 之前发 agent_output，让 sessions.py 的
                    # 持久化逻辑把追问内容写入 DB。否则广播器关闭后追问文本丢失。
                    yield _sse(
                        "agent_output",
                        json.dumps({"id": agent_key, "content": questions_text}, ensure_ascii=False),
                    )
                    yield _sse(
                        "agent_clarify",
                        json.dumps({"id": agent_key, "questions": questions_text}, ensure_ascii=False),
                    )
                    yield _sse("agent_complete", agent_key)
                    yield _sse("session_pause", json.dumps({"reason": f"{agent_key}_clarification"}))
                    logger.info(f"{agent_key} 追问已推送，等待用户回答...")
                    return
                else:
                    accumulated += chunk
                    yield _sse_raw(
                        "agent_chunk",
                        json.dumps({"id": agent_key, "chunk": chunk}, ensure_ascii=False),
                    )

            # NOTE: 提取 handoff 交接摘要，存入共享上下文
            handoff = _extract_handoff(accumulated)
            project_context["handoffs"][agent_key] = handoff
            
            patch_instr = project_context.get("patch_instruction")
            merged_output = None
            if patch_instr and agent_key == "strategy":
                old_strategy_output = project_context["full_outputs"].get(agent_key, "")
                merged_output = _merge_patch(old_strategy_output, accumulated)
                project_context["full_outputs"][agent_key] = merged_output
                ckpt_outputs[agent_key] = merged_output
            else:
                project_context["full_outputs"][agent_key] = accumulated
                ckpt_outputs[agent_key] = accumulated

            payload = {"id": agent_key, "content": accumulated}
            if merged_output is not None:
                payload["merged_content"] = merged_output

            yield _sse("agent_output", json.dumps(payload, ensure_ascii=False))
            yield _sse("agent_complete", agent_key)
            logger.info(
                "Agent %s 完成，输出: %d 字，handoff: %d 字",
                agent_key, len(accumulated), len(handoff),
            )

            # NOTE: 美术指导 Agent 完成后，按需触发多模态生成引擎
            if agent_key == "visual":
                need_image = "<generate_image>True</generate_image>" in accumulated
                need_video = "<generate_video>True</generate_video>" in accumulated

                if need_image:
                    try:
                        from app.service.image_generator import generate_brand_images
                        logger.info("检测到 <generate_image> 标识，开始生成品牌参考图...")
                        images = await generate_brand_images(accumulated, user_prompt)
                        for img in images:
                            yield _sse("agent_image", json.dumps({
                                "id": "visual",
                                "type": img["type"],
                                "data_url": img["data_url"],
                            }))
                        logger.info("品牌参考图生成完成，共 %d 张", len(images))
                    except Exception as e:
                        logger.error("品牌参考图生成失败（不影响主流程）: %s", e)
                
                if need_video:
                    try:
                        from app.service.video_generator import generate_brand_video_async
                        logger.info("检测到 <generate_video> 标识，开始排队生成即梦文生视频...")
                        yield _sse("agent_video_start", "visual")
                        video_task = asyncio.create_task(generate_brand_video_async(accumulated))
                    except Exception as e:
                        logger.error("排队即梦视频任务失败: %s", e)

        # NOTE: 拦截等待视频生成完成（如果尚未完成）
        if video_task:
            try:
                logger.info("等待即梦视频生成任务返回结果...")
                # 为了防止它无限卡死导致无法出结果，加一个总兜底超时
                videos = await asyncio.wait_for(video_task, timeout=605)
                for vid in videos:
                    yield _sse("agent_video", json.dumps({
                        "id": "visual",
                        "type": vid["type"],
                        "data_url": vid["data_url"]
                    }))
                logger.info("即梦视频结果回推完成。")
            except asyncio.TimeoutError:
                logger.error("即梦视频生成等待超时被放弃。")
            except Exception as e:
                logger.error(f"即梦视频生成失败: {e}")

        # 最终通知前端：全程结束
        # 移除自动触发 consultant_review (综合报告)，将最终收尾交给用户手动或后续交互
        yield _sse("session_complete", json.dumps({"report": "策略执行完毕，等待人工打磨或生成终稿"}, ensure_ascii=False))
        logger.info("品牌咨询核心流程完成（暂不生成综合报告），共执行 Agent: %s", selected_agents)
