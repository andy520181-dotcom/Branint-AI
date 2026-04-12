"""
Trout Agent（品牌战略专家）核心功能库 v5.0

工作流（四层理论体系 · 已对齐 strategy.md）：
  Phase -1: 自适应反问（在 strategy_agent.py 中实现，非工具）
  Phase  0: Input Assembly（消息组装）
  Phase  1: Tool Loop（工具调用循环）
    ① select_applicable_frameworks  — 全局规划，输出 theory_combo
    ② apply_layer0_macro_strategy   — Layer 0：宏观大盘（波特/蓝海/聚焦/安索夫）
    ③ apply_layer1_industry_os      — Layer 1：行业底座引擎（华为五看/Brand Key/奥美大理想/黄金圈）
    ④ apply_layer2_positioning      — Layer 2：心智定位尖刀（特劳特/里斯/STP）
    ⑤ apply_layer3_brand_identity   — Layer 3：身份血肉包装（12原型/Kapferer/Aaker/CBBE）按需 0-2次
    ⑥ build_brand_house             — 【强制】品牌屋（5层系统收拢模型）
    ⑦ design_brand_architecture     — 可选，品牌架构
    ⑧ generate_naming_candidates    — 可选，命名方案
    ⑨ synthesize_strategy_report    — 【强制最后】触发报告
"""
from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════
# 1. TROUT_TOOLS — JSON Schema 定义
# ══════════════════════════════════════════════════════════════

