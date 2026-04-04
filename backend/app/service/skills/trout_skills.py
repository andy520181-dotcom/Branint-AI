"""
Trout Agent（品牌战略专家）的核心功能库
以品牌咨询专业框架（定位理论、品牌屋、品牌架构等）为基础，
将每个框架封装为 LLM Tool，引导 LLM 逐步完成系统性品牌战略推导。

工作流（智能自适应）：
  0. select_applicable_frameworks — 【元路由，必须第一步】分析用户场景，智能选取本次需要哪些框架
  1. apply_positioning_framework  — Jack Trout 定位理论 + 竞争坐标轴分析
  2. build_brand_house            — 品牌屋构建（使命/愿景/价值观/品牌承诺/个性）
  3. design_brand_architecture    — 品牌架构模型决策（Branded House / House of Brands / 混合）
  4. apply_brand_archetypes       — Jung 原型 + Aaker 五维度 → 品牌个性系统
  5. generate_naming_candidates   — 品牌命名（描述型/联想型/抽象型）+ 商标初评
  6. synthesize_strategy_report   — 汇总已执行框架，输出最终战略报告 + Handoff
"""
from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

# ==========================================
# 1. Tool JSON Schema Definitions
# ==========================================

TROUT_TOOLS = [
    
    {
        "type": "function",
        "function": {
            "name": "select_applicable_frameworks",
            "description": (
                "【必须第一个调用】分析用户的品牌需求和市场研究结论，"
                "智能判断本次战略项目需要哪些框架、按什么顺序执行。"
                ""
                "【重要约束】无论哪种场景，以下三个核心框架是最低必选，不得跳过："
                "apply_positioning_framework（定位是一切战略的基础）、"
                "build_brand_house（品牌屋定义品牌存在的意义和对外承诺）、"
                "apply_brand_archetypes（原型系统为内容和视觉提供个性方向）。"
                "唯一的可选框架是 design_brand_architecture 和 generate_naming_candidates。"
                ""
                "不同场景对应的完整框架组合："
                "① 零基础新品牌（无品牌名/无定位）：全套——定位+品牌屋+架构+原型+命名（5个）；"
                "② 成熟品牌再定位/诊断/升级：核心三件套——定位+品牌屋+原型（命名/架构按需）；"
                "③ 多品牌/集团架构整合：定位+品牌屋+品牌架构（重点）+原型；"
                "④ 品牌调性/个性升级：定位+原型（重点）+品牌屋（调性模块）；"
                "⑤ 有新品牌命名需求：定位+品牌屋+原型+命名（重点）；"
                "⑥ 综合品牌战略分析：全套框架或按需组合，但核心三件套必须包含。"
                ""
                "注意：design_brand_architecture 仅在用户有多产品线/子品牌/集团架构需求时选用；"
                "generate_naming_candidates 仅在用户明确需要品牌命名建议时选用。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "brand_scenario": {
                        "type": "string",
                        "enum": [
                            "new_brand_startup",          # 零基础新品牌，品牌名/定位/屋/原型/命名都需要
                            "brand_repositioning",        # 已有品牌，聚焦重新定位和策略升级
                            "brand_architecture_design",  # 多品牌/集团需要整合架构
                            "brand_identity_refresh",     # 调性/个性升级（保留现有定位，重塑个性）
                            "naming_focused",             # 用户主要需求是命名方案（含基础定位）
                            "comprehensive_strategy",     # 完整品牌战略分析，全套框架
                        ],
                        "description": "识别到的用户品牌场景类型。当用户需求涵盖多个方面或场景不明确时，选 comprehensive_strategy。",
                    },
                    "scenario_diagnosis": {
                        "type": "string",
                        "description": "简短说明为什么判断为该场景（2-3句话，包含用户原文的关键信息依据）",
                    },
                    "selected_frameworks": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": [
                                "apply_positioning_framework",
                                "build_brand_house",
                                "design_brand_architecture",
                                "apply_brand_archetypes",
                                "generate_naming_candidates",
                            ],
                        },
                        "description": (
                            "本次项目需要调用的框架工具列表（按执行顺序排列）。"
                            "必须包含核心三件套：apply_positioning_framework、build_brand_house、apply_brand_archetypes。"
                            "design_brand_architecture 和 generate_naming_candidates 为可选增补项。"
                            "synthesize_strategy_report 始终在最后自动执行，无需列入此处。"
                        ),
                    },
                    "skipped_frameworks": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "reason": {"type": "string", "description": "跳过理由（一句话，必须是业务层面的合理原因）"},
                            },
                            "required": ["name", "reason"],
                        },
                        "description": "只有 design_brand_architecture 和 generate_naming_candidates 可以被跳过，核心三件套不可跳过。",
                    },
                    "priority_emphasis": {
                        "type": "string",
                        "description": "本次战略项目的最高优先级重点（一句话，指导后续框架分析的侧重点）",
                    },
                },
                "required": ["brand_scenario", "scenario_diagnosis", "selected_frameworks", "skipped_frameworks", "priority_emphasis"],
            },
        },
    },
    # ── 工具 1-6：各专业框架（由 select_applicable_frameworks 动态选用）────

    {
        "type": "function",
        "function": {
            "name": "apply_positioning_framework",
            "description": (
                "调用 Jack Trout 定位理论框架，完成品牌差异化定位推导。"
                "必须作为第一个工具调用，因为定位是一切品牌战略的基石。"
                "输入市场研究已识别的关键维度，输出标准定位模板（Positioning Statement）"
                "以及竞争坐标轴上的差异化空白区。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "brand_name": {
                        "type": "string",
                        "description": "品牌名称（若尚未确定则填写项目代号）",
                    },
                    "target_audience": {
                        "type": "string",
                        "description": "核心目标人群的精准描述，包含人口统计 + 心理特征，例如：'25-35岁追求生活品质的新中产女性，关注健康与自我提升'",
                    },
                    "category": {
                        "type": "string",
                        "description": "品牌所在的参考框架/品类，例如：'高端护肤品'、'职场效能 SaaS 工具'",
                    },
                    "core_benefit": {
                        "type": "string",
                        "description": "品牌能为目标人群提供的最核心利益（功能利益 + 情感利益二选一或合并），例如：'帮助忙碌女性用更短时间实现更好的肌肤管理'",
                    },
                    "competitive_differentiator": {
                        "type": "string",
                        "description": "相较于主要竞争对手，品牌最独特的差异化支撑点（RTB: Reason to Believe），例如：'独家专利活性酶配方 + 临床认证数据'",
                    },
                    "key_competitors": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "2-4个主要竞品品牌名，用于建立竞争坐标轴，例如：['完美日记','PROYA','雅诗兰黛']",
                    },
                    "positioning_axis_x": {
                        "type": "string",
                        "description": "竞争坐标轴的 X 轴维度（选择最能体现差异化的维度），例如：'价格定位（大众→高端）'",
                    },
                    "positioning_axis_y": {
                        "type": "string",
                        "description": "竞争坐标轴的 Y 轴维度，例如：'功效主打（护肤科学→生活方式）'",
                    },
                },
                "required": [
                    "brand_name",
                    "target_audience",
                    "category",
                    "core_benefit",
                    "competitive_differentiator",
                    "key_competitors",
                    "positioning_axis_x",
                    "positioning_axis_y",
                ],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "build_brand_house",
            "description": (
                "构建完整的品牌屋（Brand House）框架 ——"
                "品牌咨询最核心的战略文档之一，定义品牌存在的意义、行动信念与对外承诺。"
                "基于 Unilever 品牌屋模型，包含：核心品牌承诺 → 三大品牌支柱 → MVV → 品牌个性。"
                "在完成定位分析（apply_positioning_framework）后调用。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "brand_promise": {
                        "type": "string",
                        "description": "品牌对消费者的核心承诺（Brand Promise），是品牌屋的屋顶，统领一切，一句话表达，例如：'让每一次肌肤投资都看得见改变'",
                    },
                    "brand_pillars": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string", "description": "品牌支柱名称（2-4个字）"},
                                "description": {"type": "string", "description": "该支柱的具体含义（一句话）"},
                                "proof_points": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "支撑该支柱的具体证据/行动（2-3条）",
                                },
                            },
                            "required": ["name", "description", "proof_points"],
                        },
                        "description": "品牌三大支柱（Brand Pillars），支撑品牌承诺的核心理由，通常3个",
                    },
                    "mission": {
                        "type": "string",
                        "description": "品牌使命（Mission）：品牌存在的目的，解决什么社会或用户问题，例如：'让护肤科学普惠更多被高价产品阻挡在外的消费者'",
                    },
                    "vision": {
                        "type": "string",
                        "description": "品牌愿景（Vision）：5-10年后希望成为什么，例如：'成为中国功效护肤领域最被信赖的科学美肤品牌'",
                    },
                    "values": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "品牌价值观（Values）：指导品牌行为的核心信念，3-5条，例如：['科学诚信','极致功效','开放透明']",
                    },
                    "brand_personality_keywords": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "品牌个性关键词（5个形容词），定义品牌的性格魅力，例如：['专业','温暖','真实','前沿','包容']",
                    },
                    "tonality_guide": {
                        "type": "object",
                        "properties": {
                            "what_we_are": {"type": "string", "description": "品牌是什么调性（一句话）"},
                            "what_we_are_not": {"type": "string", "description": "品牌绝对不是什么调性（禁忌，一句话）"},
                        },
                        "required": ["what_we_are", "what_we_are_not"],
                        "description": "品牌语气指南",
                    },
                },
                "required": [
                    "brand_promise",
                    "brand_pillars",
                    "mission",
                    "vision",
                    "values",
                    "brand_personality_keywords",
                    "tonality_guide",
                ],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "design_brand_architecture",
            "description": (
                "根据品牌业务结构，推荐并设计最合适的品牌架构模型。"
                "品牌架构决定了子品牌/产品线与主品牌的关系，影响消费者认知、营销效率和未来延伸空间。"
                "四种主要模型：Branded House（谷歌/苹果，统一品牌，规模效益高）、"
                "House of Brands（P&G/联合利华，独立品牌，精准定位）、"
                "Endorsed Brand（万豪旗下各酒店，背书关系）、"
                "Hybrid/Sub-brand（三星/宝马，主品牌+子品牌双层结构）。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "recommended_model": {
                        "type": "string",
                        "enum": ["branded_house", "house_of_brands", "endorsed_brand", "hybrid_sub_brand"],
                        "description": "推荐采用的品牌架构模型",
                    },
                    "recommendation_rationale": {
                        "type": "string",
                        "description": "推荐该架构模型的详细理由，说明为什么该模型最适合当前品牌发展阶段和业务结构",
                    },
                    "architecture_structure": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "level": {"type": "string", "enum": ["master", "sub", "product_line"], "description": "层级：主品牌/子品牌/产品线"},
                                "name": {"type": "string", "description": "品牌/产品线名称"},
                                "positioning_focus": {"type": "string", "description": "该层级的定位重点（一句话）"},
                            },
                            "required": ["level", "name", "positioning_focus"],
                        },
                        "description": "品牌架构层级结构图（至少包含主品牌层，如有子品牌则依次列出）",
                    },
                    "future_extension_strategy": {
                        "type": "string",
                        "description": "未来品牌延伸策略建议（如何在此架构基础上扩张新品类或渗透新市场）",
                    },
                },
                "required": ["recommended_model", "recommendation_rationale", "architecture_structure", "future_extension_strategy"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "apply_brand_archetypes",
            "description": (
                "应用 Carl Jung 12原型系统 + Jennifer Aaker 品牌个性五维度，"
                "为品牌建立深层的个性原型系统，使品牌具备独特的心理特征和情感张力。"
                "Jung原型赋予品牌故事原型力量（英雄/导师/探险家/创造者等），"
                "Aaker五维度（真诚/激情/能力/精致/粗犷）提供可量化的个性档案。"
                "两套系统结合使用，指导内容策划和视觉设计的一致性。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "primary_archetype": {
                        "type": "string",
                        "enum": [
                            "innocent",      # 纯真者/天真者 - 可口可乐式的乐观
                            "everyman",      # 凡人/邻家好友 - IKEA式的亲切
                            "hero",          # 英雄 - Nike式的激励
                            "outlaw",        # 亡命徒/颠覆者 - Harley式的反叛
                            "explorer",      # 探险家 - Jeep式的自由
                            "creator",       # 创造者 - 乐高式的想象力
                            "ruler",         # 统治者 - Mercedes式的权威
                            "magician",      # 魔法师 - Apple式的变革
                            "lover",         # 情人 - Chanel式的诱惑
                            "caregiver",     # 照顾者 - 强生式的关爱
                            "jester",        # 弄臣 - 老干妈式的反差幽默
                            "sage",          # 智者 - Google式的知识权威
                        ],
                        "description": "品牌主原型（最契合的一个）",
                    },
                    "secondary_archetype": {
                        "type": "string",
                        "description": "品牌副原型（辅助主原型，使个性更丰富，可与主原型同枚举值选择）",
                    },
                    "archetype_application": {
                        "type": "string",
                        "description": "说明该原型组合如何在品牌传播、内容创作、视觉风格中得到体现（具体举例，3-5句话）",
                    },
                    "aaker_dimensions": {
                        "type": "object",
                        "properties": {
                            "sincerity": {"type": "integer", "minimum": 1, "maximum": 10, "description": "真诚度（踏实、诚实、温暖、愉快）1-10分"},
                            "excitement": {"type": "integer", "minimum": 1, "maximum": 10, "description": "激情度（大胆、充满活力、富有想象力、时尚）1-10分"},
                            "competence": {"type": "integer", "minimum": 1, "maximum": 10, "description": "能力感（可靠、智慧、成功）1-10分"},
                            "sophistication": {"type": "integer", "minimum": 1, "maximum": 10, "description": "精致感（上层、迷人）1-10分"},
                            "ruggedness": {"type": "integer", "minimum": 1, "maximum": 10, "description": "粗犷感（户外、坚韧）1-10分"},
                        },
                        "required": ["sincerity", "excitement", "competence", "sophistication", "ruggedness"],
                        "description": "Aaker 品牌个性五维度评分（总分不超过35分，主维度应在8-9分）",
                    },
                    "golden_circle": {
                        "type": "object",
                        "properties": {
                            "why": {"type": "string", "description": "Simon Sinek 黄金圈：品牌的 WHY（存在的深层原因/信念，非商业目的）"},
                            "how": {"type": "string", "description": "HOW（品牌如何实现WHY，核心方法论或差异化做法）"},
                            "what": {"type": "string", "description": "WHAT（品牌实际提供的产品/服务）"},
                        },
                        "required": ["why", "how", "what"],
                        "description": "Simon Sinek 黄金圈（从内向外沟通品牌信念）",
                    },
                },
                "required": ["primary_archetype", "secondary_archetype", "archetype_application", "aaker_dimensions", "golden_circle"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_naming_candidates",
            "description": (
                "基于已完成的定位分析和品牌个性，生成3-5个品牌命名候选方案。"
                "每个方案需覆盖：命名逻辑、品类关联性、国际化适用性、商标可注册性初评。"
                "命名策略类型：描述型（直接表达品类/功能）、联想型（隐喻/类比建立联想）、"
                "抽象型（自造词/谐音，独创性强但建立认知成本高）。"
                "在完成定位（apply_positioning_framework）和品牌屋（build_brand_house）后调用。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "naming_strategy_direction": {
                        "type": "string",
                        "enum": ["descriptive", "associative", "abstract", "mixed"],
                        "description": "本次命名整体策略方向",
                    },
                    "naming_candidates": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string", "description": "候选品牌名（中文/英文/中英组合）"},
                                "type": {
                                    "type": "string",
                                    "enum": ["descriptive", "associative", "abstract"],
                                    "description": "该候选名的命名类型",
                                },
                                "naming_logic": {"type": "string", "description": "命名逻辑与背后含义（2-3句话）"},
                                "brand_fit_score": {
                                    "type": "integer",
                                    "minimum": 1,
                                    "maximum": 10,
                                    "description": "与品牌定位的契合度评分（1-10）",
                                },
                                "international_fit": {
                                    "type": "string",
                                    "enum": ["high", "medium", "low"],
                                    "description": "国际化适用性（发音难度、文化障碍、跨语言含义）",
                                },
                                "trademark_risk": {
                                    "type": "string",
                                    "enum": ["low", "medium", "high"],
                                    "description": "商标注册风险初评（high=高风险，该名称可能已被注册或太通用无法注册）",
                                },
                                "domain_availability": {
                                    "type": "string",
                                    "description": ".com/.cn 域名可用性说明（推荐检查，此处基于常识初评）",
                                },
                            },
                            "required": ["name", "type", "naming_logic", "brand_fit_score", "international_fit", "trademark_risk", "domain_availability"],
                        },
                        "description": "3-5个候选品牌命名方案",
                    },
                    "recommended_name": {
                        "type": "string",
                        "description": "综合推荐的首选品牌名（从候选列表中选择）",
                    },
                    "recommendation_rationale": {
                        "type": "string",
                        "description": "推荐该名称的核心理由（2-3句话）",
                    },
                },
                "required": ["naming_strategy_direction", "naming_candidates", "recommended_name", "recommendation_rationale"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "synthesize_strategy_report",
            "description": (
                "调用此工具表示所有品牌战略框架分析已完成，准备输出最终品牌战略报告。"
                "必须在前述所有工具（apply_positioning_framework、build_brand_house、"
                "apply_brand_archetypes）均已调用后，才触发此工具。"
                "输入核心观点摘要，模型接收后会生成完整的 Markdown 格式战略报告。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "positioning_summary": {
                        "type": "string",
                        "description": "一句话总结品牌定位核心（来自 apply_positioning_framework 的核心结论）",
                    },
                    "brand_promise_summary": {
                        "type": "string",
                        "description": "品牌承诺一句话（来自 build_brand_house）",
                    },
                    "key_strategic_decisions": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "本次战略中最关键的3-5个战略决策点（高度概括）",
                    },
                    "recommended_next_steps": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "战略落地的优先行动建议（2-3条，供内容策划和视觉设计参考）",
                    },
                },
                "required": ["positioning_summary", "brand_promise_summary", "key_strategic_decisions", "recommended_next_steps"],
            },
        },
    },
]


