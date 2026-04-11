"""
品牌战略 Agent — Trout v4.0

工作流（四层理论体系）：
  Phase -1: 自适应反问 — 评估5个关键信息维度的完整度，针对缺口追问，最多3轮
  Phase  0: 输入组装 — 注入 System Prompt + 用户回答 + Wacksman handoff
  Phase  1: 工具调用循环（max 10轮）
    ① select_applicable_frameworks → 全局规划 theory_combo
    ② analyze_competitive_landscape → Layer 0 竞争分析
    ③ apply_positioning_theory → Layer 1 定位理论
    ④ apply_brand_driver（0-2次）→ Layer 2 驱动力
    ⑤ build_brand_house → 品牌屋（强制）
    ⑥ design_brand_architecture → 可选
    ⑦ generate_naming_candidates → 可选
    ⑧ synthesize_strategy_report → 触发报告，循环结束
  Phase  2: 流式生成 Markdown 品牌战略报告
"""
from __future__ import annotations

import json
import logging
from collections.abc import AsyncGenerator

from app.service.llm_provider import call_llm, call_llm_stream, call_llm_with_tools
from app.service.prompt_loader import load_agent_prompt
from app.service.skills.trout_skills import TROUT_TOOLS, parse_trout_tool_calls
# 复用 Market Agent 的进度常量与机制
from app.service.market_agent import PROGRESS_MARKER

logger = logging.getLogger(__name__)

# ── 常量 ──────────────────────────────────────────────────────
MAX_TOOL_ROUNDS = 10
MAX_CLARIFY_ROUNDS = 3           # 自适应反问最多轮数
SYNTHESIS_TRIGGER = "synthesize_strategy_report"
FRAMEWORK_SELECTOR = "select_applicable_frameworks"

# orchestrator 捕获此前缀后，emit strategy_clarify SSE + session_pause SSE
AGENT_CLARIFY_MARKER = "__AGENT_CLARIFY__:"




def _make_progress(step: str, label: str = "", detail: str = "") -> str:
    """构造进度 token。Orchestrator 读取此格式后转发为 agent_research_progress SSE 事件。"""
    payload = {"step": step, "label": label, "detail": detail}
    return f"{PROGRESS_MARKER}{json.dumps(payload, ensure_ascii=False)}"


# ══════════════════════════════════════════════════════════════
# Phase 1-2：主流程
# ══════════════════════════════════════════════════════════════