TROUT_TOOLS: list[dict] = [

    # ─── ① 全局规划（元路由）──────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "select_applicable_frameworks",
            "description": (
                "【必须第一步调用】读取用户补充信息和 Wacksman 市场研究交接，"
                "规划本次战略执行的完整理论组合（theory_combo）。"
                "输出包含 L0宏观大盘 / L1行业底座 / L2心智定位 / L3身份包装 四层理论选择和可选工具清单。"
                "强制必跑的工具：build_brand_house 和 synthesize_strategy_report。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "task_mode": {
                        "type": "string",
                        "enum": ["full_strategy", "modular_task", "patch"],
                        "description": "识别任务意图，决定走哪条执行路径。全案流必须为 full_strategy，单点微小需求为 modular_task，售后热更新为 patch。",
                    },
                    "target_tools": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "仅在 task_mode='modular_task' 或 'patch' 时大模型自主填写。按需精准选择要调用的底层工具（可以为空数组）",
                    },
                    "brand_scenario": {
                        "type": "string",
                        "enum": [
                            "new_brand_startup",
                            "brand_repositioning",
                            "brand_architecture_design",
                            "brand_identity_refresh",
                            "naming_focused",
                            "comprehensive_strategy",
                        ],
                        "description": "识别到的品牌项目场景类型",
                    },
                    "scenario_diagnosis": {
                        "type": "string",
                        "description": "判断该场景的依据（2-3句，引用用户原文关键信息）",
                    },
                    # Layer 0 · 宏观大盘（战略方向选择）
                    "layer0_frameworks": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": ["porter_competitive", "blue_ocean", "focus_strategy", "ansoff_matrix"],
                        },
                        "description": (
                            "【full_strategy】Layer 0 宏观大盘框架，按场景选1-2个："
                            "竞争激烈→porter_competitive；需找蓝海→blue_ocean；"
                            "聚焦细分→focus_strategy；增长方向不明→ansoff_matrix"
                        ),
                    },
                    # Layer 1 · 行业底座引擎（按行业类型选一个）
                    "layer1_industry_engine": {
                        "type": "string",
                        "enum": [
                            "huawei_five_views",
                            "brand_key",
                            "ogilvy_big_ideal",
                            "golden_circle",
                        ],
                        "description": (
                            "【full_strategy】Layer 1 行业底座引擎，必须且只能选1个："
                            "科技/B2B/制造→huawei_five_views；"
                            "快消/日化/食品→brand_key；"
                            "文化/服饰/奢品→ogilvy_big_ideal；"
                            "创新颠覆/技术初创→golden_circle；"
                            "通用找增长→huawei_five_views"
                        ),
                    },
                    "layer1_rationale": {
                        "type": "string",
                        "description": "选择该行业底座引擎的原因（1-2句话）",
                    },
                    # Layer 2 · 心智定位尖刀（必选1个）
                    "layer2_positioning_theory": {
                        "type": "string",
                        "enum": ["trout_positioning", "ries_positioning", "stp_positioning"],
                        "description": (
                            "【full_strategy】Layer 2 心智定位理论，必须且只能选1个："
                            "竞争激烈找差异化→trout_positioning；"
                            "需创造/画新品类→ries_positioning；"
                            "新市场细分→stp_positioning"
                        ),
                    },
                    # Layer 3 · 身份血肉包装（按需选 0-2 个）
                    "layer3_brand_identity": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "identity_type": {
                                    "type": "string",
                                    "enum": ["archetype", "brand_prism", "brand_equity", "brand_personality"],
                                },
                                "framework_name": {
                                    "type": "string",
                                    "description": (
                                        "具体框架名："
                                        "archetype→jung_12_archetypes；"
                                        "brand_prism→kapferer_prism；"
                                        "brand_equity→aaker_identity/keller_cbbe/yr_bav/ogilvy_honeycomb；"
                                        "brand_personality→jung_aaker_personality"
                                    ),
                                },
                                "rationale": {"type": "string", "description": "选用理由（1句）"},
                            },
                            "required": ["identity_type", "framework_name", "rationale"],
                        },
                        "description": "【full_strategy】Layer 3 身份血肉包装，按需选 0-2 个（奢品必加 kapferer_prism）",
                    },
                    "optional_tools": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": ["design_brand_architecture", "generate_naming_candidates"],
                        },
                        "description": "可选工具：有多品牌架构需求→design_brand_architecture；有命名需求→generate_naming_candidates",
                    },
                    "priority_emphasis": {
                        "type": "string",
                        "description": "本次项目的最高战略优先级（一句话，指导后续分析侧重）",
                    },
                },
                "required": [
                    "task_mode", "brand_scenario", "scenario_diagnosis", "priority_emphasis"
                ],
            },
        },
    },

    # ─── ② Layer 0：宏观大盘分析 ──────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "apply_layer0_macro_strategy",
            "description": (
                "Layer 0 宏观大盘分析。根据 select_applicable_frameworks 规划的 layer0_frameworks，"
                "执行波特竞争战略、蓝海战略、聚焦战略或安索夫增长矩阵中的1-2个分析。"
                "本工具输出宏观竞争方向和增长路径，为 Layer 1 行业底座选型提供战略前提。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    # 波特竞争战略（可选）
                    "porter_strategy": {
                        "type": "string",
                        "enum": ["cost_leadership", "differentiation", "focus_cost", "focus_differentiation"],
                        "description": "波特竞争战略选择（仅在规划中包含 porter_competitive 时填写）",
                    },
                    "porter_rationale": {
                        "type": "string",
                        "description": "选择该竞争战略的原因和执行要点",
                    },
                    # 蓝海战略（可选）
                    "blue_ocean_eliminate": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "蓝海四步-剔除：行业中哪些要素应该剔除？",
                    },
                    "blue_ocean_reduce": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "蓝海四步-减少：哪些要素应该大幅减少？",
                    },
                    "blue_ocean_raise": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "蓝海四步-增加：哪些要素应该大幅提升？",
                    },
                    "blue_ocean_create": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "蓝海四步-创造：哪些行业从未有的要素应该被创造？",
                    },
                    # 聚焦战略（可选）
                    "focus_target_segment": {
                        "type": "string",
                        "description": "聚焦战略-目标细分市场（精准描述聚焦的垂直领域/人群/场景）",
                    },
                    "focus_advantage": {
                        "type": "string",
                        "description": "聚焦战略-聚焦后的核心竞争优势",
                    },
                    # 安索夫矩阵（可选）
                    "ansoff_direction": {
                        "type": "string",
                        "enum": ["market_penetration", "product_development", "market_development", "diversification"],
                        "description": "安索夫矩阵增长方向",
                    },
                    "ansoff_rationale": {
                        "type": "string",
                        "description": "选择该增长方向的原因和关键策略",
                    },
                    # 综合结论
                    "macro_conclusion": {
                        "type": "string",
                        "description": "Layer 0 整体宏观战略结论（2-3句，明确竞争方式和增长方向，为 L1 行业底座选型提供依据）",
                    },
                },
                "required": ["macro_conclusion"],
            },
        },
    },

    # ─── ③ Layer 1：行业底座引擎（四大行业框架统一入口）────────
    {
        "type": "function",
        "function": {
            "name": "apply_layer1_industry_os",
            "description": (
                "Layer 1 行业底座引擎。根据 select_applicable_frameworks 选定的 layer1_industry_engine，"
                "执行对应的行业底座框架分析。"
                "engine_type=huawei_five_views → 华为五看（看市场/客户/竞争/自身/机会）+ 三定（定方向/目标/策略）；"
                "engine_type=brand_key → 联合利华 Brand Key（目标消费者/竞争环境/洞察/利益/信任状/个性/精髓）；"
                "engine_type=ogilvy_big_ideal → 奥美大理想（文化张力+品牌真相→大理想宣言）；"
                "engine_type=golden_circle → 西蒙·斯涅克黄金圈（WHY→HOW→WHAT）。"
                "仅填写与选定引擎对应的参数组，其他参数留空。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "engine_type": {
                        "type": "string",
                        "enum": ["huawei_five_views", "brand_key", "ogilvy_big_ideal", "golden_circle"],
                        "description": "与 select_applicable_frameworks 输出的 layer1_industry_engine 一致",
                    },
                    "brand_name": {"type": "string", "description": "品牌名称"},
                    # ── 华为五看三定参数组 ──
                    "hw_look_market": {"type": "string", "description": "【华为五看】看市场：市场规模、增速、阶段判断"},
                    "hw_look_customer": {"type": "string", "description": "【华为五看】看客户：目标客户需求与痛点分析"},
                    "hw_look_competition": {"type": "string", "description": "【华为五看】看竞争：竞争对手格局与差距分析"},
                    "hw_look_self": {"type": "string", "description": "【华为五看】看自身：自身核心能力与短板"},
                    "hw_look_opportunity": {"type": "string", "description": "【华为五看】看机会：可抓取的战略机会窗口"},
                    "hw_define_direction": {"type": "string", "description": "【华为三定】定方向：战略方向选择"},
                    "hw_define_target": {"type": "string", "description": "【华为三定】定目标：可量化的战略目标"},
                    "hw_define_strategy": {"type": "string", "description": "【华为三定】定策略：达成目标的核心举措"},
                    # ── 联合利华 Brand Key 参数组 ──
                    "bk_target_consumer": {"type": "string", "description": "【Brand Key】目标消费者：最精准的核心人群画像"},
                    "bk_competitive_context": {"type": "string", "description": "【Brand Key】竞争环境：主要竞品及市场格局"},
                    "bk_consumer_insight": {"type": "string", "description": "【Brand Key】消费者洞察：最核心的一句消费者 insight"},
                    "bk_functional_benefit": {"type": "string", "description": "【Brand Key】功能利益：品牌给消费者带来的最核心功能利益"},
                    "bk_emotional_benefit": {"type": "string", "description": "【Brand Key】情感利益：品牌带来的情感价值"},
                    "bk_rtb": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "【Brand Key】信任状 RTB（Reasons to Believe），2-4个核心支撑点",
                    },
                    "bk_brand_personality": {"type": "string", "description": "【Brand Key】品牌个性（3-5个形容词）"},
                    "bk_brand_essence": {"type": "string", "description": "【Brand Key】品牌精髓（一句话，最内核的灵魂）"},
                    # ── 奥美大理想参数组 ──
                    "oi_cultural_tension": {"type": "string", "description": "【大理想】文化张力：社会/文化层面存在的矛盾或未解决的紧张关系"},
                    "oi_brand_truth": {"type": "string", "description": "【大理想】品牌真相：品牌最真实的，与文化张力产生共鸣的核心事实"},
                    "oi_big_ideal": {"type": "string", "description": "【大理想】大理想宣言：品牌希望为世界带来什么改变（一句话，充满张力）"},
                    "oi_role_in_culture": {"type": "string", "description": "【大理想】品牌在文化中扮演的角色"},
                    # ── 黄金圈参数组 ──
                    "gc_why": {"type": "string", "description": "【黄金圈】WHY：品牌存在的信念与根本目的（最内圈）"},
                    "gc_how": {"type": "string", "description": "【黄金圈】HOW：实现信念的独特方法与差异化路径"},
                    "gc_what": {"type": "string", "description": "【黄金圈】WHAT：品牌对外提供的产品或服务（最外圈）"},
                    "gc_purpose_statement": {"type": "string", "description": "【黄金圈】综合 Purpose 宣言（凝练整个黄金圈的一句话）"},
                    # 通用结论
                    "layer1_conclusion": {
                        "type": "string",
                        "description": "Layer 1 行业底座核心结论（2-3句），以及如何为 Layer 2 心智定位提供底座支撑",
                    },
                },
                "required": ["engine_type", "brand_name", "layer1_conclusion"],
            },
        },
    },

    # ─── ④ Layer 2：心智定位尖刀（多理论统一入口）─────────────
    {
        "type": "function",
        "function": {
            "name": "apply_layer2_positioning",
            "description": (
                "Layer 2 核心品牌定位分析。根据 select_applicable_frameworks 选定的 layer2_positioning_theory，"
                "执行对应的定位理论及其子模型。"
                "theory_type=trout_positioning → 定位三角模型 + 定位四步法；"
                "theory_type=ries_positioning → 品类创新四步 + 定位四象限；"
                "theory_type=stp_positioning → 市场细分矩阵 + 定位地图。"
                "仅填写与选定理论对应的参数组，其他参数留空。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "theory_type": {
                        "type": "string",
                        "enum": ["trout_positioning", "ries_positioning", "stp_positioning"],
                        "description": "与 select_applicable_frameworks 输出的 layer1_theory 一致",
                    },
                    "brand_name": {"type": "string", "description": "品牌名称"},
                    "core_positioning_statement": {
                        "type": "string",
                        "description": "核心定位语（所有理论通用）：[品牌名]是面向[目标人群]的[品类]，能够[核心利益]，不同于竞争对手，因为[差异化支撑点]",
                    },
                    # ── 特劳特定位理论参数组 ──
                    "trout_target_market": {"type": "string", "description": "【特劳特】定位三角-目标市场描述"},
                    "trout_main_competitors": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "【特劳特】定位三角-主要竞争对手（2-4个）",
                    },
                    "trout_own_advantage": {"type": "string", "description": "【特劳特】定位三角-自身核心优势"},
                    "trout_mind_position": {"type": "string", "description": "【特劳特】心智定位占位（抢占哪个词/概念）"},
                    "trout_differentiation": {"type": "string", "description": "【特劳特】差异化主张USP（一句话）"},
                    "trout_category_leadership": {"type": "string", "description": "【特劳特】品类第一策略"},
                    "trout_trust_builder": {"type": "string", "description": "【特劳特】定位四步法-信任状建立策略"},
                    "trout_communication_strategy": {"type": "string", "description": "【特劳特】定位四步法-传播定位策略"},
                    # ── 里斯定位理论参数组 ──
                    "ries_new_category_name": {"type": "string", "description": "【里斯】品类创新-新品类名称定义"},
                    "ries_focus_strategy": {"type": "string", "description": "【里斯】聚焦策略（聚焦于哪个单一优势领域）"},
                    "ries_visual_hammer": {"type": "string", "description": "【里斯】视觉锤方向（强化品牌定位的视觉符号）"},
                    "ries_pr_launch": {"type": "string", "description": "【里斯】公关启动策略（先用公关建立可信度）"},
                    "ries_quadrant_position": {
                        "type": "string",
                        "enum": ["leader", "challenger", "follower", "nicher"],
                        "description": "【里斯】定位四象限位置：领导者/挑战者/跟随者/补缺者",
                    },
                    # ── STP经典定位参数组 ──
                    "stp_segmentation_vars": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "【STP】市场细分变量（如人口/地理/行为/心理维度）",
                    },
                    "stp_target_segment": {"type": "string", "description": "【STP】目标市场画像（精准描述）"},
                    "stp_positioning_statement": {"type": "string", "description": "【STP】定位语（基于目标市场的精准定位语）"},
                    "stp_map_axis_x": {"type": "string", "description": "【STP】定位地图X轴维度"},
                    "stp_map_axis_y": {"type": "string", "description": "【STP】定位地图Y轴维度"},
                    "stp_map_brand_position": {"type": "string", "description": "【STP】品牌在定位地图中的坐标位置描述"},
                },
                "required": ["theory_type", "brand_name", "core_positioning_statement"],
            },
        },
    },

    # ─── ⑤ Layer 3：身份血肉包装（统一入口）──────────────────
    {
        "type": "function",
        "function": {
            "name": "apply_layer3_brand_identity",
            "description": (
                "Layer 3 品牌身份血肉包装。根据 select_applicable_frameworks 选定的 layer3_brand_identity，"
                "每次调用执行一个身份包装框架（最多调用2次）。"
                "identity_type 决定分析类别，framework_name 决定具体框架。"
                "archetype 类：12大品牌原型（必加，Jung + Aaker五维度）；"
                "brand_prism 类：Kapferer 品牌棱镜（奢品/文化品必加）；"
                "brand_equity 类：品牌资产积累（Aaker识别/CBBE/BAV/奥美蜂巢）；"
                "brand_personality 类：品牌性格系统（Jung原型+Aaker五维度深度版）。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "identity_type": {
                        "type": "string",
                        "enum": ["archetype", "brand_prism", "brand_equity", "brand_personality"],
                        "description": "身份包装类别",
                    },
                    "framework_name": {
                        "type": "string",
                        "description": (
                            "具体框架名称。"
                            "archetype→jung_12_archetypes；"
                            "brand_prism→kapferer_prism；"
                            "brand_equity→aaker_identity/keller_cbbe/yr_bav/brand_promise/ogilvy_honeycomb；"
                            "brand_personality→jung_aaker_personality"
                        ),
                    },
                    # 品牌身份构建参数（brand_identity类通用）
                    "identity_core_essence": {"type": "string", "description": "【身份构建】品牌核心精髓/本质定义"},
                    "identity_personality_traits": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "【身份构建】品牌个性特征关键词（3-5个）",
                    },
                    # Aaker 品牌识别系统特有参数
                    "aaker_product_dimension": {"type": "string", "description": "【Aaker】品牌作为产品的核心属性"},
                    "aaker_org_dimension": {"type": "string", "description": "【Aaker】品牌作为组织的文化特质"},
                    "aaker_person_dimension": {"type": "string", "description": "【Aaker】品牌作为人的个性特征"},
                    "aaker_symbol_dimension": {"type": "string", "description": "【Aaker】品牌作为符号的视觉/隐喻"},
                    # Kapferer 品牌棱镜特有参数
                    "kapferer_physique": {"type": "string", "description": "【Kapferer】物质特征（外在形象）"},
                    "kapferer_personality": {"type": "string", "description": "【Kapferer】品牌个性（语气/风格）"},
                    "kapferer_culture": {"type": "string", "description": "【Kapferer】文化（背后的价值体系）"},
                    "kapferer_relationship": {"type": "string", "description": "【Kapferer】关系（与消费者的互动方式）"},
                    "kapferer_reflection": {"type": "string", "description": "【Kapferer】反射（消费者使用品牌的外在形象）"},
                    "kapferer_self_image": {"type": "string", "description": "【Kapferer】自我认知（消费者使用后的内心感受）"},
                    # 奥美蜂巢模型特有参数
                    "honeycomb_core_value": {"type": "string", "description": "【蜂巢】核心价值"},
                    "honeycomb_personality": {"type": "string", "description": "【蜂巢】品牌个性"},
                    "honeycomb_facts": {"type": "string", "description": "【蜂巢】支撑事实"},
                    "honeycomb_benefits": {"type": "string", "description": "【蜂巢】消费者利益"},
                    "honeycomb_values": {"type": "string", "description": "【蜂巢】价值观"},
                    "honeycomb_essence": {"type": "string", "description": "【蜂巢】品牌精髓"},
                    # 品牌资产积累参数（brand_equity类）
                    # Keller CBBE
                    "cbbe_salience": {"type": "string", "description": "【CBBE】品牌识别/显著性"},
                    "cbbe_performance": {"type": "string", "description": "【CBBE】品牌表现（功能层）"},
                    "cbbe_imagery": {"type": "string", "description": "【CBBE】品牌形象（情感层）"},
                    "cbbe_judgments": {"type": "string", "description": "【CBBE】品牌判断（质量/信任/相关）"},
                    "cbbe_feelings": {"type": "string", "description": "【CBBE】品牌感受（情绪反应）"},
                    "cbbe_resonance": {"type": "string", "description": "【CBBE】品牌共鸣（忠诚度/社群）"},
                    # Y&R BAV
                    "bav_differentiation": {"type": "string", "description": "【BAV】差异性分析"},
                    "bav_relevance": {"type": "string", "description": "【BAV】相关性分析"},
                    "bav_esteem": {"type": "string", "description": "【BAV】尊重度分析"},
                    "bav_knowledge": {"type": "string", "description": "【BAV】认知度分析"},
                    "bav_brand_strength": {"type": "string", "description": "【BAV】品牌强度=差异性×相关性结论"},
                    "bav_brand_stature": {"type": "string", "description": "【BAV】品牌高度=尊重度×认知度结论"},
                    # 品牌承诺模型
                    "promise_functional": {"type": "string", "description": "【承诺模型】功能性承诺"},
                    "promise_emotional": {"type": "string", "description": "【承诺模型】情感性承诺"},
                    "promise_self_expressive": {"type": "string", "description": "【承诺模型】自我表达性承诺"},
                    # 品牌个性参数（brand_personality类）
                    "jung_primary_archetype": {
                        "type": "string",
                        "enum": [
                            "innocent", "sage", "explorer", "outlaw", "magician", "hero",
                            "lover", "jester", "everyman", "caregiver", "ruler", "creator",
                        ],
                        "description": "【Jung】品牌主原型",
                    },
                    "jung_secondary_archetype": {"type": "string", "description": "【Jung】品牌副原型（可选）"},
                    "jung_archetype_application": {"type": "string", "description": "【Jung】原型在内容和视觉中的应用方向"},
                    "aaker_sincerity": {"type": "number", "description": "【Aaker五维度】真诚度（1-5分）"},
                    "aaker_excitement": {"type": "number", "description": "【Aaker五维度】激动度（1-5分）"},
                    "aaker_competence": {"type": "number", "description": "【Aaker五维度】能力感（1-5分）"},
                    "aaker_sophistication": {"type": "number", "description": "【Aaker五维度】精致度（1-5分）"},
                    "aaker_ruggedness": {"type": "number", "description": "【Aaker五维度】粗犷度（1-5分）"},
                    "personality_summary": {"type": "string", "description": "【个性】品牌性格系统综合描述"},
                    # 使命驱动参数（mission_driven类）
                    "golden_circle_why": {"type": "string", "description": "【黄金圆】WHY-品牌存在的信念和目的"},
                    "golden_circle_how": {"type": "string", "description": "【黄金圆】HOW-实现信念的核心方法"},
                    "golden_circle_what": {"type": "string", "description": "【黄金圆】WHAT-提供的产品/服务"},
                    # 通用分析结论
                    "identity_conclusion": {
                        "type": "string",
                        "description": "本次身份包装分析的核心结论（2-3句），以及如何赋予品牌有血有肉的个性与识别度",
                    },
                },
                "required": ["identity_type", "framework_name", "identity_conclusion"],
            },
        },
    },

    # ─── ⑤ build_brand_house（强制必选）────────────────────────
    {
        "type": "function",
        "function": {
            "name": "build_brand_house",
            "description": (
                "【强制必选】构建 Unilever 品牌屋模型，定义品牌承诺、三大战略支柱、"
                "使命/愿景/价值观，以及品牌语气指南。"
                "品牌屋是所有战略输出的集成框架，必须在 apply_positioning_theory 之后调用。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "brand_promise": {
                        "type": "string",
                        "description": "品牌承诺（屋顶），一句话统领品牌的核心，须简洁有力、可持续兑现",
                    },
                    "pillar_1": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "description": {"type": "string"},
                            "proof_points": {"type": "array", "items": {"type": "string"}},
                        },
                        "required": ["name", "description", "proof_points"],
                        "description": "品牌第一支柱",
                    },
                    "pillar_2": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "description": {"type": "string"},
                            "proof_points": {"type": "array", "items": {"type": "string"}},
                        },
                        "required": ["name", "description", "proof_points"],
                        "description": "品牌第二支柱",
                    },
                    "pillar_3": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "description": {"type": "string"},
                            "proof_points": {"type": "array", "items": {"type": "string"}},
                        },
                        "required": ["name", "description", "proof_points"],
                        "description": "品牌第三支柱",
                    },
                    "mission": {"type": "string", "description": "品牌使命"},
                    "vision": {"type": "string", "description": "品牌愿景"},
                    "values": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "品牌价值观（3-5条）",
                    },
                    "brand_is": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "品牌调性：品牌是什么样的（3个形容词）",
                    },
                    "brand_is_not": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "品牌调性：品牌不是什么（禁忌调性，3个）",
                    },
                },
                "required": [
                    "brand_promise", "pillar_1", "pillar_2", "pillar_3",
                    "mission", "vision", "values", "brand_is", "brand_is_not",
                ],
            },
        },
    },

    # ─── ⑥ design_brand_architecture（可选）───────────────────
    {
        "type": "function",
        "function": {
            "name": "design_brand_architecture",
            "description": (
                "可选工具：品牌架构模型决策。仅在用户有多产品线、子品牌或集团架构整合需求时调用。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "recommended_model": {
                        "type": "string",
                        "enum": ["branded_house", "house_of_brands", "endorsed_brands", "hybrid"],
                        "description": "推荐架构模型",
                    },
                    "rationale": {"type": "string", "description": "选择该模型的原因"},
                    "architecture_hierarchy": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "品牌层级结构（从母品牌到子品牌）",
                    },
                    "extension_strategy": {"type": "string", "description": "未来品牌延伸策略建议"},
                },
                "required": ["recommended_model", "rationale", "architecture_hierarchy", "extension_strategy"],
            },
        },
    },

    # ─── ⑦ generate_naming_candidates（可选）──────────────────
    {
        "type": "function",
        "function": {
            "name": "generate_naming_candidates",
            "description": "可选工具：品牌命名候选方案。仅在用户有命名需求时调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "naming_strategy": {
                        "type": "string",
                        "enum": ["descriptive", "associative", "abstract", "founder", "acronym", "hybrid"],
                        "description": "命名策略类型",
                    },
                    "candidates": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "rationale": {"type": "string"},
                                "trademark_risk": {"type": "string", "enum": ["low", "medium", "high"]},
                            },
                            "required": ["name", "rationale", "trademark_risk"],
                        },
                        "description": "候选品牌名列表（3-5个）",
                    },
                    "top_recommendation": {"type": "string", "description": "首选推荐名"},
                    "recommendation_reason": {"type": "string", "description": "首选推荐理由"},
                },
                "required": ["naming_strategy", "candidates", "top_recommendation", "recommendation_reason"],
            },
        },
    },

    # ─── ⑨ synthesize_strategy_report（强制最后步骤）──────────
    {
        "type": "function",
        "function": {
            "name": "synthesize_strategy_report",
            "description": (
                "【强制最后步骤】在所有框架工具调用完毕后调用。"
                "汇总本次执行的所有框架结果（Layer 0/1/2/3），触发最终战略报告的流式生成。"
                "同时提供下游 handoff 数据要点。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "executed_frameworks": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "本次实际执行的工具列表（按执行顺序）",
                    },
                    "layer0_conclusion": {"type": "string", "description": "Layer 0 宏观大盘分析核心结论"},
                    "layer1_conclusion": {"type": "string", "description": "Layer 1 行业底座引擎核心结论"},
                    "layer2_conclusion": {"type": "string", "description": "Layer 2 心智定位核心结论（含定位语）"},
                    "layer3_conclusion": {"type": "string", "description": "Layer 3 身份血肉包装核心结论（无则填'未执行'）"},
                    "brand_house_summary": {"type": "string", "description": "品牌屋核心内容摘要（品牌承诺+三大支柱名称）"},
                    # Handoff 数据（供下游 Agent 使用）
                    "handoff_positioning_statement": {"type": "string", "description": "完整定位语"},
                    "handoff_usp": {"type": "string", "description": "核心差异化主张USP"},
                    "handoff_brand_promise": {"type": "string", "description": "品牌承诺"},
                    "handoff_personality_keywords": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "品牌个性关键词（5个）",
                    },
                    "handoff_communication_direction": {"type": "string", "description": "给Lois的传播方向指引"},
                    "handoff_visual_direction": {"type": "string", "description": "给Scher的视觉方向指引"},
                    "report_ready": {
                        "type": "boolean",
                        "description": "是否准备好生成报告（所有必选框架完成后才能为true）",
                    },
                },
                "required": [
                    "executed_frameworks", "layer0_conclusion", "layer1_conclusion",
                    "layer2_conclusion", "brand_house_summary",
                    "handoff_positioning_statement", "handoff_usp", "handoff_brand_promise",
                    "handoff_personality_keywords", "handoff_communication_direction",
                    "handoff_visual_direction", "report_ready",
                ],
                # NOTE: layer3_conclusion 非强制，L3可能未执行
            },
        },
    },

    # ─── ⑨ plan_communication_strategy（可选）────────────────
    {
        "type": "function",
        "function": {
            "name": "plan_communication_strategy",
            "description": (
                "可选工具：品牌传播策略规划。当用户提出传播方向、媒介策略、内容方向、"
                "品牌声音等诉求时调用。输出核心传播主张、触点矩阵和内容方向指引。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "core_message": {
                        "type": "string",
                        "description": "核心传播主张（一句话，基于品牌定位提炼，所有内容围绕此展开）",
                    },
                    "target_audience_summary": {
                        "type": "string",
                        "description": "目标受众核心画像描述（简洁，1-2句）",
                    },
                    "communication_phases": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "phase": {"type": "string", "description": "阶段名称（如：认知期/考虑期/转化期）"},
                                "objective": {"type": "string", "description": "该阶段传播目标"},
                                "key_message": {"type": "string", "description": "该阶段核心信息"},
                                "channels": {"type": "array", "items": {"type": "string"}, "description": "推荐触点渠道"},
                            },
                            "required": ["phase", "objective", "key_message", "channels"],
                        },
                        "description": "分阶段传播路径（2-3个阶段）",
                    },
                    "content_pillars": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "内容支柱主题（3-4个，指导内容方向）",
                    },
                    "brand_voice_guide": {
                        "type": "string",
                        "description": "品牌声音指南（语气、措辞风格、禁用表达）",
                    },
                    "kpi_framework": {
                        "type": "string",
                        "description": "建议衡量传播效果的核心 KPI 框架（如：品牌认知度/NPS/内容互动率）",
                    },
                },
                "required": ["core_message", "target_audience_summary", "communication_phases", "content_pillars"],
            },
        },
    },

    # ─── ⑩ design_gtm_strategy（可选）────────────────────────
    {
        "type": "function",
        "function": {
            "name": "design_gtm_strategy",
            "description": (
                "可选工具：品牌/产品上市策略（Go-To-Market）。当用户提出新品牌上市、"
                "产品发布、进入新市场等诉求时调用。输出上市路径、渠道策略、定价方向和阶段里程碑。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "gtm_objective": {
                        "type": "string",
                        "description": "上市核心目标（如：12个月内获取首批1000个付费用户）",
                    },
                    "gtm_model": {
                        "type": "string",
                        "enum": ["direct_sales", "channel_partner", "product_led", "community_led", "hybrid"],
                        "description": "GTM 模式：直销/渠道伙伴/产品驱动/社群驱动/混合",
                    },
                    "beachhead_market": {
                        "type": "string",
                        "description": "滩头阵地市场（最小初始目标市场，集中资源首先攻克的细分）",
                    },
                    "pricing_strategy": {
                        "type": "string",
                        "enum": ["penetration", "premium", "freemium", "value_based", "subscription"],
                        "description": "定价策略：渗透定价/溢价定价/免费增值/价值定价/订阅制",
                    },
                    "pricing_rationale": {"type": "string", "description": "定价策略选择原因"},
                    "distribution_channels": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "核心分发渠道列表（线上+线下）",
                    },
                    "launch_phases": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "phase_name": {"type": "string"},
                                "timeline": {"type": "string"},
                                "key_actions": {"type": "array", "items": {"type": "string"}},
                                "success_metric": {"type": "string"},
                            },
                            "required": ["phase_name", "timeline", "key_actions", "success_metric"],
                        },
                        "description": "上市阶段里程碑（2-3个阶段）",
                    },
                    "key_risks": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "主要风险与应对预案（2-3条）",
                    },
                },
                "required": ["gtm_objective", "gtm_model", "beachhead_market", "pricing_strategy", "distribution_channels", "launch_phases"],
            },
        },
    },

    # ─── ⑪ audit_brand_health（可选）─────────────────────────
    {
        "type": "function",
        "function": {
            "name": "audit_brand_health",
            "description": (
                "可选工具：品牌健康度审计。当用户提出品牌复盘、健康度评估、"
                "战略回顾或找出品牌问题根源等诉求时调用。输出多维度评分与优先改进建议。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "brand_name": {"type": "string", "description": "被审计品牌名称"},
                    "audit_dimensions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "dimension": {
                                    "type": "string",
                                    "enum": ["positioning_clarity", "differentiation", "brand_consistency",
                                             "audience_resonance", "visual_identity", "communication_effectiveness",
                                             "brand_equity", "competitive_advantage"],
                                    "description": "审计维度",
                                },
                                "score": {"type": "integer", "description": "评分 1-10"},
                                "finding": {"type": "string", "description": "该维度关键发现（1-2句）"},
                                "priority": {"type": "string", "enum": ["critical", "important", "nice_to_have"]},
                            },
                            "required": ["dimension", "score", "finding", "priority"],
                        },
                        "description": "逐维度审计结果",
                    },
                    "overall_health_score": {
                        "type": "integer",
                        "description": "品牌整体健康度综合评分（1-100）",
                    },
                    "critical_issues": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "必须立即解决的关键问题（≤3条）",
                    },
                    "quick_wins": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "3个月内可执行的快速改善措施",
                    },
                    "long_term_roadmap": {
                        "type": "string",
                        "description": "品牌建设12-24个月路线图建议（3-5句）",
                    },
                },
                "required": ["brand_name", "audit_dimensions", "overall_health_score", "critical_issues", "quick_wins"],
            },
        },
    },
]