# ==========================================
# 2. Tool Execution Callbacks
# ==========================================

def execute_positioning_framework(args: dict) -> str:
    """
    执行定位框架工具：将 LLM 提供的结构化参数，格式化为定位分析摘要。
    这不是调用外部 API，而是将结构化输入转为统一的框架文档，
    供 LLM 在下一轮对话中参考并填写详细分析内容。
    """
    brand = args.get("brand_name", "（待定）")
    audience = args.get("target_audience", "")
    category = args.get("category", "")
    benefit = args.get("core_benefit", "")
    differentiator = args.get("competitive_differentiator", "")
    competitors = args.get("key_competitors", [])
    axis_x = args.get("positioning_axis_x", "")
    axis_y = args.get("positioning_axis_y", "")

    # 生成标准定位语（Positioning Statement）
    positioning_statement = (
        f"{brand} 是面向【{audience}】的【{category}】，"
        f"能够【{benefit}】，"
        f"不同于竞争对手，因为【{differentiator}】。"
    )

    result = {
        "framework": "Jack Trout 品牌定位框架",
        "positioning_statement": positioning_statement,
        "positioning_map": {
            "axis_x": axis_x,
            "axis_y": axis_y,
            "plotted_competitors": competitors,
            "instruction": (
                f"请在接下来的报告中，以文字描述 {brand} 在以\u300c{axis_x}\u300d为X轴、"
                f"\u300c{axis_y}\u300d为Y轴的定位坐标图中所处位置，并说明差异化空白区。"
            ),
        },
        "status": "✅ 定位框架已建立，请继续调用 build_brand_house。",
    }
    logger.info("Trout 定位框架已生成: %s", positioning_statement[:60])
    return json.dumps(result, ensure_ascii=False)