async def run_strategy_agent_stream(
    user_prompt: str,
    handoff_context: str,
    clarification_answers: str | None = None,
    clarify_round: int = 0,
    skip_clarify: bool = False,
    patch_instruction: str | None = None,
    old_output: str = "",
    is_micro_task: bool = False,
) -> AsyncGenerator[str, None]:
    """
    品牌战略 Agent 主入口（流式输出）。

    Args:
        user_prompt:             用户的品牌需求原文
        handoff_context:         Wacksman 市场研究 handoff 交接摘要
        clarification_answers:   用户对追问的回答（None 表示尚未追问）
        clarify_round:           当前是第几轮反问（由 orchestrator 传入）

    Yields:
        str: 流式输出的文本 chunk，或以 AGENT_CLARIFY_MARKER 开头的追问信号
    """


    # ─── 统一入口启动 ────────────────────────────────────
    if patch_instruction:
        user_prompt = patch_instruction
        yield _make_progress("start", label="Trout 接收到局部指令，正在推演…")
    else:
        yield _make_progress("start", label="Trout 启动战略规划引擎，准备开始深度推演…")

    # ─── Phase 0：组装输入消息 ────────────────────────────────
    system_prompt = load_agent_prompt("strategy")

    user_content = f"品牌需求/指令：\n{user_prompt}"
    if handoff_context:
        user_content += f"\n\n【市场研究交接（Wacksman）】\n{handoff_context}"
    if clarification_answers:
        user_content += f"\n\n【用户补充信息（战略追问回答）】\n{clarification_answers}"
    if old_output:
        user_content += f"\n\n【已有报告底稿（用于局部修改/热更新参考）】\n{old_output}"

    if is_micro_task:
        task_mode = "modular_task"
        user_content += (
            "\n\n【执行指令】本次属于『单点微缩任务 (Micro-Task)』，你作为品牌战略顾问 Trout 独立作业。\n\n"
            "## 信息充分性原则（最优先）\n"
            "在执行任何工具或输出任何内容之前，请先评估用户的诉求是否包含完成任务所必需的关键信息。\n"
            "如果缺少关键信息（例如：行业/赛道、核心受众、差异化诉求、预算规模、竞争对手等），\n"
            "你必须以 `__AGENT_CLARIFY__:` 作为回复的第一字符，紧跟一段简洁的追问文字，然后立刻停止。\n"
            "不要在追问之后继续输出任何分析或结论！\n\n"
            "## 工具调用原则\n"
            "如果信息充分，请根据用户诉求的意图直接调用「唯一最相关」的单个工具，禁止调用 select_applicable_frameworks：\n"
            "- 品牌屋搭建/重构 → build_brand_house\n"
            "- 核心定位/定位重塑 → apply_positioning_theory\n"
            "- 竞争分析/格局梳理 → analyze_competitive_landscape\n"
            "- 品牌驱动力/传播逻辑 → apply_brand_driver\n"
            "- 命名/Slogan → generate_naming_candidates\n"
            "- 多品牌/业务矩阵 → design_brand_architecture\n"
            "- 即兴问答/无需工具 → 直接以资深顾问口吻极简作答\n\n"
            "绝对禁止：输出完整 Markdown 长文报告 / 调用多个工具进行全案推演。"
        )
    else:
        task_mode = "full_strategy"
        user_content += (
            "\n\n【执行指令】请首先调用 select_applicable_frameworks 识别任务意图。\n"
            "如果处于 full_strategy，请规划 theory_combo 顺序调用理论工具，并以 synthesize_strategy_report 收尾；\n"
            "如果处于 patch，请只需且只能设置 target_tools，严禁调起无关的大盘架构工具！\n"
        )

    messages: list[dict] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]

    # 执行状态追踪
    executed_frameworks: list[str] = []
    theory_combo: dict = {}
    yielded_action_labels: set[str] = set()

    # ─── Phase 1：工具调用循环 ────────────────────────────────
    for round_idx in range(1, MAX_TOOL_ROUNDS + 1):
        logger.info(
            "Trout Phase 1 · Round %d/%d | 已执行: %s",
            round_idx, MAX_TOOL_ROUNDS,
            executed_frameworks or ["无"],
        )

        content, tool_calls = await call_llm_with_tools(
            messages=messages,
            tools=TROUT_TOOLS,
        )
        text_content = (content or "").strip()

        # 情形 A：LLM 调用了工具
        if tool_calls:
            messages.append({
                "role": "assistant",
                "content": text_content or None,
                "tool_calls": tool_calls,
            })

            parsed_results = parse_trout_tool_calls(tool_calls)
            synthesis_triggered = False

            for item in parsed_results:
                tool_name = item["tool_name"]
                result_str = item["result"]
                executed_frameworks.append(tool_name)
                logger.info("Trout 工具执行: %s", tool_name)
                
                action_label = {
                    "select_applicable_frameworks": "构建品牌战略全局规划",
                    "analyze_competitive_landscape": "审视行业竞争格局与心智缝隙",
                    "apply_positioning_theory": "推演核心品牌定位",
                    "apply_brand_driver": "规划品牌传播底层驱动力",
                    "build_brand_house": "搭建严密的品牌屋框架",
                    "design_brand_architecture": "梳理多品牌业务矩阵",
                    "generate_naming_candidates": "碰撞中英文品牌命名建议",
                    "synthesize_strategy_report": "全维定鼎，正在整合战略报告",
                }.get(tool_name, f"执行 {tool_name}")
                
                if action_label not in yielded_action_labels:
                    yield _make_progress(tool_name, label=action_label)
                    yielded_action_labels.add(action_label)

                # 提取 theory_combo 供进度提示使用
                if tool_name == FRAMEWORK_SELECTOR:
                    try:
                        # select_applicable_frameworks 的执行结果是文本摘要，theory_combo 在 args 中
                        # 从 tool_calls 原始 args 中提取
                        for tc in tool_calls:
                            if tc.get("function", {}).get("name") == FRAMEWORK_SELECTOR:
                                raw = tc["function"].get("arguments", "{}")
                                args = json.loads(raw) if isinstance(raw, str) else raw
                                # 只有全案和 patch 会用到这个返回值来覆盖，如果一开始就是 micro_task 则直接保留 modular_task
                                if not is_micro_task:
                                    task_mode = args.get("task_mode", "full_strategy")

                                theory_combo = {
                                    "task_mode": task_mode,
                                    "layer0": args.get("layer0_frameworks", []),
                                    "layer1": args.get("layer1_theory", ""),
                                    "layer2": [d.get("framework_name") for d in args.get("layer2_drivers", [])],
                                    "optional": args.get("optional_tools", []),
                                    "target_tools": args.get("target_tools", [])
                                }
                                logger.info("Trout theory_combo 解析: %s", theory_combo)
                                break
                    except Exception as e:
                        logger.warning("theory_combo 解析失败: %s", e)

                # 将工具结果注入消息历史
                tool_call_id = next(
                    (tc.get("id", "") for tc in tool_calls
                     if tc.get("function", {}).get("name") == tool_name),
                    f"tool_{round_idx}_{tool_name}",
                )
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "content": result_str,
                })

                if tool_name == SYNTHESIS_TRIGGER:
                    synthesis_triggered = True

            if synthesis_triggered:
                logger.info(
                    "Trout 所有工具执行完毕，进入报告生成。序列: %s",
                    " → ".join(executed_frameworks),
                )
                break

            # 注入执行进度提示，帮助 LLM 明确下一步工具
            _inject_progress_hint(messages, executed_frameworks, theory_combo)

        # 情形 B：LLM 直接返回文本（不调用工具）
        elif text_content:
            logger.info("Trout Round %d 直接返回文本，跳出循环", round_idx)
            messages.append({"role": "assistant", "content": text_content})
            break

        # 情形 C：空响应，异常退出
        else:
            logger.warning("Trout Round %d 空响应，终止循环", round_idx)
            break

    # ─── Phase 2：流式输出（报告/对话/补丁） ───────────────────────────────
    executed_display = [
        f for f in executed_frameworks
        if f not in (FRAMEWORK_SELECTOR, SYNTHESIS_TRIGGER)
    ]

    chapter_map = {
        "analyze_competitive_landscape": "一、竞争战略诊断",
        "apply_positioning_theory":      "二、核心品牌定位",
        "apply_brand_driver":            "三、品牌驱动力分析",
        "build_brand_house":             "四、品牌屋",
        "design_brand_architecture":     "五、品牌架构",
        "generate_naming_candidates":    "六、品牌命名建议",
    }
    chapters = [chapter_map[f] for f in executed_display if f in chapter_map]

    if task_mode == "full_strategy":
        messages.append({
            "role": "user",
            "content": (
                f"所有框架分析已完成（{len(executed_display)} 个工具）。\n"
                f"请根据以上分析结果，生成完整的品牌战略 Markdown 报告。\n"
                f"本次需输出章节：{' | '.join(chapters)}。\n"
                "严格按照 strategy.md 报告结构，每章详尽展开，\n"
                "最后附上 <handoff> 标签数据（含传播方向指引和视觉方向指引）。"
            ),
        })
        logger.info("Trout Phase 2 开始流式生成长篇战略报告...")
    else:
        patch_notice = ""
        if task_mode == "patch":
            patch_notice = (
                "\n\n注意：当前为 patch 热更新模式！\n"
                "请将你修改后的具体内容，使用 `<PATCH_BLOCK>` 和 `</PATCH_BLOCK>` 标签紧接在回复中完整输出（如完整段落或最新 JSON 卡片）。\n"
                "标签外的内容会作为陪聊话术。如果被要求修改品牌屋JSON，务必输出完整的 JSON 卡片。不要全盘重写报告全文！"
            )
        messages.append({
            "role": "user",
            "content": (
                f"任务类型 ({task_mode}) 所需的框架分析/推演已完成。\n"
                "请直接以资深品牌顾问的口吻（极其简练、亲切高级，直接切入正题），回复用户的具体诉求或输出修改结果。\n"
                "如果不涉及全盘战略再造，千万不要去写大型 Markdown 报告模板。"
                f"{patch_notice}"
            ),
        })
        logger.info("Trout Phase 2 开始流式生成直接对话与补丁响应 (mode=%s)...", task_mode)

    async for chunk in call_llm_stream(messages):
        yield chunk

    if task_mode == "full_strategy":
        menu_text = (
            "\n\n---\n**核心战略现已成型。** 如果您觉得大方向准确，我们可以直接开始产出物料。\n"
            "请回复序号，让我为您调配下一步团队资源：\n\n"
            "1.同步推演文案与视觉\n"
            "2.策划内容文案\n"
            "3.输出视觉美术\n\n"
            "*(若战略仍需打磨，请直接提出修改要求即可)*\n"
        )
        yield menu_text

    logger.info(
        "Trout 报告生成完成（工具调用共 %d 次）",
        len(executed_frameworks),
    )


