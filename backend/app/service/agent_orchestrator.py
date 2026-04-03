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
from app.service.market_agent import _run_research_loop
from app.service.strategy_agent import _run_strategy_loop
from app.service.content_agent import _run_content_loop
from app.service.visual_agent import _run_visual_loop
from app.service.skills.wacksman_skills import execute_tavily_search

logger = logging.getLogger(__name__)

AgentId = Literal["consultant_plan", "market", "strategy", "content", "visual", "consultant_review"]


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

        # NOTE: 共享项目上下文 — 贯穿整个工作流
        project_context: dict = {
            "user_prompt": user_prompt,
            "handoffs": {},      # 各 Agent 的精炼交接摘要
            "full_outputs": {},  # 各 Agent 的完整输出（供 review 引用）
        }

        # NOTE: 先将已落盘的完成输出填充到 project_context，
        # 这样即使不重跑它们，下游 Agent 也能拿到正确的 handoff 数据
        for aid, output in ckpt_outputs.items():
            if output:
                project_context["full_outputs"][aid] = output
                project_context["handoffs"][aid] = _extract_handoff(output)

        # ─── 品牌顾问：需求分析 & 路由诊断（工具先行） ──────────────
        if _is_completed("consultant_plan"):
            # 断点续传：consultant_plan 已落盘，直接重放存档输出（不调用 LLM）
            plan_accumulated = ckpt_outputs["consultant_plan"]
            selected_agents = ckpt_selected  # 复用上次的路由顺序
            logger.info("[RESUME] consultant_plan 已完成，重放存档，路由: %s", selected_agents)
            yield _sse("agent_start", "consultant_plan")
            yield _sse("agent_output", json.dumps({"id": "consultant_plan", "content": plan_accumulated}))
            yield _sse("routing_decided", json.dumps(selected_agents))
            yield _sse("agent_complete", "consultant_plan")
        else:
            yield _sse("agent_start", "consultant_plan")
            logger.info("品牌顾问 — 开始需求诊断...")

            decision = await run_ogilvy_decision(user_prompt, conversation_history)
            action = decision.get("action", "none")
            args = decision.get("args", {})

            if action == "direct_response":
                # NOTE: 轻量咋询直接回复模式：品牌顾问做主语直接流式作答，跳过全部专业 Agent
                response_prompt = args.get("response_prompt", "以首席品牌顾问身份回答用户咋询。")
                logger.info("品牌顾问 — Direct Response 模式，跳过专业 Agent 流水线")

                direct_accumulated = ""
                async for chunk in run_direct_response_stream(user_prompt, response_prompt, conversation_history):
                    direct_accumulated += chunk
                    yield _sse_raw(
                        "agent_chunk",
                        json.dumps({"id": "consultant_plan", "chunk": chunk}, ensure_ascii=False),
                    )

                yield _sse("agent_output", json.dumps({"id": "consultant_plan", "content": direct_accumulated}))
                yield _sse("agent_complete", "consultant_plan")
                # NOTE: 直接回复完成后直接结束会话，无需 review 历程
                yield _sse("routing_decided", json.dumps([]))
                yield _sse("session_complete", json.dumps({"report": direct_accumulated}, ensure_ascii=False))
                logger.info("品牌顾问 Direct Response 完成，输出: %d 字", len(direct_accumulated))
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
                    search_result = execute_tavily_search(query)
                except Exception as e:
                    logger.error("Tavily 搜索失败: %s", e)
                    search_result = "抱歉，由于网络检索服务异常，未能获取最新资讯。"
                
                response_prompt = f"针对用户的问题，基于以下最新互联网检索结果进行解答：\n\n【检索结果】\n{search_result}"
                direct_accumulated = f"> 已为您检索最新资讯：**{query}**\n\n"
                
                async for chunk in run_direct_response_stream(user_prompt, response_prompt, conversation_history):
                    direct_accumulated += chunk
                    yield _sse_raw(
                        "agent_chunk",
                        json.dumps({"id": "consultant_plan", "chunk": chunk}, ensure_ascii=False),
                    )

                yield _sse("agent_output", json.dumps({"id": "consultant_plan", "content": direct_accumulated}))
                yield _sse("agent_complete", "consultant_plan")
                yield _sse("routing_decided", json.dumps([]))
                yield _sse("session_complete", json.dumps({"report": direct_accumulated}, ensure_ascii=False))
                return

            elif action == "export_final_deliverable":
                doc_title = args.get("document_title", "Brand_Consultant_Report")
                logger.info("品牌顾问 — 触发 Export 动作: %s", doc_title)
                
                export_msg = (
                    f"✅ **{doc_title}**\n\n您所需的全案已处理完毕。作为基于文本的智能体系统，"
                    "物理文件生成目前处于开发阶段，您可以稍后在系统的【下载面板】查收结果。"
                )
                
                direct_accumulated = ""
                async for chunk in run_planning_phase_stream(export_msg):
                    direct_accumulated += chunk
                    yield _sse_raw(
                        "agent_chunk",
                        json.dumps({"id": "consultant_plan", "chunk": chunk}, ensure_ascii=False),
                    )

                yield _sse("agent_output", json.dumps({"id": "consultant_plan", "content": direct_accumulated}))
                yield _sse("agent_complete", "consultant_plan")
                yield _sse("routing_decided", json.dumps([]))
                
                # 推送导出完成伪信号
                yield _sse("export_ready", json.dumps({"title": doc_title, "url": f"/api/exports/{doc_title}.pdf"}, ensure_ascii=False))
                yield _sse("session_complete", json.dumps({"report": direct_accumulated}, ensure_ascii=False))
                return

            elif action == "revert_to_checkpoint":
                target_round = args.get("target_round", 1)
                explanation = args.get("explanation", f"好的，系统上下文即将为您回退到历史第 {target_round} 轮的干净状态...")
                logger.info("品牌顾问 — 触发 Revert 动作: 到 Round %s", target_round)
                
                direct_accumulated = ""
                async for chunk in run_planning_phase_stream(explanation):
                    direct_accumulated += chunk
                    yield _sse_raw(
                        "agent_chunk",
                        json.dumps({"id": "consultant_plan", "chunk": chunk}, ensure_ascii=False),
                    )
                    
                yield _sse("agent_output", json.dumps({"id": "consultant_plan", "content": direct_accumulated}))
                yield _sse("agent_complete", "consultant_plan")
                yield _sse("routing_decided", json.dumps([]))
                
                # 给前端发出清空历史的数据指令
                yield _sse("session_revert", json.dumps({"target_round": target_round}, ensure_ascii=False))
                yield _sse("session_complete", json.dumps({"report": direct_accumulated}, ensure_ascii=False))
                return

            elif action == "analyze_uploaded_asset":
                asset_focus = args.get("asset_focus", "多模态素材")
                logger.info("品牌顾问 — 触发 Analyze Uploaded Asset 动作: 重点 %s", asset_focus)
                
                explanation = f"⚠️ [系统截阻：目前前端暂未开放上传通道，但系统已正确识别您意图解析的侧重点 `{asset_focus}`。请尝试用纯文字再次描述。]"
                direct_accumulated = ""
                async for chunk in run_planning_phase_stream(explanation):
                    direct_accumulated += chunk
                    yield _sse_raw(
                        "agent_chunk",
                        json.dumps({"id": "consultant_plan", "chunk": chunk}, ensure_ascii=False),
                    )
                    
                yield _sse("agent_output", json.dumps({"id": "consultant_plan", "content": direct_accumulated}))
                yield _sse("agent_complete", "consultant_plan")
                yield _sse("routing_decided", json.dumps([]))
                yield _sse("session_complete", json.dumps({"report": direct_accumulated}, ensure_ascii=False))
                return

            elif action == "clarify_requirement" or action == "request_human_approval":
                # 走到此处则说明需要阻断当前流水线，向用户发问
                question_text = args.get("question", "您好，为了更好地为您提供服务，请问您能提供更多具体的背景信息吗？")
                logger.info("Ogilvy 中断流水线，发起 %s 动作，发问内容: %s", action, question_text)
                
                plan_accumulated = ""
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

            elif action == "generate_workflow_dag":
                # 得到了完整的 DAG 路由规划
                selected_agents = args.get("routing_sequence", [])
                plan_text = args.get("plan_explanation", "为您制定了以下工作流：")
                logger.info("Ogilvy 输出 DAG: %s", selected_agents)
                
                plan_accumulated = ""
                async for chunk in run_planning_phase_stream(plan_text):
                    plan_accumulated += chunk
                    yield _sse_raw(
                        "agent_chunk",
                        json.dumps({"id": "consultant_plan", "chunk": chunk}, ensure_ascii=False),
                    )
            else:
                # Fallback 降级：走纯旧式的文本输出解析
                content = decision.get("content", "")
                logger.info("Ogilvy 回退至文本解析模式。")

                plan_accumulated = ""
                async for chunk in run_planning_phase_stream(content):
                    plan_accumulated += chunk
                    yield _sse_raw(
                        "agent_chunk",
                        json.dumps({"id": "consultant_plan", "chunk": chunk}, ensure_ascii=False),
                    )
                selected_agents, plan_text = _parse_routing_response(plan_accumulated)

            yield _sse("routing_decided", json.dumps(selected_agents))
            yield _sse("agent_output", json.dumps({"id": "consultant_plan", "content": plan_accumulated}))

            # NOTE: 记录 consultant_plan 的决策文本作为初始 handoff，供后续 Agent 了解宏观计划
            project_context["handoffs"]["consultant_plan"] = plan_text
            project_context["full_outputs"]["consultant_plan"] = plan_accumulated

            yield _sse("agent_complete", "consultant_plan")
            logger.info("路由决策完成：%s", selected_agents)

        # 用于后台执行高耗时的视频生成任务
        video_task = None

        # NOTE: 构造包含多轮历史对话的全局增强提示词
        # 确保所有下游 Agent 能看到前几轮原始需求（特别是本轮输入仅有“继续”时）
        history_text = _build_history_context(conversation_history or [])
        enriched_user_prompt = user_prompt
        if history_text:
            enriched_user_prompt = f"【历史多轮对话上下文】\n{history_text}\n\n====== 本轮用户输入 ======\n{user_prompt}"

        # ─── 动态执行选定的专业 Agent（结构化交接）────────────
        for agent_key in selected_agents:

            if _is_completed(agent_key):
                # 断点续传：该 Agent 已落盘，直接重放存档输出（不调用 LLM）
                saved_output = ckpt_outputs[agent_key]
                logger.info("[RESUME] Agent %s 已完成，重放存档（%d 字）", agent_key, len(saved_output))
                # NOTE: project_context 已在函数开头预填充，此处仅需发出趄价 SSE 让前端显示
                yield _sse("agent_start", agent_key)
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
                stream = run_strategy_agent_stream(enriched_user_prompt, handoff_context)
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
                # 这类 token 不是报告内容，不要累积到 accumulated，而是转发为独立 SSE 事件
                if chunk.startswith(PROGRESS_MARKER):
                    progress_data = chunk[len(PROGRESS_MARKER):]
                    yield _sse_raw(
                        "agent_research_progress",
                        json.dumps({"id": agent_key, "progress": progress_data}, ensure_ascii=False),
                    )
                else:
                    accumulated += chunk
                    yield _sse_raw(
                        "agent_chunk",
                        json.dumps({"id": agent_key, "chunk": chunk}, ensure_ascii=False),
                    )

            # NOTE: 提取 handoff 交接摘要，存入共享上下文
            handoff = _extract_handoff(accumulated)
            project_context["handoffs"][agent_key] = handoff
            project_context["full_outputs"][agent_key] = accumulated

            yield _sse("agent_output", json.dumps({"id": agent_key, "content": accumulated}))
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

        # ─── 品牌顾问：质量审核 & 最终综合报告（流式） ─────────
        if _is_completed("consultant_review"):
            # 断点续传：consultant_review 已落盘，直接重放
            review_accumulated = ckpt_outputs["consultant_review"]
            logger.info("[RESUME] consultant_review 已完成，重放存档（%d 字）", len(review_accumulated))
            yield _sse("agent_start", "consultant_review")
            yield _sse("agent_output", json.dumps({"id": "consultant_review", "content": review_accumulated}))
        else:
            yield _sse("agent_start", "consultant_review")
            logger.info("品牌顾问 — 开始质量审核，生成最终报告")

            review_accumulated = ""
            async for chunk in run_quality_review_stream(
                user_prompt=user_prompt,
                selected_agents=selected_agents,
                project_context=project_context,
            ):
                review_accumulated += chunk
                yield _sse_raw(
                    "agent_chunk",
                    json.dumps({"id": "consultant_review", "chunk": chunk}, ensure_ascii=False),
                )

            yield _sse("agent_output", json.dumps({"id": "consultant_review", "content": review_accumulated}))
            project_context["full_outputs"]["consultant_review"] = review_accumulated

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
        yield _sse("agent_complete", "consultant_review")
        yield _sse("session_complete", json.dumps({"report": review_accumulated}, ensure_ascii=False))
        logger.info("品牌咨询全流程完成，共执行 Agent: %s", selected_agents)