def execute_brand_house(args: dict) -> str:
    """将品牌屋参数格式化为结构化文档，供 LLM 参考生成完整品牌屋章节。"""
    pillars = args.get("brand_pillars", [])
    pillars_text = "\n".join(
        f"  [{p.get('name')}] {p.get('description')} — 证据：{', '.join(p.get('proof_points', []))}"
        for p in pillars
    )
    result = {
        "framework": "Unilever 品牌屋模型",
        "brand_promise": args.get("brand_promise"),
        "brand_pillars": pillars,
        "mvv": {
            "mission": args.get("mission"),
            "vision": args.get("vision"),
            "values": args.get("values", []),
        },
        "personality": {
            "keywords": args.get("brand_personality_keywords", []),
            "tonality": args.get("tonality_guide", {}),
        },
        "status": "✅ 品牌屋框架已建立，请继续调用 design_brand_architecture 或 apply_brand_archetypes。",
    }
    logger.info("Trout 品牌屋已构建，品牌承诺: %s", args.get("brand_promise", "")[:50])
    return json.dumps(result, ensure_ascii=False)


def execute_brand_architecture(args: dict) -> str:
    """将品牌架构决策格式化为文档。"""
    model_map = {
        "branded_house": "统一品牌（Branded House）",
        "house_of_brands": "多品牌矩阵（House of Brands）",
        "endorsed_brand": "背书品牌（Endorsed Brand）",
        "hybrid_sub_brand": "混合/子品牌（Hybrid Sub-brand）",
    }
    result = {
        "framework": "品牌架构模型",
        "recommended_model": model_map.get(args.get("recommended_model", ""), args.get("recommended_model")),
        "rationale": args.get("recommendation_rationale"),
        "structure": args.get("architecture_structure", []),
        "future_extension": args.get("future_extension_strategy"),
        "status": "✅ 品牌架构决策完成。",
    }
    logger.info("Trout 品牌架构: %s", result["recommended_model"])
    return json.dumps(result, ensure_ascii=False)


