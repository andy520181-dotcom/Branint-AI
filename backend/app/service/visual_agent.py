"""
美术指导 Agent — Scher

工作流（路径 A：纯净文本流）：
  图像和视频的生成已从 Agent 输出流中彻底剥离，
  改由用户在前端的视觉资产区中显式点击按钮触发。

  Scher 的核心职责收窄为：以最顶尖的美术指导口吻，
  输出完整的品牌视觉策略——色彩体系、字体规范、构图语法，
  以及足够精准的设计方向描述，
  让设计师和用户有清晰的执行锚点。
"""
from __future__ import annotations

import logging
import json
from collections.abc import AsyncGenerator

from app.config import settings
from app.service.llm_provider import call_llm_stream
from app.service.prompt_loader import load_agent_prompt

logger = logging.getLogger(__name__)

# NOTE: 保留 Marker 常量供 orchestrator 解析层兼容（即使本 Agent 不再主动生成媒体）
AGENT_CLARIFY_MARKER = "__AGENT_CLARIFY__:"
PROGRESS_MARKER = "\x00WACKSMAN_PROGRESS\x00"
RECOMMENDATION_MARKER = "\x00ASSET_REC\x00"


def _make_progress(step: str, label: str = "") -> str:
    payload = {"step": step, "label": label, "detail": ""}
    return f"{PROGRESS_MARKER}{json.dumps(payload, ensure_ascii=False)}"