# ══════════════════════════════════════════════════════════════
# 2. Tool Executor Functions（工具执行回调）
# ══════════════════════════════════════════════════════════════

def execute_select_frameworks(args: dict[str, Any]) -> str:
    """
    解析全局规划结果，构建执行序列摘要。
    根据 task_mode 动态分发路由。
    """
    task_mode = args.get("task_mode", "full_strategy")
    scenario = args.get("brand_scenario", "unknown")
    emphasis = args.get("priority_emphasis", "")

    # 根据不同的 task_mode 编排执行计划
    if task_mode in ("modular_task", "patch"):
        execution_plan = args.get("target_tools", [])
    else:
        # 默认：full_strategy
        layer0 = args.get("layer0_frameworks", [])
        layer1 = args.get("layer1_industry_engine", "")
        layer2 = args.get("layer2_positioning_theory", "")
        layer3 = [d.get("framework_name", "") for d in args.get("layer3_brand_identity", [])]
        optional = args.get("optional_tools", [])

        execution_plan = [
            "apply_layer0_macro_strategy",
            "apply_layer1_industry_os",
            "apply_layer2_positioning",
        ]
        for f in layer3:
            if f: execution_plan.append(f"apply_layer3_brand_identity({f})")
        execution_plan.append("build_brand_house")
        execution_plan.extend(optional)
        execution_plan.append("synthesize_strategy_report")

    summary = (
        f"任务意图解析完成：当前模式 `{task_mode}`\n"
        f"场景：{scenario} | 战略重心：{emphasis}\n"
        f"执行顺序：{' → '.join(execution_plan) if execution_plan else '无工具调用，准备直接回复'}"
    )
    if task_mode == "full_strategy":
        layer3_names = [d.get("framework_name", "") for d in args.get("layer3_brand_identity", [])] if args.get("layer3_brand_identity") else ["无"]
        summary += (
            f"\n--- full_strategy 理论分配 ---\n"
            f"Layer 0（宏观大盘）：{', '.join(args.get('layer0_frameworks', []))}\n"
            f"Layer 1（行业底座）：{args.get('layer1_industry_engine', '')}\n"
            f"Layer 2（心智定位）：{args.get('layer2_positioning_theory', '')}\n"
            f"Layer 3（身份血肉）：{', '.join(layer3_names)}\n"
            f"可选工具：{', '.join(args.get('optional_tools', [])) if args.get('optional_tools') else '无'}"
        )
    logger.info("Trout 全局规划：%s", summary)
    return summary


