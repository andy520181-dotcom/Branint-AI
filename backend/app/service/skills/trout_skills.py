"""
Trout Agent（品牌战略专家）核心功能库 v4.0

工作流（四层理论体系）：
  Phase -1: 自适应反问（在 strategy_agent.py 中实现，非工具）
  Phase  0: Input Assembly（消息组装）
  Phase  1: Tool Loop（工具调用循环）
    ① select_applicable_frameworks  — 全局规划，输出 theory_combo
    ② analyze_competitive_landscape — Layer 0：JWT必跑 + 按需选1-2个
    ③ apply_positioning_theory      — Layer 1：特劳特/里斯/STP 三选一
    ④ apply_brand_driver            — Layer 2：身份/资产/个性/使命，按需最多2次
    ⑤ build_brand_house             — 【强制】品牌屋
    ⑥ design_brand_architecture     — 可选，品牌架构
    ⑦ generate_naming_candidates    — 可选，命名方案
    ⑧ synthesize_strategy_report    — 【强制最后】触发报告
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
                "输出包含 Layer 0/1/2 的理论选择和可选工具清单。"
                "Layer 0 中 JWT品牌四问始终必选；"
                "Layer 1 的定位理论必须选且只能选1个；"
                "Layer 2 驱动力框架按需选 0-2 个。"
                "强制必跑的工具：build_brand_house 和 synthesize_strategy_report。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "task_mode": {
                        "type": "string",
                        "enum": ["full_strategy", "name_only", "slogan_only", "positioning_only", "patch"],
                        "description": "识别任务意图，决定走哪条执行路径",
                    },
                    "patch_target_tools": {
                        "type": "array",
                        "items": { "type": "string" },
                        "description": "仅在 task_mode='patch' 时填写。指出需要被热更新/调用的具体底层工具名称。",
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
                    "layer0_frameworks": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": ["jwt_4questions", "porter_competitive", "blue_ocean", "ansoff_matrix"],
                        },
                        "description": (
                            "【针对 full_strategy 模式】Layer 0 竞争战略分析框架，jwt_4questions 始终必选，"
                            "按场景再选1-2个其他框架（竞争激烈→porter；"
                            "需找蓝海→blue_ocean；增长方向不明→ansoff_matrix）"
                        ),
                    },
                    "layer1_theory": {
                        "type": "string",
                        "enum": ["trout_positioning", "ries_positioning", "stp_positioning"],
                        "description": (
                            "【针对 full_strategy 模式】Layer 1 核心定位主理论，必须且只能选1个。"
                            "竞争激烈找差异化→trout_positioning；"
                            "需创造新品类→ries_positioning；"
                            "新市场细分→stp_positioning"
                        ),
                    },
                    "layer1_rationale": {
                        "type": "string",
                        "description": "选择该定位理论的原因（1-2句话）",
                    },
                    "layer2_drivers": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "driver_type": {
                                    "type": "string",
                                    "enum": ["brand_identity", "brand_equity", "brand_personality", "mission_driven"],
                                },
                                "framework_name": {
                                    "type": "string",
                                    "description": (
                                        "具体框架名：brand_identity→aaker_identity/kapferer_prism/ogilvy_image/ogilvy_honeycomb/lb_brand_mark；"
                                        "brand_equity→keller_cbbe/yr_bav/brand_value_chain/brand_promise；"
                                        "brand_personality→jung_aaker_personality；"
                                        "mission_driven→golden_circle"
                                    ),
                                },
                                "rationale": {"type": "string", "description": "选用理由（1句）"},
                            },
                            "required": ["driver_type", "framework_name", "rationale"],
                        },
                        "description": "【针对 full_strategy 模式】Layer 2 驱动力框架，按需选 0-2 个，超过2个会导致分析失焦",
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

    # ─── ② Layer 0：竞争战略分析 ─────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "analyze_competitive_landscape",
            "description": (
                "Layer 0 竞争战略分析。JWT品牌四问始终必须完成，"
                "其他框架（波特/蓝海/安索夫）根据 select_applicable_frameworks 的规划选用。"
                "本工具输出竞争方式和增长方向，为 Layer 1 定位理论选择提供战略前提。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    # JWT 四问（始终必填）
                    "jwt_where_now": {
                        "type": "string",
                        "description": "JWT问题1：我们现在在哪？（品牌现状、市场位置、核心挑战）",
                    },
                    "jwt_why_here": {
                        "type": "string",
                        "description": "JWT问题2：为什么在这里？（根因分析、历史决策、市场力量）",
                    },
                    "jwt_where_go": {
                        "type": "string",
                        "description": "JWT问题3：我们可以去哪里？（战略机会、差异化空间）",
                    },
                    "jwt_how_get": {
                        "type": "string",
                        "description": "JWT问题4：我们如何到达那里？（路径、资源、关键动作）",
                    },
                    # 波特竞争战略（可选）
                    "porter_strategy": {
                        "type": "string",
                        "enum": ["cost_leadership", "differentiation", "focus_cost", "focus_differentiation"],
                        "description": "波特竞争战略选择（仅在规划中包含porter_competitive时填写）",
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
                    "competitive_conclusion": {
                        "type": "string",
                        "description": "Layer 0 整体战略结论（2-3句话，明确竞争方式和增长方向，为Layer1选择定位理论提供依据）",
                    },
                },
                "required": ["jwt_where_now", "jwt_why_here", "jwt_where_go", "jwt_how_get", "competitive_conclusion"],
            },
        },
    },

    # ─── ③ Layer 1：核心定位理论（多理论统一入口）─────────────
    {
        "type": "function",
        "function": {
            "name": "apply_positioning_theory",
            "description": (
                "Layer 1 核心品牌定位分析。根据 select_applicable_frameworks 选定的 layer1_theory，"
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

    # ─── ④ Layer 2：品牌驱动力（统一入口）────────────────────
    {
        "type": "function",
        "function": {
            "name": "apply_brand_driver",
            "description": (
                "Layer 2 品牌驱动力分析。根据 select_applicable_frameworks 选定的 layer2_drivers，"
                "每次调用执行一个驱动力框架（最多调用2次）。"
                "driver_type 决定分析类别，framework_name 决定具体框架。"
                "brand_identity 类：定义品牌身份（Aaker/Kapferer/奥格威/奥美/李奥贝纳）；"
                "brand_equity 类：积累品牌资产（CBBE/BAV/价值链/承诺模型）；"
                "brand_personality 类：品牌性格与原型（Jung原型+Aaker五维度）；"
                "mission_driven 类：信念驱动（黄金圆WHY-HOW-WHAT）。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "driver_type": {
                        "type": "string",
                        "enum": ["brand_identity", "brand_equity", "brand_personality", "mission_driven"],
                        "description": "驱动力类别",
                    },
                    "framework_name": {
                        "type": "string",
                        "description": (
                            "具体框架名称。"
                            "brand_identity→aaker_identity/kapferer_prism/ogilvy_image/ogilvy_honeycomb/lb_brand_mark；"
                            "brand_equity→keller_cbbe/yr_bav/brand_value_chain/brand_promise；"
                            "brand_personality→jung_aaker_personality；"
                            "mission_driven→golden_circle"
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
                    "driver_conclusion": {
                        "type": "string",
                        "description": "本次驱动力分析的核心结论（2-3句），以及如何支撑 Layer 1 的定位",
                    },
                },
                "required": ["driver_type", "framework_name", "driver_conclusion"],
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

    # ─── ⑧ synthesize_strategy_report（强制最后步骤）──────────
    {
        "type": "function",
        "function": {
            "name": "synthesize_strategy_report",
            "description": (
                "【强制最后步骤】在所有框架工具调用完毕后调用。"
                "汇总本次执行的所有框架结果（Layer 0/1/2），触发最终战略报告的流式生成。"
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
                    "layer0_conclusion": {"type": "string", "description": "Layer 0 竞争战略分析核心结论"},
                    "layer1_conclusion": {"type": "string", "description": "Layer 1 品牌定位核心结论（含定位语）"},
                    "layer2_conclusion": {"type": "string", "description": "Layer 2 驱动力分析核心结论（无则填'未执行'）"},
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
    if task_mode == "name_only":
        execution_plan = ["generate_naming_candidates"]
    elif task_mode == "slogan_only":
        execution_plan = []  # 由模型直接补全文字输出，或最多通过 positioning 提供支撑
    elif task_mode == "positioning_only":
        execution_plan = ["apply_positioning_theory"]
    elif task_mode == "patch":
        execution_plan = args.get("patch_target_tools", [])
    else:
        # 默认：full_strategy
        layer0 = args.get("layer0_frameworks", ["jwt_4questions"])
        layer1 = args.get("layer1_theory", "trout_positioning")
        layer2 = args.get("layer2_drivers", [])
        optional = args.get("optional_tools", [])

        # NOTE: 强制确保 jwt_4questions 在 Layer 0 中
        if "jwt_4questions" not in layer0:
            layer0 = ["jwt_4questions"] + layer0
            logger.warning("⚠️ JWT品牌四问被强制加入 Layer 0（必跑项）")
            
        execution_plan = ["analyze_competitive_landscape", "apply_positioning_theory"]
        for driver in layer2: # type: ignore
            execution_plan.append(f"apply_brand_driver({driver.get('framework_name', '')})")
        execution_plan.append("build_brand_house")
        execution_plan.extend(optional)
        execution_plan.append("synthesize_strategy_report")

    layer2_names = [d.get("framework_name", "") for d in args.get("layer2_drivers", [])] if args.get("layer2_drivers") else ["无"]

    summary = (
        f"✅ 任务意图解析完成：当前模式 `{task_mode}`\n"
        f"场景：{scenario} | 战略重心：{emphasis}\n"
        f"执行顺序：{' → '.join(execution_plan) if execution_plan else '无工具调用，准备直接回复'}"
    )
    if task_mode == "full_strategy":
        summary += (
            f"\n--- full_strategy 理论分配 ---\n"
            f"Layer 0（竞争分析）：{', '.join(args.get('layer0_frameworks', []))}\n"
            f"Layer 1（核心定位）：{args.get('layer1_theory', '')}\n"
            f"Layer 2（驱动力）：{', '.join(layer2_names)}\n"
            f"可选工具：{', '.join(args.get('optional_tools', [])) if args.get('optional_tools') else '无'}"
        )
    logger.info("Trout 全局规划：%s", summary)
    return summary


def execute_analyze_competitive_landscape(args: dict[str, Any]) -> str:
    """执行 Layer 0 竞争战略分析，返回结构化摘要。"""
    jwt_summary = (
        f"JWT诊断：\n"
        f"  现在在哪：{args.get('jwt_where_now', '')}\n"
        f"  为何在此：{args.get('jwt_why_here', '')}\n"
        f"  可以去哪：{args.get('jwt_where_go', '')}\n"
        f"  如何到达：{args.get('jwt_how_get', '')}"
    )

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

    ansoff_summary = ""
    if args.get("ansoff_direction"):
        ansoff_summary = f"\n安索夫矩阵：{args['ansoff_direction']} — {args.get('ansoff_rationale', '')}"

    conclusion = args.get("competitive_conclusion", "")

    result = f"{jwt_summary}{porter_summary}{blue_ocean_summary}{ansoff_summary}\n\nLayer 0 结论：{conclusion}"
    logger.info("Layer 0 竞争分析完成")
    return result


def execute_apply_positioning_theory(args: dict[str, Any]) -> str:
    """执行 Layer 1 定位理论，根据 theory_type 路由到对应子分析。"""
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

    logger.info("Layer 1 定位分析完成，理论：%s", theory_type)
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


def execute_apply_brand_driver(args: dict[str, Any]) -> str:
    """执行 Layer 2 驱动力分析，根据 driver_type 路由。"""
    driver_type = args.get("driver_type", "")
    framework_name = args.get("framework_name", "")
    conclusion = args.get("driver_conclusion", "")

    if driver_type == "brand_identity":
        detail = _format_brand_identity(args, framework_name)
    elif driver_type == "brand_equity":
        detail = _format_brand_equity(args, framework_name)
    elif driver_type == "brand_personality":
        detail = _format_brand_personality(args)
    elif driver_type == "mission_driven":
        detail = _format_mission_driven(args)
    else:
        detail = ""

    logger.info("Layer 2 驱动力分析完成：%s / %s", driver_type, framework_name)
    return f"【Layer 2 · {framework_name}】\n{detail}\n\n结论：{conclusion}"


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
    return (
        f"黄金圆理论（Simon Sinek）：\n"
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
    "select_applicable_frameworks": execute_select_frameworks,
    "analyze_competitive_landscape": execute_analyze_competitive_landscape,
    "apply_positioning_theory": execute_apply_positioning_theory,
    "apply_brand_driver": execute_apply_brand_driver,
    "build_brand_house": execute_build_brand_house,
    "design_brand_architecture": execute_design_brand_architecture,
    "generate_naming_candidates": execute_generate_naming_candidates,
    "synthesize_strategy_report": execute_synthesize_report,
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