def execute_brand_archetypes(args: dict) -> str:
    """将原型系统格式化为品牌个性档案。"""
    archetype_names = {
        "innocent": "纯真者", "everyman": "凡人/邻家好友", "hero": "英雄",
        "outlaw": "颠覆者", "explorer": "探险家", "creator": "创造者",
        "ruler": "权威统治者", "magician": "魔法师", "lover": "情人",
        "caregiver": "照顾者", "jester": "弄臣", "sage": "智者",
    }
    primary = archetype_names.get(args.get("primary_archetype", ""), args.get("primary_archetype", ""))
    secondary = archetype_names.get(args.get("secondary_archetype", ""), args.get("secondary_archetype", ""))

    result = {
        "framework": "Jung原型 + Aaker五维度品牌个性系统",
        "archetypes": {
            "primary": primary,
            "secondary": secondary,
            "application": args.get("archetype_application"),
        },
        "aaker_dimensions": args.get("aaker_dimensions", {}),
        "golden_circle": args.get("golden_circle", {}),
        "status": "✅ 品牌原型系统已建立，请继续调用 generate_naming_candidates 或 synthesize_strategy_report。",
    }
    logger.info("Trout 原型: %s + %s", primary, secondary)
    return json.dumps(result, ensure_ascii=False)


def execute_naming_candidates(args: dict) -> str:
    """将命名候选方案格式化为结构化列表。"""
    strategy_map = {
        "descriptive": "描述型", "associative": "联想型",
        "abstract": "抽象型", "mixed": "混合型",
    }
    result = {
        "framework": "品牌命名系统",
        "strategy": strategy_map.get(args.get("naming_strategy_direction", ""), ""),
        "candidates": args.get("naming_candidates", []),
        "recommendation": {
            "name": args.get("recommended_name"),
            "rationale": args.get("recommendation_rationale"),
        },
        "status": "✅ 命名方案已生成，请调用 synthesize_strategy_report 完成战略报告。",
    }
    logger.info("Trout 命名推荐: %s", args.get("recommended_name", ""))
    return json.dumps(result, ensure_ascii=False)