async def run_visual_agent_stream(
    user_prompt: str,
    handoff_context: str,
    is_micro_task: bool = False,
) -> AsyncGenerator[str, None]:
    """
    美术指导 Agent 主入口（纯文本流式输出）。

    Args:
        user_prompt:      用户的视觉诉求或品牌信息
        handoff_context:  上游 Agent（品牌顾问、战略、市场）的交接摘要
        is_micro_task:    True = 单点快速输出模式（简洁）；False = 全案视觉规范模式

    Yields:
        str: 流式输出的文本 chunk，或以 AGENT_CLARIFY_MARKER 开头的追问信号
    """
    system_prompt = load_agent_prompt("visual")
    context_block = f"\n\n## 上游交接背景\n{handoff_context}\n" if handoff_context else ""

    yield _make_progress("start", label="Scher 正在研读品牌档案，构建视觉语言体系…")

    # NOTE: 根据任务类型注入不同的输出指令
    # is_micro_task = 用户单点发起（比如"给我写一段配色方向"），简洁精炼
    # 完整模式 = 作为全案流程的一环，输出完整的视觉规范报告
    if is_micro_task:
        output_directive = (
            "你处于单兵作战模式。"
            "直接以资深美术指导的口吻给出精炼的视觉方向建议，"
            "不超过200字，不用写 Markdown 标题框架，只要核心洞察即可。"
        )
    else:
        output_directive = (
            "请以全球顶尖美术指导的口吻，基于上游交接的品牌背景，"
            "输出完整的品牌视觉策略报告，涵盖：\n"
            "1. 色彩体系（主色 / 辅色 / 情绪校准）\n"
            "2. 字体规范（中英文字体选型逻辑与层级）\n"
            "3. 构图与图像语法（留白哲学、几何语言、质感取向）\n"
            "4. 品牌视觉人格总结（一句话定义视觉基因）\n\n"
            "保持真人对话的流式节奏，有洞察、有温度，绝不像机器人在汇报清单。"
            "不要提及“图片已生成”或任何与 AI 工具调用有关的话语。"
        )

    stream_messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": (
                f"{context_block}\n\n"
                f"用户诉求：{user_prompt}\n\n"
                f"【输出要求】{output_directive}"
            )
        }
    ]

    yield _make_progress("typing", label="Scher 正在亲笔书写全案视觉准则…")

    # NOTE: 并行启动一个小任务，动态分析用户诉求并给出适合的交付按钮清单
    # 这样主文案流式输出不会被阻塞，几乎不增加整体耗时
    import asyncio
    from app.service.llm_provider import call_llm_with_tools
    
    async def _fetch_recommendations():
        recommend_tool = {
            "type": "function",
            "function": {
                "name": "recommend_assets",
                "description": "基于当前的诉求和背景，推荐 1-3 个最值得生成的视觉设计交付物组合。注意，如果是纯文字规划，也可以推荐适合承载文字的视觉包装类型（如：汇报幻灯片）",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "recommendations": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "type": {"type": "string", "enum": ["logo", "poster", "banner", "digital_ad", "packaging", "presentation"], "description": "资产类型，影响构建生图 prompt 时的纵横比与底层风格"},
                                    "label": {"type": "string", "description": "按钮上显示给用户看的文字，需要带渲染感，如 '生成极简Logo'、'包装概念图' 等"},
                                    "count": {"type": "integer", "description": "推荐默认一次生成的张数，建议 1-2"}
                                },
                                "required": ["type", "label", "count"]
                            }
                        }
                    },
                    "required": ["recommendations"]
                }
            }
        }
        rec_messages = [
            {
                "role": "system",
                "content": (
                    "你是一位拥有敏锐商业嗅觉的美术指导，请根据用户的只言片语与品牌档案，"
                    "判断其最迫切需要什么形式的具体视觉资产来佐证方案。"
                    "最多推荐 3 个，按优先级排列。"
                    "注意：如果用户未提供品牌背景，直接根据请求内容判断。"
                )
            },
            {
                "role": "user",
                # NOTE: 单兵模式下 handoff_context 为空字符串；
                # 此时用 user_prompt 填充品牌背景字段，确保推荐 LLM 有足够判断依据，
                # 而不是面对空白上下文触发无意义的兜底
                "content": (
                    f"品牌背景：\n{handoff_context or '用户未提供品牌背景，请直接根据请求内容分析'}\n\n"
                    f"用户请求：\n{user_prompt}\n"
                )
            }
        ]
        try:
            _, t_calls = await call_llm_with_tools(
                rec_messages,
                tools=[recommend_tool],
                tool_choice={"type": "function", "function": {"name": "recommend_assets"}},
                model=settings.default_model
            )
            if t_calls:
                args = json.loads(t_calls[0]["function"]["arguments"])
                recs = args.get("recommendations", [])
                if recs:  # 成功得到非空推荐，直接返回
                    return recs
        except Exception as e:
            logger.warning(f"动态生成推荐资产失败: {e}")

        # NOTE: 智能兜底 —— 基于用户请求关键词判断，
        # 比固定返回 logo+海报 准确得多
        prompt_lower = user_prompt.lower()
        if any(kw in prompt_lower for kw in ["logo", "标志", "图标"]):
            return [
                {"type": "logo", "label": "生成极简 Logo", "count": 2},
                {"type": "banner", "label": "生成品牌 Banner", "count": 1},
            ]
        elif any(kw in prompt_lower for kw in ["poster", "海报", "宣传", "作海报"]):
            return [
                {"type": "poster", "label": "生成品牌海报 ×2", "count": 2},
                {"type": "banner", "label": "生成横幅宣传图", "count": 1},
            ]
        elif any(kw in prompt_lower for kw in ["packaging", "包装", "产品"]):
            return [
                {"type": "packaging", "label": "生成包装概念图", "count": 1},
                {"type": "poster", "label": "生成产品宣传海报", "count": 1},
            ]
        elif any(kw in prompt_lower for kw in ["ppt", "汇报", "presentation", "幻灯片"]):
            return [
                {"type": "presentation", "label": "生成品牌汇报封面", "count": 1},
                {"type": "banner", "label": "生成配套封面图", "count": 1},
            ]
        elif any(kw in prompt_lower for kw in ["banner", "横幅", "广告", "投放"]):
            return [
                {"type": "banner", "label": "生成数字广告 Banner ×2", "count": 2},
                {"type": "digital_ad", "label": "生成小红书竖版广告", "count": 1},
            ]
        else:
            # 完全未识别关键词，返回最通用的 logo+poster 组合
            return [
                {"type": "logo", "label": "生成品牌主视觉 Logo", "count": 1},
                {"type": "poster", "label": "生成品牌视觉海报", "count": 1},
            ]


    rec_task = asyncio.create_task(_fetch_recommendations())

    async for chunk in call_llm_stream(stream_messages, model=settings.default_model):
        yield chunk

    # 流式文本结束后，获取并行计算的推荐列表并利用 Marker 发送
    recs = await rec_task
    yield f"{RECOMMENDATION_MARKER}{json.dumps(recs, ensure_ascii=False)}"

    logger.info("Scher 纯文本视觉策略与动态推荐按键输出完成")


async def run_visual_agent(user_prompt: str, handoff_context: str) -> str:
    """非流式入口（仅作 fallback，正式链路请使用 run_visual_agent_stream）"""
    return "Scher 当前仅支持流式调用，请使用 run_visual_agent_stream。"
