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

# NOTE: 与 agent_orchestrator.py 约定的信号前缀
# orchestrator 捕获此前缀后，emit strategy_clarify SSE + session_pause SSE
TROUT_CLARIFY_MARKER = "__TROUT_CLARIFY__:"

# 5个关键信息维度（缺少任何一个都需要追问）
_CLARIFY_DIMENSIONS = [
    ("competitive_landscape", "竞争格局认知（主要竞品/差异认知）"),
    ("target_audience",       "目标人群画像（谁是核心用户/购买频次）"),
    ("brand_maturity",        "品牌成熟阶段（全新/已有基础/多品牌整合）"),
    ("strategic_focus",       "当前战略重心（开市场/抢用户/提溢价/调性升级）"),
    ("market_scope",          "市场地理范围（中国/出海/区域性）"),
]


# ══════════════════════════════════════════════════════════════
# Phase -1：自适应反问机制
# ══════════════════════════════════════════════════════════════

async def _assess_and_clarify(
    user_prompt: str,
    handoff_context: str,
    existing_answers: str,
    clarify_round: int,
) -> str | None:
    """
    评估当前已有信息是否覆盖5个关键维度。
    返回：
      - str：需要追问时，返回追问文本（将被 strategy_agent 加上 MARKER yield 出去）
      - None：信息充足，无需追问，直接放行
    """
    # 构建评估上下文
    info_context = f"用户品牌需求：{user_prompt}"
    if handoff_context:
        info_context += f"\n\n市场研究情报（Wacksman）：{handoff_context}"
    if existing_answers:
        info_context += f"\n\n用户补充回答：{existing_answers}"

    dimensions_desc = "\n".join(
        f"  [{key}] {label}" for key, label in _CLARIFY_DIMENSIONS
    )

    assessment_prompt = (
        f"你是一位品牌战略总架构师（Trout），正在亲自评估以下信息是否足够完成深度的品牌战略分析。\n\n"
        f"当前掌握的信息：\n{info_context}\n\n"
        f"需要覆盖的5个战略关键维度：\n{dimensions_desc}\n\n"
        f"请评估哪些维度信息明显缺失或模糊（无法支撑定位分析）。\n\n"
        f"如果所有维度信息充足，或者已进行了 {clarify_round} 轮追问（上限），"
        f"请回复：SUFFICIENT\n\n"
        f"如果有明显缺失的维度，请回复：QUESTIONS\n[一段连贯的话术]。\n\n"
        f"【追问话术要求——极其核心】：\n"
        f"1. 承接过渡：绝对不能一上来直接生硬提问！开头第一段必须用 1-2 句话点评、总结你刚收到的信息（尤其是 Wacksman 整理的市场研究情报及其核心挑战）。让用户感受到你已经充分理解了前面的市场调研数据。\n"
        f"2. 自然引出：随后使用类似“不过，要为您制定一套更扎实的品牌战略，仅仅看宏观市场还不够，我们还需要针对几个关键内部背景进行探讨……”的口吻引出缺失项。\n"
        f"3. 精准追问：只把重点放在明显缺失的那 1-3 个维度进行提问，语言要像资深商业顾问般亲切专业，不要像机器做问卷般死板。"
    )

    messages = [
        {"role": "system", "content": "你是品牌战略顾问助理，负责评估信息完整度并生成精准追问。"},
        {"role": "user", "content": assessment_prompt},
    ]

    response = await call_llm(messages)
    response = response.strip()

    if response.startswith("SUFFICIENT") or clarify_round >= MAX_CLARIFY_ROUNDS:
        logger.info("Trout 反问评估：信息充足或达到追问上限，放行继续")
        return None

    if response.startswith("QUESTIONS"):
        questions_text = response[len("QUESTIONS"):].strip().lstrip("\n")
        logger.info("Trout 反问 Round %d：发现信息缺口，生成追问", clarify_round + 1)
        return questions_text

    # 兜底：无法识别格式时放行
    logger.warning("Trout 反问评估：无法识别 LLM 响应格式，放行继续")
    return None


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
) -> AsyncGenerator[str, None]:
    """
    品牌战略 Agent 主入口（流式输出）。

    Args:
        user_prompt:             用户的品牌需求原文
        handoff_context:         Wacksman 市场研究 handoff 交接摘要
        clarification_answers:   用户对追问的回答（None 表示尚未追问）
        clarify_round:           当前是第几轮反问（由 orchestrator 传入）

    Yields:
        str: 流式输出的文本 chunk，或以 TROUT_CLARIFY_MARKER 开头的追问信号
    """
    # ─── Phase -1：自适应反问 ────────────────────────────────
    # NOTE: 当 skip_clarify=True (如用户要求重新生成)，或者已有 clarification_answers 时，跳过此阶段
    if not skip_clarify and clarification_answers is None:
        questions = await _assess_and_clarify(
            user_prompt=user_prompt,
            handoff_context=handoff_context,
            existing_answers="",
            clarify_round=clarify_round,
        )
        if questions:
            # NOTE: 发出追问信号，orchestrator 捕获后 emit strategy_clarify SSE + session_pause
            yield f"{TROUT_CLARIFY_MARKER}{questions}"
            return

    # ─── Chat/Patch Mode ────────────────────────────────────
    if patch_instruction:
        yield _make_progress("start", label="Trout 开启闲聊模式，准备为您精修组件…")
        async for chunk in run_strategy_patch_stream(patch_instruction, old_output):
            yield chunk
        return

    yield _make_progress("start", label="Trout 启动战略规划引擎，准备开始深度推演…")

    # ─── Phase 0：组装输入消息 ────────────────────────────────
    system_prompt = load_agent_prompt("strategy")

    user_content = f"品牌需求：\n{user_prompt}"
    if handoff_context:
        user_content += f"\n\n【市场研究交接（Wacksman）】\n{handoff_context}"
    if clarification_answers:
        user_content += f"\n\n【用户补充信息（战略追问回答）】\n{clarification_answers}"

    user_content += (
        "\n\n【执行指令】请首先调用 select_applicable_frameworks 完成全局规划，"
        "输出 theory_combo（包含 Layer 0/1/2 的理论选择），"
        "然后按照规划的顺序依次调用各理论工具，完成所有分析后调用 synthesize_strategy_report。"
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
                                theory_combo = {
                                    "layer0": args.get("layer0_frameworks", []),
                                    "layer1": args.get("layer1_theory", ""),
                                    "layer2": [d.get("framework_name") for d in args.get("layer2_drivers", [])],
                                    "optional": args.get("optional_tools", []),
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

    # ─── Phase 2：流式生成报告 ───────────────────────────────
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

    messages.append({
        "role": "user",
        "content": (
            f"所有框架分析已完成（{len(executed_display)} 个工具）。"
            f"请根据以上分析结果，生成完整的品牌战略 Markdown 报告。"
            f"本次需输出章节：{' | '.join(chapters)}。"
            "严格按照 strategy.md 报告结构，每章详尽展开，"
            "最后附上 <handoff> 标签数据（含传播方向指引和视觉方向指引）。"
        ),
    })

    logger.info("Trout Phase 2 开始流式生成报告（%d 章）...", len(chapters))
    async for chunk in call_llm_stream(messages):
        yield chunk

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
    NOTE: 参考 market_agent.py 的 PROGRESS_MARKER 机制。
    """
    if not theory_combo:
        return

    # 构建完整预期执行序列
    expected = ["analyze_competitive_landscape", "apply_positioning_theory"]
    for fw in theory_combo.get("layer2", []):
        if fw:
            expected.append("apply_brand_driver")
    expected.append("build_brand_house")
    expected.extend(theory_combo.get("optional", []))
    expected.append("synthesize_strategy_report")

    # 去重保持顺序
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
    logger.debug("Trout 进度提示注入: 下一步 = %s", next_tool)

# ══════════════════════════════════════════════════════════════
# Phase 3：局部热更新模式 (Patch Mode)
# ══════════════════════════════════════════════════════════════

async def run_strategy_patch_stream(
    patch_instruction: str,
    old_output: str
) -> AsyncGenerator[str, None]:
    """
    Trout 专属的 Chat & Patch 模式：直接结合旧报告和用户指令，流式输出闲聊及热更新补丁。
    """
    prompt = (
        "你是首席品牌战略架构师 Trout。目前处于【局部热更新 / 闲聊模式】。\n"
        "用户对你之前出具的战略报告提出了新的修改要求或探讨。\n\n"
        f"【用户的修改要求】：\n{patch_instruction}\n\n"
        f"【你之前生成的完整报告底稿】：\n{old_output}\n\n"
        "【回复要求——极其重要】：\n"
        "1. 首段闲聊：用极其简练、亲切高级的合伙人口吻（切勿打招呼，单刀直入）以普通文本形式回复用户的诉求。例如“已收到，我把愿景部分修饰得更具攻击性了：”。\n"
        "2. 补丁输出：把你修改后的具体内容，使用 `<PATCH_BLOCK>` 和 `</PATCH_BLOCK>` 标签紧接在回复中输出。\n"
        "   - 注意：如果用户要求修改品牌屋，请直接在补丁标签内输出完整的最新 ```jsonbrandhouse ... ``` 卡片。\n"
        "   - 注意：如果修改的是某个Markdown模块（例如口号），请在补丁内输出该完整段落。\n"
        "   - 注意：不在标签里的内容会被视为陪聊文字展示给用户，标签内部的内容将在后台被精调合并进总档。\n"
    )
    
    messages = [
        {"role": "system", "content": "你是资深品牌战略专家 Trout，当前处于直接对话与积木化热更新模式。"},
        {"role": "user", "content": prompt}
    ]
    
    async for chunk in call_llm_stream(messages):
        yield chunk