def execute_synthesize_report(args: dict) -> str:
    """触发报告输出的触发器，返回正式报告撰写指令。"""
    result = {
        "status": "✅ 所有品牌战略框架分析完成，现在输出完整品牌战略报告。",
        "positioning_summary": args.get("positioning_summary"),
        "brand_promise": args.get("brand_promise_summary"),
        "key_decisions": args.get("key_strategic_decisions", []),
        "next_steps": args.get("recommended_next_steps", []),
        "report_instruction": (
            "请现在按照品牌战略报告标准格式，将以上所有框架分析整合为完整的 Markdown 报告，"
            "包含：① 战略定位 ② 品牌屋 ③ 品牌架构 ④ 品牌原型系统 ⑤ 命名方案 ⑥ Handoff 摘要。"
        ),
    }
    logger.info("Trout 战略报告触发：%s", args.get("positioning_summary", "")[:50])
    return json.dumps(result, ensure_ascii=False)


# ==========================================
# 2b. Executor: select_applicable_frameworks
# ==========================================

def execute_select_frameworks(args: dict) -> str:
    """
    元路由工具的执行器。
    在 Python 层将 LLM 的决策格式化为清晰的「框架执行计划」文档，
    并强制执行最低框架保证：定位 + 品牌屋 + 原型 是任何场景下的必选三件套。
    即使 LLM 漏选了核心框架，也会在这里自动补充。
    """
    scenario = args.get("brand_scenario", "")
    selected = args.get("selected_frameworks", [])
    skipped = args.get("skipped_frameworks", [])
    emphasis = args.get("priority_emphasis", "")
    diagnosis = args.get("scenario_diagnosis", "")

    scenario_label = {
        "new_brand_startup": "零基础新品牌",
        "brand_repositioning": "成熟品牌再定位",
        "brand_architecture_design": "多品牌架构整合",
        "brand_identity_refresh": "品牌调性/个性升级",
        "naming_focused": "命名专项",
        "comprehensive_strategy": "综合品牌战略分析",
        # 兜底兼容旧键（防止迁移期间 LLM 仍然输出旧场景名）
        "lightweight_strategy": "品牌战略分析",
    }.get(scenario, scenario)

    # NOTE: 核心最低保证 —— 无论 LLM 选了什么，以下三个框架必须存在
    # Ogilvy 已过滤掉真正的轻量请求（direct_response），进入 Trout 的必须完整
    MANDATORY_FRAMEWORKS = [
        "apply_positioning_framework",
        "build_brand_house",
        "apply_brand_archetypes",
    ]

    # 检查是否有核心框架被遗漏，自动补充到 selected 中（保持顺序）
    auto_added: list[str] = []
    for mandatory in MANDATORY_FRAMEWORKS:
        if mandatory not in selected:
            selected.append(mandatory)
            auto_added.append(mandatory)
            logger.warning(
                "Trout 框架保证机制触发：%s 被自动补充到框架序列（LLM 遗漏了该核心框架）",
                mandatory,
            )

    # 同步移除「被自动补充框架」在 skipped 列表中的错误记录
    skipped = [s for s in skipped if s.get("name") not in MANDATORY_FRAMEWORKS]

    # 确保执行顺序合理（定位→品牌屋→架构→原型→命名）
    ORDER = [
        "apply_positioning_framework",
        "build_brand_house",
        "design_brand_architecture",
        "apply_brand_archetypes",
        "generate_naming_candidates",
    ]
    ordered_selected = [f for f in ORDER if f in selected]
    # 补充任何不在标准顺序中的框架（理论上不会发生，保险起见）
    ordered_selected += [f for f in selected if f not in ORDER]

    skip_summary = [
        f"{s.get('name')} (原因: {s.get('reason')})"
        for s in skipped
    ]

    logger.info(
        "Trout 框架预选完成 | 场景: %s | 执行: %s | 跳过: %s%s",
        scenario_label,
        ordered_selected,
        skip_summary or "无",
        f" | ⚠️ 自动补充: {auto_added}" if auto_added else "",
    )

    framework_sequence = ordered_selected + ["synthesize_strategy_report"]

    result = {
        "status": f"✅ 框架计划确定 | 场景：{scenario_label}",
        "scenario": scenario_label,
        "diagnosis": diagnosis,
        "framework_sequence": framework_sequence,
        "auto_added_mandatory": auto_added,
        "skipped": skip_summary,
        "priority_emphasis": emphasis,
        "instruction": (
            f"请严格按以下顺序依次调用框架工具（共 {len(framework_sequence)} 步）："
            f"{' → '.join(framework_sequence)}。"
            f"{'跳过的框架：' + ', '.join(s.get('name','') for s in skipped) + '。' if skipped else ''}"
            f"重点关注：{emphasis}"
        ),
    }
    return json.dumps(result, ensure_ascii=False)


