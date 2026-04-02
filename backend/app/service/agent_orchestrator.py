from __future__ import annotations

import json
import logging
import re
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
    ) -> AsyncGenerator[str, None]:
        """
        执行完整品牌咨询工作流（结构化交接 + 实时流式输出）
        yield 每条符合 text/event-stream 规范的 SSE 事件字符串
        """
        # NOTE: 共享项目上下文 — 贯穿整个工作流
        project_context: dict = {
            "user_prompt": user_prompt,
            "handoffs": {},      # 各 Agent 的精炼交接摘要
            "full_outputs": {},  # 各 Agent 的完整输出（供 review 引用）
        }

        # ─── 品牌顾问：需求分析 & 路由决策（流式） ──────────────
        yield _sse("agent_start", "consultant_plan")
        logger.info("品牌顾问 — 开始需求分析，制定执行计划")

        plan_accumulated = ""
        async for chunk in run_planning_phase_stream(user_prompt, conversation_history or []):
            plan_accumulated += chunk
            yield _sse_raw(
                "agent_chunk",
                json.dumps({"id": "consultant_plan", "chunk": chunk}, ensure_ascii=False),
            )

        # 累积完成后解析路由决策
        selected_agents, plan_text = _parse_routing_response(plan_accumulated)

        yield _sse("routing_decided", json.dumps(selected_agents))
        yield _sse("agent_output", json.dumps({"id": "consultant_plan", "content": plan_text}))
        yield _sse("agent_complete", "consultant_plan")
        logger.info("路由决策完成：%s", selected_agents)

        # 用于后台执行高耗时的视频生成任务
        video_task = None

        # ─── 动态执行选定的专业 Agent（结构化交接）────────────
        for agent_key in selected_agents:
            yield _sse("agent_start", agent_key)
            logger.info("启动 Agent: %s（流式模式）", agent_key)

            accumulated = ""

            # NOTE: 构建下游 Agent 需要的交接上下文
            # 每个 Agent 只接收它需要的前序 handoff，而非全文
            handoff_context = ""
            if agent_key == "market":
                # 市场研究是第一个专业 Agent，不需要前序交接
                stream = run_market_agent_stream(user_prompt)
            elif agent_key == "strategy":
                handoff_context = _build_handoff_context(project_context, ["market"])
                stream = run_strategy_agent_stream(user_prompt, handoff_context)
            elif agent_key == "content":
                handoff_context = _build_handoff_context(project_context, ["market", "strategy"])
                stream = run_content_agent_stream(user_prompt, handoff_context)
            elif agent_key == "visual":
                handoff_context = _build_handoff_context(project_context, ["market", "strategy", "content"])
                stream = run_visual_agent_stream(user_prompt, handoff_context)
            else:
                logger.warning("未知 Agent key: %s，跳过", agent_key)
                continue

            async for chunk in stream:
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

            # NOTE: 美术指导 Agent 完成后，自动触发图片生成，并后台排队等待视频生成
            if agent_key == "visual":
                try:
                    from app.service.image_generator import generate_brand_images
                    logger.info("美术指导 Agent 完成文本输出，开始生成品牌参考图...")
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
                
                try:
                    from app.service.video_generator import generate_brand_video_async
                    logger.info("开始排队并后台生成即梦文生视频...")
                    yield _sse("agent_video_start", "visual")
                    # 使用当前事件循环启动后台任务
                    import asyncio
                    video_task = asyncio.create_task(generate_brand_video_async(accumulated))
                except Exception as e:
                    logger.error("排队即梦视频任务失败: %s", e)

        # ─── 品牌顾问：质量审核 & 最终综合报告（流式） ─────────
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
                import asyncio
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