def execute_apply_layer0_macro_strategy(args: dict[str, Any]) -> str:
    """执行 Layer 0 宏观大盘与竞争战略分析，返回结构化摘要。"""
    porter_summary = ""
    if args.get("porter_strategy"):
        porter_summary = f"\n波特战略：{args['porter_strategy']} — {args.get('porter_rationale', '')}"

    blue_ocean_summary = ""
    if args.get("blue_ocean_create"):
        blue_ocean_summary = (
            f"\n蓝海四步：剔除{args.get('blue_ocean_eliminate', [])} | "
            f"减少{args.get('blue_ocean_reduce', [])} | "
            f"增加{args.get('blue_ocean_raise', [])} | "
            f"创造{args.get('blue_ocean_create', [])}"
        )

    focus_summary = ""
    if args.get("focus_target_segment"):
        focus_summary = (
            f"\n聚焦战略：目标细分→{args['focus_target_segment']} | "
            f"聚焦优势→{args.get('focus_advantage', '')}"
        )

    ansoff_summary = ""
    if args.get("ansoff_direction"):
        ansoff_summary = f"\n安索夫矩阵：{args['ansoff_direction']} — {args.get('ansoff_rationale', '')}"

    conclusion = args.get("macro_conclusion", "")

    result = f"{porter_summary}{blue_ocean_summary}{focus_summary}{ansoff_summary}\n\nLayer 0 宏观大盘结论：{conclusion}"
    logger.info("Layer 0 宏观大盘分析完成")
    return result.strip()