# ==========================================
# 3. Tool Dispatcher
# ==========================================

TOOL_EXECUTORS: dict[str, Any] = {
    "select_applicable_frameworks": execute_select_frameworks,
    "apply_positioning_framework": execute_positioning_framework,
    "build_brand_house": execute_brand_house,
    "design_brand_architecture": execute_brand_architecture,
    "apply_brand_archetypes": execute_brand_archetypes,
    "generate_naming_candidates": execute_naming_candidates,
    "synthesize_strategy_report": execute_synthesize_report,
}


def execute_trout_tool(tool_name: str, args: dict) -> str:
    """
    统一工具调度入口。
    将 LLM 的 tool_call 路由到对应的执行函数,返回结构化结果字符串。
    """
    executor = TOOL_EXECUTORS.get(tool_name)
    if not executor:
        logger.warning("Trout 未知工具调用: %s", tool_name)
        return json.dumps({"error": f"未知工具: {tool_name}"}, ensure_ascii=False)
    try:
        return executor(args)
    except Exception as e:
        logger.error("Trout 工具执行失败 [%s]: %s", tool_name, e)
        return json.dumps({"error": str(e)}, ensure_ascii=False)


def parse_trout_tool_calls(tool_calls: list) -> list[tuple[str, dict]]:
    """
    解析 LLM 返回的 tool_calls 列表，提取工具名和参数。
    返回 [(tool_name, args_dict), ...]
    """
    parsed = []
    for tc in (tool_calls or []):
        try:
            func = tc.get("function", {})
            name = func.get("name", "")
            args = json.loads(func.get("arguments", "{}"))
            parsed.append((name, args))
        except (json.JSONDecodeError, AttributeError) as e:
            logger.warning("Trout tool_call 解析失败: %s", e)
    return parsed