# ══════════════════════════════════════════════════════════════
# 内部辅助函数
# ══════════════════════════════════════════════════════════════

def _inject_progress_hint(
    messages: list[dict],
    executed: list[str],
    theory_combo: dict,
) -> None:
    """
    在工具结果后注入执行进度提示，帮助 LLM 明确下一步工具。
    """
    if not theory_combo:
        return

    task_mode = theory_combo.get("task_mode", "full_strategy")
    expected = []
    
    if task_mode in ("modular_task", "patch"):
        expected = list(theory_combo.get("target_tools", []))
    else:
        expected = ["analyze_competitive_landscape", "apply_positioning_theory"]
        for fw in theory_combo.get("layer2", []):
            if fw:
                expected.append("apply_brand_driver")
        expected.append("build_brand_house")
        expected.extend(theory_combo.get("optional", []))
        expected.append("synthesize_strategy_report")

    seen: set[str] = set()
    expected_unique: list[str] = []
    for item in expected:
        if item not in seen:
            seen.add(item)
            expected_unique.append(item)

    remaining = [t for t in expected_unique if t not in executed]
    if not remaining:
        return

    next_tool = remaining[0]
    hint = (
        f"[执行进度] 已完成: {' → '.join(executed)} | "
        f"下一步请调用: {next_tool} | "
        f"待执行: {' → '.join(remaining)}"
    )
    messages.append({"role": "user", "content": hint})
    logger.debug("Trout 进度提示注入: 下一步 = %s, task_mode = %s", next_tool, task_mode)