def execute_apply_layer1_industry_os(args: dict[str, Any]) -> str:
    """执行 Layer 1 行业底座引擎，根据 engine_type 路由到对应子分析。"""
    engine_type = args.get("engine_type", "")
    brand_name = args.get("brand_name", "")
    conclusion = args.get("layer1_conclusion", "")

    if engine_type == "huawei_five_views":
        detail = _execute_huawei_five_views(args)
    elif engine_type == "brand_key":
        detail = _execute_brand_key(args)
    elif engine_type == "ogilvy_big_ideal":
        detail = _execute_ogilvy_big_ideal(args)
    elif engine_type == "golden_circle":
        detail = _execute_golden_circle_l1(args)
    else:
        detail = f"行业底座分析（{engine_type}）"

    logger.info("Layer 1 行业底座引擎完成：%s / %s", engine_type, brand_name)
    return f"【Layer 1 · {engine_type} · 品牌：{brand_name}】\n{detail}\n\n行业底座结论：{conclusion}"


def _execute_huawei_five_views(args: dict) -> str:
    """华为五看三定框架。"""
    return (
        f"华为五看三定框架：\n\n"
        f"【五看】\n"
        f"  看市场：{args.get('hw_look_market', '')}\n"
        f"  看客户：{args.get('hw_look_customer', '')}\n"
        f"  看竞争：{args.get('hw_look_competition', '')}\n"
        f"  看自身：{args.get('hw_look_self', '')}\n"
        f"  看机会：{args.get('hw_look_opportunity', '')}\n\n"
        f"【三定】\n"
        f"  定方向：{args.get('hw_define_direction', '')}\n"
        f"  定目标：{args.get('hw_define_target', '')}\n"
        f"  定策略：{args.get('hw_define_strategy', '')}"
    )


def _execute_brand_key(args: dict) -> str:
    """联合利华 Brand Key 框架。"""
    rtb_list = "\n".join(f"    - {r}" for r in args.get("bk_rtb", []))
    return (
        f"联合利华 Brand Key 模型：\n\n"
        f"  目标消费者：{args.get('bk_target_consumer', '')}\n"
        f"  竞争环境：{args.get('bk_competitive_context', '')}\n"
        f"  消费者洞察：{args.get('bk_consumer_insight', '')}\n"
        f"  功能利益：{args.get('bk_functional_benefit', '')}\n"
        f"  情感利益：{args.get('bk_emotional_benefit', '')}\n"
        f"  信任状（RTB）：\n{rtb_list}\n"
        f"  品牌个性：{args.get('bk_brand_personality', '')}\n"
        f"  品牌精髓：{args.get('bk_brand_essence', '')}"
    )


def _execute_ogilvy_big_ideal(args: dict) -> str:
    """奥美大理想框架。"""
    return (
        f"奥美大理想框架：\n\n"
        f"  文化张力：{args.get('oi_cultural_tension', '')}\n"
        f"  品牌真相：{args.get('oi_brand_truth', '')}\n\n"
        f"  ★ 大理想宣言：{args.get('oi_big_ideal', '')}\n\n"
        f"  品牌文化角色：{args.get('oi_role_in_culture', '')}"
    )


def _execute_golden_circle_l1(args: dict) -> str:
    """西蒙·斯涅克黄金圈框架（L1行业底座版）。"""
    return (
        f"黄金圈理论（Simon Sinek）：\n\n"
        f"  WHY（信念/目的）：{args.get('gc_why', '')}\n"
        f"  HOW（独特方法）：{args.get('gc_how', '')}\n"
        f"  WHAT（产品/服务）：{args.get('gc_what', '')}\n\n"
        f"  Purpose 宣言：{args.get('gc_purpose_statement', '')}"
    )


def execute_apply_layer2_positioning(args: dict[str, Any]) -> str:
    """执行 Layer 2 心智定位尖刀，根据 theory_type 路由到对应子分析。"""
    theory_type = args.get("theory_type", "trout_positioning")
    brand_name = args.get("brand_name", "")
    positioning_statement = args.get("core_positioning_statement", "")

    if theory_type == "trout_positioning":
        result = _execute_trout_positioning(args, brand_name, positioning_statement)
    elif theory_type == "ries_positioning":
        result = _execute_ries_positioning(args, brand_name, positioning_statement)
    elif theory_type == "stp_positioning":
        result = _execute_stp_positioning(args, brand_name, positioning_statement)
    else:
        result = f"定位理论 {theory_type} 执行结果：{positioning_statement}"

    logger.info("Layer 2 心智定位分析完成，理论：%s", theory_type)
    return result


def _execute_trout_positioning(args: dict, brand_name: str, statement: str) -> str:
    """特劳特定位理论：定位三角 + 定位四步法"""
    return (
        f"【特劳特定位理论】品牌：{brand_name}\n"
        f"定位语：{statement}\n\n"
        f"定位三角：\n"
        f"  目标市场：{args.get('trout_target_market', '')}\n"
        f"  主要竞品：{', '.join(args.get('trout_main_competitors', []))}\n"
        f"  自身优势：{args.get('trout_own_advantage', '')}\n\n"
        f"心智定位占位：{args.get('trout_mind_position', '')}\n"
        f"差异化主张：{args.get('trout_differentiation', '')}\n"
        f"品类第一策略：{args.get('trout_category_leadership', '')}\n\n"
        f"定位四步法：\n"
        f"  信任状建立：{args.get('trout_trust_builder', '')}\n"
        f"  传播定位策略：{args.get('trout_communication_strategy', '')}"
    )


def _execute_ries_positioning(args: dict, brand_name: str, statement: str) -> str:
    """里斯定位理论：品类创新四步 + 定位四象限"""
    quadrant_labels = {
        "leader": "领导者", "challenger": "挑战者",
        "follower": "跟随者", "nicher": "补缺者",
    }
    quadrant = args.get("ries_quadrant_position", "challenger")
    return (
        f"【里斯定位理论】品牌：{brand_name}\n"
        f"定位语：{statement}\n\n"
        f"品类创新：{args.get('ries_new_category_name', '')}\n"
        f"聚焦策略：{args.get('ries_focus_strategy', '')}\n"
        f"视觉锤方向：{args.get('ries_visual_hammer', '')}\n"
        f"公关启动策略：{args.get('ries_pr_launch', '')}\n"
        f"市场四象限位置：{quadrant_labels.get(quadrant, quadrant)}"
    )


def _execute_stp_positioning(args: dict, brand_name: str, statement: str) -> str:
    """STP经典定位：市场细分 + 定位地图"""
    return (
        f"【STP经典定位】品牌：{brand_name}\n"
        f"定位语：{statement}\n\n"
        f"市场细分变量：{', '.join(args.get('stp_segmentation_vars', []))}\n"
        f"目标市场画像：{args.get('stp_target_segment', '')}\n"
        f"定位地图坐标轴：X轴={args.get('stp_map_axis_x', '')} | Y轴={args.get('stp_map_axis_y', '')}\n"
        f"品牌坐标位置：{args.get('stp_map_brand_position', '')}"
    )


def execute_apply_layer3_brand_identity(args: dict[str, Any]) -> str:
    """执行 Layer 3 身份血肉包装分析，根据 identity_type 路由。"""
    identity_type = args.get("identity_type", "")
    framework_name = args.get("framework_name", "")
    conclusion = args.get("identity_conclusion", "")

    if identity_type == "archetype":
        detail = _format_brand_personality(args)   # 复用 12原型+Aaker五维度格式
    elif identity_type == "brand_prism":
        detail = _format_brand_identity(args, "kapferer_prism")
    elif identity_type == "brand_equity":
        detail = _format_brand_equity(args, framework_name)
    elif identity_type == "brand_personality":
        detail = _format_brand_personality(args)
    else:
        detail = _format_brand_identity(args, framework_name)

    logger.info("Layer 3 身份血肉包装完成：%s / %s", identity_type, framework_name)
    return f"【Layer 3 · {framework_name}】\n{detail}\n\n包装结论：{conclusion}"


def _format_brand_identity(args: dict, framework_name: str) -> str:
    if framework_name == "aaker_identity":
        return (
            f"Aaker 品牌识别四维：\n"
            f"  作为产品：{args.get('aaker_product_dimension', '')}\n"
            f"  作为组织：{args.get('aaker_org_dimension', '')}\n"
            f"  作为人：{args.get('aaker_person_dimension', '')}\n"
            f"  作为符号：{args.get('aaker_symbol_dimension', '')}"
        )
    if framework_name == "kapferer_prism":
        return (
            f"Kapferer 品牌棱镜：\n"
            f"  物质特征：{args.get('kapferer_physique', '')} | 个性：{args.get('kapferer_personality', '')}\n"
            f"  文化：{args.get('kapferer_culture', '')} | 关系：{args.get('kapferer_relationship', '')}\n"
            f"  反射：{args.get('kapferer_reflection', '')} | 自我认知：{args.get('kapferer_self_image', '')}"
        )
    if framework_name == "ogilvy_honeycomb":
        return (
            f"奥美品牌蜂巢：\n"
            f"  核心价值→{args.get('honeycomb_core_value', '')} | 个性→{args.get('honeycomb_personality', '')}\n"
            f"  事实→{args.get('honeycomb_facts', '')} | 利益→{args.get('honeycomb_benefits', '')}\n"
            f"  价值观→{args.get('honeycomb_values', '')} | 精髓→{args.get('honeycomb_essence', '')}"
        )
    # ogilvy_image / lb_brand_mark
    traits = ', '.join(args.get('identity_personality_traits', []))
    return f"品牌核心精髓：{args.get('identity_core_essence', '')}\n个性特征：{traits}"


def _format_brand_equity(args: dict, framework_name: str) -> str:
    if framework_name == "keller_cbbe":
        return (
            f"Keller CBBE 共鸣金字塔：\n"
            f"  显著性：{args.get('cbbe_salience', '')}\n"
            f"  表现：{args.get('cbbe_performance', '')} | 形象：{args.get('cbbe_imagery', '')}\n"
            f"  判断：{args.get('cbbe_judgments', '')} | 感受：{args.get('cbbe_feelings', '')}\n"
            f"  共鸣：{args.get('cbbe_resonance', '')}"
        )
    if framework_name == "yr_bav":
        return (
            f"Y&R BAV 品牌资产：\n"
            f"  差异性：{args.get('bav_differentiation', '')} | 相关性：{args.get('bav_relevance', '')}\n"
            f"  尊重度：{args.get('bav_esteem', '')} | 认知度：{args.get('bav_knowledge', '')}\n"
            f"  品牌强度：{args.get('bav_brand_strength', '')}\n"
            f"  品牌高度：{args.get('bav_brand_stature', '')}"
        )
    if framework_name == "brand_promise":
        return (
            f"品牌承诺模型：\n"
            f"  功能承诺：{args.get('promise_functional', '')}\n"
            f"  情感承诺：{args.get('promise_emotional', '')}\n"
            f"  自我表达承诺：{args.get('promise_self_expressive', '')}"
        )
    return f"品牌资产分析（{framework_name}）"


def _format_brand_personality(args: dict) -> str:
    archetype_cn = {
        "innocent": "纯真者", "sage": "智者", "explorer": "探险家",
        "outlaw": "反叛者", "magician": "魔法师", "hero": "英雄",
        "lover": "情人", "jester": "弄臣", "everyman": "普通人",
        "caregiver": "照料者", "ruler": "统治者", "creator": "创造者",
    }
    primary = args.get("jung_primary_archetype", "")
    return (
        f"Jung 原型 + Aaker 五维度：\n"
        f"  主原型：{archetype_cn.get(primary, primary)}\n"
        f"  副原型：{args.get('jung_secondary_archetype', '无')}\n"
        f"  原型应用：{args.get('jung_archetype_application', '')}\n"
        f"  Aaker五维：真诚{args.get('aaker_sincerity', '-')} | 激动{args.get('aaker_excitement', '-')} | "
        f"能力{args.get('aaker_competence', '-')} | 精致{args.get('aaker_sophistication', '-')} | "
        f"粗犷{args.get('aaker_ruggedness', '-')}\n"
        f"  性格综述：{args.get('personality_summary', '')}"
    )


def _format_mission_driven(args: dict) -> str:
    # NOTE: 黄金圈在新架构中已升至 L1，此处保留作为 L3 brand_equity 兼容层
    return (
        f"黄金圈理论（Simon Sinek）：\n"
        f"  WHY（信念）：{args.get('golden_circle_why', '')}\n"
        f"  HOW（方法）：{args.get('golden_circle_how', '')}\n"
        f"  WHAT（产品）：{args.get('golden_circle_what', '')}"
    )


def execute_build_brand_house(args: dict[str, Any]) -> str:
    """构建品牌屋，返回结构化品牌屋摘要。"""
    p1 = args.get("pillar_1", {})
    p2 = args.get("pillar_2", {})
    p3 = args.get("pillar_3", {})
    values = " | ".join(args.get("values", []))
    brand_is = " / ".join(args.get("brand_is", []))
    brand_is_not = " / ".join(args.get("brand_is_not", []))

    result = (
        f"【品牌屋构建完成】\n"
        f"品牌承诺（屋顶）：{args.get('brand_promise', '')}\n\n"
        f"三大支柱：\n"
        f"  ① {p1.get('name', '')}：{p1.get('description', '')}\n"
        f"  ② {p2.get('name', '')}：{p2.get('description', '')}\n"
        f"  ③ {p3.get('name', '')}：{p3.get('description', '')}\n\n"
        f"使命：{args.get('mission', '')}\n"
        f"愿景：{args.get('vision', '')}\n"
        f"价值观：{values}\n\n"
        f"调性：品牌是 [{brand_is}] / 品牌不是 [{brand_is_not}]"
    )
    logger.info("品牌屋构建完成：%s", args.get("brand_promise", ""))
    return result


def execute_design_brand_architecture(args: dict[str, Any]) -> str:
    """品牌架构模型决策。"""
    model_labels = {
        "branded_house": "品牌之家（Branded House）",
        "house_of_brands": "品牌群（House of Brands）",
        "endorsed_brands": "背书品牌（Endorsed Brands）",
        "hybrid": "混合架构（Hybrid）",
    }
    model = args.get("recommended_model", "")
    hierarchy = " > ".join(args.get("architecture_hierarchy", []))
    return (
        f"【品牌架构决策】\n"
        f"推荐模型：{model_labels.get(model, model)}\n"
        f"选择原因：{args.get('rationale', '')}\n"
        f"层级结构：{hierarchy}\n"
        f"延伸策略：{args.get('extension_strategy', '')}"
    )


def execute_generate_naming_candidates(args: dict[str, Any]) -> str:
    """品牌命名候选方案。"""
    candidates = args.get("candidates", [])
    candidates_text = "\n".join(
        f"  {i+1}. {c.get('name', '')} — {c.get('rationale', '')} [商标风险: {c.get('trademark_risk', '')}]"
        for i, c in enumerate(candidates)
    )
    return (
        f"【品牌命名方案】\n"
        f"命名策略：{args.get('naming_strategy', '')}\n"
        f"候选名单：\n{candidates_text}\n\n"
        f"首选推荐：{args.get('top_recommendation', '')} — {args.get('recommendation_reason', '')}"
    )


def execute_plan_communication_strategy(args: dict[str, Any]) -> str:
    """品牌传播策略规划：核心主张 + 阶段路径 + 内容支柱。"""
    phases = args.get("communication_phases", [])
    phases_text = "\n".join(
        f"  [{p.get('phase', '')}] 目标：{p.get('objective', '')} | 核心信息：{p.get('key_message', '')} | 渠道：{', '.join(p.get('channels', []))}"
        for p in phases
    )
    pillars = " / ".join(args.get("content_pillars", []))
    result = (
        f"【传播策略规划】\n"
        f"核心传播主张：{args.get('core_message', '')}\n"
        f"目标受众：{args.get('target_audience_summary', '')}\n\n"
        f"分阶段路径：\n{phases_text}\n\n"
        f"内容支柱：{pillars}\n"
        f"品牌声音：{args.get('brand_voice_guide', '待定')}\n"
        f"衡量 KPI：{args.get('kpi_framework', '待定')}"
    )
    logger.info("传播策略规划完成：%s", args.get("core_message", ""))
    return result


def execute_design_gtm_strategy(args: dict[str, Any]) -> str:
    """GTM 上市策略：目标 + 模式 + 定价 + 渠道 + 里程碑。"""
    gtm_model_labels = {
        "direct_sales": "直销模式",
        "channel_partner": "渠道伙伴模式",
        "product_led": "产品驱动增长 (PLG)",
        "community_led": "社群驱动增长 (CLG)",
        "hybrid": "混合模式",
    }
    pricing_labels = {
        "penetration": "渗透定价",
        "premium": "溢价定价",
        "freemium": "免费增值",
        "value_based": "价值定价",
        "subscription": "订阅制",
    }
    phases = args.get("launch_phases", [])
    phases_text = "\n".join(
        f"  [{p.get('phase_name', '')} · {p.get('timeline', '')}] "
        f"关键动作：{', '.join(p.get('key_actions', []))} | 成功指标：{p.get('success_metric', '')}"
        for p in phases
    )
    channels = " / ".join(args.get("distribution_channels", []))
    risks = "\n".join(f"  • {r}" for r in args.get("key_risks", []))
    result = (
        f"【GTM 上市策略】\n"
        f"核心目标：{args.get('gtm_objective', '')}\n"
        f"GTM 模式：{gtm_model_labels.get(args.get('gtm_model', ''), args.get('gtm_model', ''))}\n"
        f"滩头市场：{args.get('beachhead_market', '')}\n"
        f"定价策略：{pricing_labels.get(args.get('pricing_strategy', ''), '')} — {args.get('pricing_rationale', '')}\n"
        f"分发渠道：{channels}\n\n"
        f"上市里程碑：\n{phases_text}\n\n"
        f"主要风险：\n{risks}"
    )
    logger.info("GTM 策略规划完成：%s", args.get("gtm_objective", ""))
    return result


def execute_audit_brand_health(args: dict[str, Any]) -> str:
    """品牌健康度审计：多维评分 + 关键问题 + 改进路线。"""
    dimension_labels = {
        "positioning_clarity": "定位清晰度",
        "differentiation": "差异化程度",
        "brand_consistency": "品牌一致性",
        "audience_resonance": "受众共鸣度",
        "visual_identity": "视觉识别系统",
        "communication_effectiveness": "传播有效性",
        "brand_equity": "品牌资产积累",
        "competitive_advantage": "竞争优势",
    }
    priority_labels = {"critical": "🔴关键", "important": "🟡重要", "nice_to_have": "🟢可优化"}
    dimensions = args.get("audit_dimensions", [])
    dim_text = "\n".join(
        f"  {dimension_labels.get(d.get('dimension', ''), d.get('dimension', ''))}："
        f"{d.get('score', 0)}/10 [{priority_labels.get(d.get('priority', ''), '')}] — {d.get('finding', '')}"
        for d in dimensions
    )
    critical = "\n".join(f"  [题] {i}" for i in args.get("critical_issues", []))
    wins = "\n".join(f"  [赢] {w}" for w in args.get("quick_wins", []))
    result = (
        f"【品牌健康度审计 · {args.get('brand_name', '')}】\n"
        f"整体健康度评分：{args.get('overall_health_score', 0)}/100\n\n"
        f"各维度评分：\n{dim_text}\n\n"
        f"关键问题（立即处理）：\n{critical}\n\n"
        f"快速改善措施（3个月内）：\n{wins}\n\n"
        f"12-24个月路线图：{args.get('long_term_roadmap', '待规划')}"
    )
    logger.info("品牌健康度审计完成：%s，总分 %s", args.get("brand_name", ""), args.get("overall_health_score", 0))
    return result


def execute_synthesize_report(args: dict[str, Any]) -> str:
    """
    汇总所有框架执行结果，返回报告提示标记。
    NOTE: 返回的字符串由 strategy_agent.py 识别，触发 Phase 2 流式报告生成。
    """
    executed = args.get("executed_frameworks", [])
    handoff_data = {
        "品牌定位语": args.get("handoff_positioning_statement", ""),
        "核心USP": args.get("handoff_usp", ""),
        "品牌承诺": args.get("handoff_brand_promise", ""),
        "品牌个性关键词": args.get("handoff_personality_keywords", []),
        "传播方向指引": args.get("handoff_communication_direction", ""),
        "视觉方向指引": args.get("handoff_visual_direction", ""),
    }
    logger.info("Trout 所有框架执行完毕，准备生成报告。已执行：%s", executed)
    return json.dumps(
        {
            "trigger": "synthesize_report",
            "executed_frameworks": executed,
            "layer0_conclusion": args.get("layer0_conclusion", ""),
            "layer1_conclusion": args.get("layer1_conclusion", ""),
            "layer2_conclusion": args.get("layer2_conclusion", "未执行"),
            "layer3_conclusion": args.get("layer3_conclusion", "未执行"),
            "brand_house_summary": args.get("brand_house_summary", ""),
            "handoff": handoff_data,
        },
        ensure_ascii=False,
        indent=2,
    )


# ══════════════════════════════════════════════════════════════
# 3. Tool Dispatcher
# ══════════════════════════════════════════════════════════════

TOOL_EXECUTORS: dict[str, Any] = {
    # 全局规划
    "select_applicable_frameworks":  execute_select_frameworks,
    # Layer 0 · 宏观大盘
    "apply_layer0_macro_strategy":   execute_apply_layer0_macro_strategy,
    # Layer 1 · 行业底座引擎（新增）
    "apply_layer1_industry_os":      execute_apply_layer1_industry_os,
    # Layer 2 · 心智定位尖刀
    "apply_layer2_positioning":      execute_apply_layer2_positioning,
    # Layer 3 · 身份血肉包装
    "apply_layer3_brand_identity":   execute_apply_layer3_brand_identity,
    # 强制工具
    "build_brand_house":             execute_build_brand_house,
    "synthesize_strategy_report":    execute_synthesize_report,
    # 可选工具
    "design_brand_architecture":     execute_design_brand_architecture,
    "generate_naming_candidates":    execute_generate_naming_candidates,
    "plan_communication_strategy":   execute_plan_communication_strategy,
    "design_gtm_strategy":           execute_design_gtm_strategy,
    "audit_brand_health":            execute_audit_brand_health,
}


def parse_trout_tool_calls(tool_calls: list[dict]) -> list[dict[str, str]]:
    """
    解析 LLM 返回的 tool_calls 列表；
    对每个 tool call 执行对应分析，返回 [{tool_name, result}, ...] 列表。
    """
    results: list[dict[str, str]] = []
    for tc in tool_calls:
        fn = tc.get("function", {})
        name = fn.get("name", "")
        try:
            raw_args = fn.get("arguments", "{}")
            args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
        except json.JSONDecodeError:
            args = {}

        executor = TOOL_EXECUTORS.get(name)
        if executor:
            try:
                result = executor(args)
            except Exception as e:
                logger.error("工具 %s 执行失败：%s", name, e, exc_info=True)
                result = f"[工具执行错误] {name}: {e}"
        else:
            logger.warning("未知工具：%s", name)
            result = f"[未知工具] {name}"

        results.append({"tool_name": name, "result": result})
    return results
