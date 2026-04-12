"""
内容策划 Agent (Lois) 技能库 v2.0

职责归口说明：
  命名（Naming）和品牌口号（Slogan）均由品牌战略 Agent Trout 负责。
  Lois 以 Trout 输出的名字和口号为既定前提，专注内容执行层。

工具分三组：
  A. 通用工具
     ① clarify_content_requirement  — 信息不足时主动追问（触发全局挂起）

  B. 单兵执行工具（Execution Tools）—— 独立承接用户具体创作诉求
     ② write_short_video_script     — 短视频脚本（钩子 / 分镜 / CTA / BGM）
     ③ write_live_streaming_script  — 直播带货脚本（开场 / 讲品 / 互动 / 逼单）
     ④ plan_marketing_event         — 营销活动策划（主题 / 节点 / 物料 / 传播）
     ⑤ write_content_titles         — 多平台爆款标题批量生成

  C. 全案工具（Full-Plan Tools）—— 品牌内容策略完整推演
     ⑥ define_brand_voice           — 品牌语感系统（人格 / 调性词库 / 禁忌语）
     ⑦ draft_brand_story            — 品牌故事创作（标准版 + 电梯演讲版）
     ⑧ build_social_matrix          — 全渠道社交媒体内容矩阵
     ⑨ design_kol_koc_strategy      — KOL/KOC 投放策略与关键词防线
     ⑩ synthesize_content_report    — 汇总报告并生成 Handoff 交接至 Scher
"""
from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════
# 1. LOIS_TOOLS — JSON Schema 定义（Execution + Full-Plan）
# ══════════════════════════════════════════════════════════════

LOIS_TOOLS: list[dict] = [

    # ─── A. 通用追问工具 ─────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "clarify_content_requirement",
            "description": (
                "当完成当前内容任务的关键信息缺失时调用。"
                "触发后系统将挂起流程，等待用户补充信息后继续。"
                "此工具优先级最高，在开始任何创作之前检查信息完整性。"
            ),
            "parameters": {
                "type": "object",
                "required": ["missing_info_type", "question"],
                "properties": {
                    "missing_info_type": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": [
                                "product_or_service",   # 产品/服务核心卖点不清晰
                                "target_audience",       # 目标人群不明确
                                "brand_tone",            # 调性方向未确定
                                "platform_or_channel",   # 发布平台/渠道未指定
                                "content_goal",          # 内容目标（种草/转化/曝光）未说明
                                "event_budget",          # 活动预算区间不明
                                "video_duration",        # 视频时长未指定
                                "live_product_price",    # 直播产品定价未给出
                            ],
                        },
                        "description": "缺失的信息类型列表（可多选）",
                    },
                    "question": {
                        "type": "string",
                        "description": (
                            "向用户发起的简洁追问。语气要符合 Lois 的人格：直接、有洞察、带点创意腔调。"
                            "绝对不允许一口气问超过 3 个问题，优先问最影响创作方向的那 1-2 个。"
                        ),
                    },
                },
            },
        },
    },

    # ─── B. 单兵执行工具 ──────────────────────────────────────────

    # ② 短视频脚本
    {
        "type": "function",
        "function": {
            "name": "write_short_video_script",
            "description": (
                "为短视频平台创作完整脚本。"
                "适用诉求：写抖音/视频号/小红书脚本、创作短视频内容、策划视频选题等。"
                "输出完整的开头钩子、分镜台词、CTA 和 BGM 情绪建议。"
            ),
            "parameters": {
                "type": "object",
                "required": ["platform", "product_or_topic", "core_selling_point", "target_audience", "tone", "duration_seconds"],
                "properties": {
                    "platform": {
                        "type": "string",
                        "enum": ["douyin", "weixin_channels", "kuaishou", "bilibili", "xiaohongshu", "general"],
                        "description": "发布平台，决定节奏规律和语言风格",
                    },
                    "product_or_topic": {
                        "type": "string",
                        "description": "视频的主角：产品名 / 品牌名 / 选题方向",
                    },
                    "core_selling_point": {
                        "type": "string",
                        "description": "最想让用户记住的那一句话（核心 USP）",
                    },
                    "target_audience": {
                        "type": "string",
                        "description": "核心目标人群画像（例如：25-35岁都市白领女性，对职场焦虑有共鸣）",
                    },
                    "tone": {
                        "type": "string",
                        "enum": ["emotional_resonance", "knowledge_sharing", "entertainment", "sales_conversion", "brand_story"],
                        "description": "内容基调：情感共鸣 / 知识干货 / 娱乐轻松 / 直接转化 / 品牌故事",
                    },
                    "duration_seconds": {
                        "type": "integer",
                        "enum": [15, 30, 60, 90, 180, 300],
                        "description": "视频时长（秒），决定脚本分段数量和节奏密度",
                    },
                    "hook_type": {
                        "type": "string",
                        "enum": ["question", "conflict", "data_shock", "scene_immersion", "emotion_trigger"],
                        "description": "开头钩子类型：提问/矛盾冲突/数据冲击/场景代入/情绪触发（可选，不填则由 Lois 自主判断）",
                    },
                    "special_requirement": {
                        "type": "string",
                        "description": "特殊要求备注（可选）",
                    },
                },
            },
        },
    },

    # ③ 直播脚本
    {
        "type": "function",
        "function": {
            "name": "write_live_streaming_script",
            "description": (
                "为直播带货或直播活动创作完整话术脚本。"
                "适用诉求：写直播稿、直播话术、带货脚本、开播词等。"
                "产出开场词、产品讲解节奏模板、互动话术钩子、逼单话术和收场词。"
            ),
            "parameters": {
                "type": "object",
                "required": ["product_name", "product_price", "core_usp", "target_audience", "session_duration_minutes"],
                "properties": {
                    "product_name": {
                        "type": "string",
                        "description": "直播主推产品或品牌名称",
                    },
                    "product_price": {
                        "type": "string",
                        "description": "产品价格区间（例如：日常价199，直播优惠价129）",
                    },
                    "core_usp": {
                        "type": "string",
                        "description": "产品最核心的差异化卖点（主打成分/功能/情感价值）",
                    },
                    "target_audience": {
                        "type": "string",
                        "description": "直播间核心目标观众群体画像",
                    },
                    "session_duration_minutes": {
                        "type": "integer",
                        "description": "直播时长（分钟），决定节点分布密度",
                    },
                    "live_type": {
                        "type": "string",
                        "enum": ["ecommerce_sales", "brand_showcase", "product_launch", "interactive_entertainment"],
                        "description": "直播类型：带货销售 / 品牌宣传 / 新品发布 / 娱乐互动（可选）",
                    },
                    "gifting_mechanism": {
                        "type": "string",
                        "description": "是否有赠品、限时折扣、秒杀等促销机制（可选）",
                    },
                },
            },
        },
    },

    # ④ 活动策划
    {
        "type": "function",
        "function": {
            "name": "plan_marketing_event",
            "description": (
                "制定品牌营销活动完整策划案。"
                "适用诉求：做活动策划、写活动方案、策划节日营销/品牌周年/新品发布/联名活动等。"
                "产出：活动主题创意、执行节点、物料清单、线上传播配合、KPI 目标。"
            ),
            "parameters": {
                "type": "object",
                "required": ["event_type", "brand_name", "target_outcome", "timeline_weeks"],
                "properties": {
                    "event_type": {
                        "type": "string",
                        "enum": ["product_launch", "brand_anniversary", "seasonal_sale", "brand_collab", "flash_sale", "community_event", "holiday_campaign"],
                        "description": "活动类型：新品发布/品牌周年/季节大促/品牌联名/限时秒杀/社群活动/节假日营销",
                    },
                    "brand_name": {
                        "type": "string",
                        "description": "品牌名称",
                    },
                    "event_theme_hint": {
                        "type": "string",
                        "description": "活动主题方向初步设想（可选，留空则由 Lois 自主提案）",
                    },
                    "budget_range": {
                        "type": "string",
                        "description": "活动预算区间（例如：10万以内 / 10-50万 / 不限），决定执行规模",
                    },
                    "target_outcome": {
                        "type": "string",
                        "description": "活动核心目标（品牌曝光/销售转化/新客拉新/用户留存）",
                    },
                    "timeline_weeks": {
                        "type": "integer",
                        "description": "从现在到活动结束的总周期（周数），决定执行计划的节奏",
                    },
                    "special_requirement": {
                        "type": "string",
                        "description": "特别说明（例如：线上为主/线下有门店资源/有网红合作资源等，可选）",
                    },
                },
            },
        },
    },

    # ⑤ 标题批量生成
    {
        "type": "function",
        "function": {
            "name": "write_content_titles",
            "description": (
                "批量生成多平台、多角度的爆款标题或创意文案标题。"
                "适用诉求：写标题、起标题、帮我想几个选题名字、标题优化等。"
                "根据不同平台调性输出差异化的标题矩阵。"
            ),
            "parameters": {
                "type": "object",
                "required": ["topic", "platforms", "count_per_platform"],
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "标题的核心主题或内容方向",
                    },
                    "platforms": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": ["xiaohongshu", "douyin", "weixin_gongzhonghao", "weibo", "bilibili", "zhihu", "general"],
                        },
                        "description": "需要生成标题的平台列表",
                    },
                    "product_or_brand": {
                        "type": "string",
                        "description": "涉及的产品或品牌名（可选），有助于精准化标题",
                    },
                    "emotion_angle": {
                        "type": "string",
                        "description": "情绪切入角度（例如：焦虑/向往/惊喜/认同，可选）",
                    },
                    "count_per_platform": {
                        "type": "integer",
                        "description": "每个平台生成的标题数量，建议 3-8 个",
                    },
                    "title_style": {
                        "type": "string",
                        "enum": ["question", "list", "contrast", "data", "emotional", "mixed"],
                        "description": "标题风格偏好：疑问型/列表型/对比型/数据冲击/情感共鸣/混合（可选）",
                    },
                },
            },
        },
    },

    # ─── C. 全案工具 ───────────────────────────────────────────────

    # ⑥ 品牌语感系统
    {
        "type": "function",
        "function": {
            "name": "define_brand_voice",
            "description": (
                "【全案第一步必须调用】为品牌建立完整的语感系统（Brand Voice System）。"
                "输出品牌的说话人格、调性关键词库、禁忌语清单、以及跨渠道一致性指令。"
                "后续所有创作工具以此为基准框架，确保品牌口径统一。"
            ),
            "parameters": {
                "type": "object",
                "required": ["brand_name", "brand_persona", "tone_keywords", "forbidden_words", "channel_consistency_note"],
                "properties": {
                    "brand_name": {"type": "string"},
                    "brand_persona": {
                        "type": "string",
                        "description": "品牌人格化描述（用'就像一个人'的方式描述，例如：就像你身边那个既懂成分学又幽默随性的美妆闺蜜）",
                    },
                    "tone_keywords": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "品牌核心调性词汇（6-10个）",
                    },
                    "forbidden_words": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "绝对禁止使用的词汇或表达习惯（例如：'震惊'、'逆天'、夸大感叹号）",
                    },
                    "channel_consistency_note": {
                        "type": "string",
                        "description": "跨渠道一致性要求（例如：无论公众号长文还是小红书九宫格，语气偏差不超过20%）",
                    },
                    "signature_phrases": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "品牌专属标志性用语（可选，例如：'科学护肤不将就'，供文案复用加强记忆）",
                    },
                    "voice_conclusion": {
                        "type": "string",
                        "description": "品牌语感系统一句话总结（供后续工具引用）",
                    },
                },
            },
        },
    },

    # ⑦ 品牌故事
    {
        "type": "function",
        "function": {
            "name": "draft_brand_story",
            "description": (
                "创作品牌故事（Brand Story）。"
                "产出标准版（300字，围绕起源/问题/承诺三段结构）和"
                "电梯演讲版（50字，可在任何场合快速传播）。"
            ),
            "parameters": {
                "type": "object",
                "required": ["brand_name", "founder_background", "problem_solved", "brand_promise", "story_type"],
                "properties": {
                    "brand_name": {"type": "string"},
                    "founder_background": {
                        "type": "string",
                        "description": "品牌创始人/团队背景与初心（真实经历最佳）",
                    },
                    "problem_solved": {
                        "type": "string",
                        "description": "品牌解决了目标消费者生活中的什么具体问题",
                    },
                    "brand_promise": {
                        "type": "string",
                        "description": "品牌对消费者的核心承诺",
                    },
                    "story_type": {
                        "type": "string",
                        "enum": ["hero_journey", "discovery_moment", "rebellion_against_ordinary", "origin_of_change"],
                        "description": "故事叙事结构：英雄之旅/发现时刻/对平庸的反叛/改变的起点",
                    },
                    "emotional_core": {
                        "type": "string",
                        "description": "故事情感内核（用一种情绪描述：信念/愤怒/温暖/好奇，可选）",
                    },
                    "story_standard": {
                        "type": "string",
                        "description": "标准版故事正文（300字左右，由 Lois 创作）",
                    },
                    "story_elevator": {
                        "type": "string",
                        "description": "电梯演讲版（50字以内的一句话故事，由 Lois 创作）",
                    },
                },
            },
        },
    },

    # ⑧ 社交媒体内容矩阵
    {
        "type": "function",
        "function": {
            "name": "build_social_matrix",
            "description": (
                "制定全渠道社交媒体内容矩阵：每个平台的内容方向、发布节奏、内容形式和核心目的。"
                "会根据品牌行业（To C / To B）和目标人群自动匹配适合的平台组合。"
            ),
            "parameters": {
                "type": "object",
                "required": ["brand_name", "brand_type", "primary_audience", "channels"],
                "properties": {
                    "brand_name": {"type": "string"},
                    "brand_type": {
                        "type": "string",
                        "enum": ["to_c_mass", "to_c_premium", "to_b", "lifestyle", "local_business"],
                        "description": "品牌类型决定平台权重：大众消费品/高端消费品/B端/生活方式/本地商家",
                    },
                    "primary_audience": {"type": "string"},
                    "channels": {
                        "type": "array",
                        "description": "要覆盖的渠道矩阵",
                        "items": {
                            "type": "object",
                            "required": ["platform", "content_direction", "frequency", "format", "goal"],
                            "properties": {
                                "platform": {
                                    "type": "string",
                                    "enum": ["xiaohongshu", "douyin", "weixin_gongzhonghao", "weixin_channels", "weibo", "bilibili", "zhihu", "linkedin"],
                                },
                                "content_direction": {"type": "string", "description": "该平台的内容方向（例如：成分科普种草 / 创始人日常 vlog）"},
                                "frequency": {"type": "string", "description": "建议发布频率（例如：每周 2-3 篇）"},
                                "format": {"type": "string", "description": "主要内容形式（例如：9图+长文 / 15-60s 短视频 / 图文混排）"},
                                "goal": {
                                    "type": "string",
                                    "enum": ["awareness", "engagement", "conversion", "retention", "seo"],
                                    "description": "该渠道的核心传播目的",
                                },
                            },
                        },
                    },
                    "month1_content_theme": {
                        "type": "string",
                        "description": "首月重点传播主题方向",
                    },
                },
            },
        },
    },

    # ⑩ KOL/KOC 策略与关键词防线
    {
        "type": "function",
        "function": {
            "name": "design_kol_koc_strategy",
            "description": (
                "制定 KOL/KOC 投放矩阵和搜索引擎/平台内部关键词防线策略。"
                "决定'哪些人帮品牌说话'和'用户主动搜索时能不能被找到'。"
            ),
            "parameters": {
                "type": "object",
                "required": ["brand_name", "kol_tiers", "core_keywords", "long_tail_keywords", "hashtags"],
                "properties": {
                    "brand_name": {"type": "string"},
                    "kol_tiers": {
                        "type": "array",
                        "description": "KOL/KOC 投放层级组合设计",
                        "items": {
                            "type": "object",
                            "required": ["tier", "follower_range", "content_type", "budget_ratio", "rationale"],
                            "properties": {
                                "tier": {
                                    "type": "string",
                                    "enum": ["S_class", "head_kol", "mid_kol", "tail_koc", "ugc_seeding"],
                                },
                                "follower_range": {"type": "string"},
                                "content_type": {"type": "string"},
                                "budget_ratio": {"type": "string", "description": "占总投放预算的比例（例如：30%）"},
                                "rationale": {"type": "string"},
                            },
                        },
                    },
                    "core_keywords": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "核心品牌关键词（5个，要有强记忆点）",
                    },
                    "long_tail_keywords": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "长尾搜索关键词（10个，覆盖用户真实搜索路径）",
                    },
                    "hashtags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "社交媒体话题标签 Hashtag（10个，兼顾大中小体量）",
                    },
                },
            },
        },
    },

    # ⑩ 全案汇总报告
    {
        "type": "function",
        "function": {
            "name": "synthesize_content_report",
            "description": (
                "【全案最后一步】将所有工具产出整合为完整的内容策略报告，"
                "并生成关键的 Handoff 交接信息传递给视觉 Agent Scher。"
            ),
            "parameters": {
                "type": "object",
                "required": [
                    "executed_tools",
                    "handoff_slogan",
                    "handoff_brand_voice_keywords",
                    "handoff_top_channels",
                    "handoff_visual_style_direction",
                    "handoff_content_theme_month1",
                ],
                "properties": {
                    "executed_tools": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "本次执行的工具列表（用于报告目录）",
                    },
                    "handoff_slogan": {
                        "type": "string",
                        "description": "首选推荐 Slogan（含理由）",
                    },
                    "handoff_brand_voice_keywords": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "调性关键词（3个，Scher 必须对齐）",
                    },
                    "handoff_top_channels": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "主力传播渠道 TOP 2",
                    },
                    "handoff_visual_style_direction": {
                        "type": "string",
                        "description": "给 Scher 的视觉风格指令（例如：色调需温暖克制，禁止使用过饱和霓虹色，主视觉元素围绕'轻盈'展开）",
                    },
                    "handoff_content_theme_month1": {
                        "type": "string",
                        "description": "首月核心传播主题",
                    },
                },
            },
        },
    },
]

# NOTE: 单兵执行车道只暴露追问工具 + 4个执行工具，不加载全案工具
LOIS_EXECUTION_TOOLS: list[dict] = [t for t in LOIS_TOOLS if t["function"]["name"] in {
    "clarify_content_requirement",
    "write_short_video_script",
    "write_live_streaming_script",
    "plan_marketing_event",
    "write_content_titles",
}]


# ══════════════════════════════════════════════════════════════
# 2. Tool Executor Functions（工具执行回调）
# ══════════════════════════════════════════════════════════════

def execute_clarify_content_requirement(args: dict[str, Any]) -> str:
    """将追问信号透传给 content_agent.py，由其 yield AGENT_CLARIFY_MARKER。"""
    return f"__CLARIFY_REQUIRED__:{args.get('question', '')}"


def execute_write_short_video_script(args: dict[str, Any]) -> str:
    """构建短视频脚本创作指令摘要，供 LLM 生成最终脚本用。"""
    platform_labels = {
        "douyin": "抖音", "weixin_channels": "视频号", "kuaishou": "快手",
        "bilibili": "B站", "xiaohongshu": "小红书", "general": "通用短视频平台",
    }
    tone_labels = {
        "emotional_resonance": "情感共鸣", "knowledge_sharing": "知识干货",
        "entertainment": "娱乐轻松", "sales_conversion": "直接转化", "brand_story": "品牌故事",
    }
    result = (
        f"【短视频脚本创作参数确认】\n"
        f"平台：{platform_labels.get(args.get('platform', ''), args.get('platform', ''))}\n"
        f"主角：{args.get('product_or_topic', '')}\n"
        f"核心卖点：{args.get('core_selling_point', '')}\n"
        f"目标人群：{args.get('target_audience', '')}\n"
        f"内容基调：{tone_labels.get(args.get('tone', ''), args.get('tone', ''))}\n"
        f"视频时长：{args.get('duration_seconds', '')}秒\n"
        f"开头类型：{args.get('hook_type', '由 Lois 自主判断')}\n"
        f"特殊要求：{args.get('special_requirement', '无')}\n\n"
        "请基于以上确认参数，完整创作：① 开头钩子（前3秒）② 视频结构与台词分镜 ③ CTA（行动号召）④ BGM 情绪建议"
    )
    logger.info("短视频脚本参数确认：平台=%s, 时长=%ss", args.get("platform"), args.get("duration_seconds"))
    return result


def execute_write_live_streaming_script(args: dict[str, Any]) -> str:
    """构建直播脚本创作指令摘要。"""
    result = (
        f"【直播脚本创作参数确认】\n"
        f"主推产品：{args.get('product_name', '')}\n"
        f"产品价格：{args.get('product_price', '')}\n"
        f"核心卖点：{args.get('core_usp', '')}\n"
        f"目标观众：{args.get('target_audience', '')}\n"
        f"直播时长：{args.get('session_duration_minutes', '')}分钟\n"
        f"直播类型：{args.get('live_type', '带货销售')}\n"
        f"促销机制：{args.get('gifting_mechanism', '无特别说明')}\n\n"
        "请基于以上确认参数，完整创作：① 开场词（前5分钟暖场）② 产品讲解节奏模板 "
        "③ 互动话术钩子（评论/抽奖/提问引导）④ 逼单话术组合 ⑤ 收场词（引导关注/留存）"
    )
    logger.info("直播脚本参数确认：产品=%s, 时长=%s分钟", args.get("product_name"), args.get("session_duration_minutes"))
    return result


def execute_plan_marketing_event(args: dict[str, Any]) -> str:
    """构建活动策划创作指令摘要。"""
    event_type_labels = {
        "product_launch": "新品发布", "brand_anniversary": "品牌周年庆",
        "seasonal_sale": "季节大促", "brand_collab": "品牌联名",
        "flash_sale": "限时秒杀", "community_event": "社群活动", "holiday_campaign": "节假日营销",
    }
    result = (
        f"【活动策划参数确认】\n"
        f"活动类型：{event_type_labels.get(args.get('event_type', ''), args.get('event_type', ''))}\n"
        f"品牌名称：{args.get('brand_name', '')}\n"
        f"主题初步设想：{args.get('event_theme_hint', '（请 Lois 自主提案）')}\n"
        f"预算区间：{args.get('budget_range', '未说明')}\n"
        f"核心目标：{args.get('target_outcome', '')}\n"
        f"执行周期：{args.get('timeline_weeks', '')}周\n"
        f"特殊资源/约束：{args.get('special_requirement', '无')}\n\n"
        "请基于以上确认参数，完整创作：① 活动主题创意（含口号）② 执行节点时间线 "
        "③ 线上传播配合方案 ④ 物料清单 ⑤ KPI 目标建议"
    )
    logger.info("活动策划参数确认：类型=%s, 品牌=%s", args.get("event_type"), args.get("brand_name"))
    return result


def execute_write_content_titles(args: dict[str, Any]) -> str:
    """构建标题生成指令摘要。"""
    platform_labels = {
        "xiaohongshu": "小红书", "douyin": "抖音", "weixin_gongzhonghao": "微信公众号",
        "weibo": "微博", "bilibili": "B站", "zhihu": "知乎", "general": "通用",
    }
    platforms_text = " / ".join(
        platform_labels.get(p, p) for p in args.get("platforms", [])
    )
    result = (
        f"【标题生成参数确认】\n"
        f"核心主题：{args.get('topic', '')}\n"
        f"涉及产品/品牌：{args.get('product_or_brand', '无')}\n"
        f"目标平台：{platforms_text}\n"
        f"每平台数量：{args.get('count_per_platform', 5)}个\n"
        f"情绪角度：{args.get('emotion_angle', '由 Lois 自主发挥')}\n"
        f"风格偏好：{args.get('title_style', '混合')}\n\n"
        "请基于以上确认参数，按平台分组批量生成爆款标题，每个标题附简要说明为何有吸引力。"
    )
    logger.info("标题生成参数确认：主题=%s, 平台=%s", args.get("topic"), platforms_text)
    return result


def execute_define_brand_voice(args: dict[str, Any]) -> str:
    """提取品牌语感系统结果。"""
    tone_keywords = " / ".join(args.get("tone_keywords", []))
    forbidden_words = " / ".join(args.get("forbidden_words", []))
    signature_phrases = " / ".join(args.get("signature_phrases", [])) or "待定"
    result = (
        f"【品牌语感系统建立完成 · {args.get('brand_name', '')}】\n"
        f"品牌人格：{args.get('brand_persona', '')}\n"
        f"核心调性词：{tone_keywords}\n"
        f"禁忌语清单：{forbidden_words}\n"
        f"标志性用语：{signature_phrases}\n"
        f"跨渠道一致性指令：{args.get('channel_consistency_note', '')}\n"
        f"语感总结：{args.get('voice_conclusion', '')}"
    )
    logger.info("品牌语感系统建立完成：%s", args.get("brand_name"))
    return result


def execute_draft_brand_story(args: dict[str, Any]) -> str:
    """提取品牌故事创作结果。"""
    result = (
        f"【品牌故事创作完成 · {args.get('brand_name', '')}】\n"
        f"叙事结构：{args.get('story_type', '')}\n"
        f"情感内核：{args.get('emotional_core', '待定')}\n"
        f"标准版（300字）：{args.get('story_standard', '（由 LLM 在最终报告中创作）')}\n"
        f"电梯演讲版：{args.get('story_elevator', '（由 LLM 在最终报告中创作）')}"
    )
    logger.info("品牌故事参数确认，将在最终报告中进行创作")
    return result


def execute_build_social_matrix(args: dict[str, Any]) -> str:
    """提取社交媒体矩阵配置。"""
    channels = args.get("channels", [])
    channels_text = "\n".join(
        f"  [{c.get('platform', '')}] 方向：{c.get('content_direction', '')} | 频率：{c.get('frequency', '')} | 形式：{c.get('format', '')} | 目标：{c.get('goal', '')}"
        for c in channels
    )
    result = (
        f"【社交媒体内容矩阵建立完成 · {args.get('brand_name', '')}】\n"
        f"品牌类型：{args.get('brand_type', '')} | 核心人群：{args.get('primary_audience', '')}\n"
        f"渠道矩阵：\n{channels_text}\n"
        f"首月传播主题：{args.get('month1_content_theme', '')}"
    )
    logger.info("社交媒体矩阵建立完成：%s 个渠道", len(channels))
    return result


def execute_design_kol_koc_strategy(args: dict[str, Any]) -> str:
    """提取 KOL/KOC 投放策略。"""
    tiers = args.get("kol_tiers", [])
    tiers_text = "\n".join(
        f"  {t.get('tier', '')}（{t.get('follower_range', '')}）：{t.get('content_type', '')} | 预算占比：{t.get('budget_ratio', '')} | 理由：{t.get('rationale', '')}"
        for t in tiers
    )
    core_kw = " · ".join(args.get("core_keywords", []))
    hashtags = "  ".join(f"#{h}" for h in args.get("hashtags", []))
    result = (
        f"【KOL/KOC 策略完成 · {args.get('brand_name', '')}】\n"
        f"投放层级：\n{tiers_text}\n"
        f"核心关键词：{core_kw}\n"
        f"Hashtag 防线：{hashtags}"
    )
    logger.info("KOL/KOC 策略建立完成")
    return result


def execute_synthesize_content_report(args: dict[str, Any]) -> str:
    """生成报告触发标记，供 content_agent.py 识别后生成最终流式报告。"""
    logger.info("Lois 全案工具执行完毕，准备生成最终报告")
    return json.dumps({
        "trigger": "synthesize_content_report",
        "executed_tools": args.get("executed_tools", []),
        "handoff_slogan": args.get("handoff_slogan", ""),
        "handoff_brand_voice_keywords": args.get("handoff_brand_voice_keywords", []),
        "handoff_top_channels": args.get("handoff_top_channels", []),
        "handoff_visual_style_direction": args.get("handoff_visual_style_direction", ""),
        "handoff_content_theme_month1": args.get("handoff_content_theme_month1", ""),
    }, ensure_ascii=False, indent=2)


# ══════════════════════════════════════════════════════════════
# 3. Tool Dispatcher
# ══════════════════════════════════════════════════════════════

LOIS_TOOL_EXECUTORS: dict[str, Any] = {
    # 通用
    "clarify_content_requirement":  execute_clarify_content_requirement,
    # 单兵执行
    "write_short_video_script":     execute_write_short_video_script,
    "write_live_streaming_script":  execute_write_live_streaming_script,
    "plan_marketing_event":         execute_plan_marketing_event,
    "write_content_titles":         execute_write_content_titles,
    # 全案
    "define_brand_voice":           execute_define_brand_voice,
    "draft_brand_story":            execute_draft_brand_story,
    "build_social_matrix":          execute_build_social_matrix,
    "design_kol_koc_strategy":      execute_design_kol_koc_strategy,
    "synthesize_content_report":    execute_synthesize_content_report,
}


def dispatch_lois_tool(tool_name: str, args: dict[str, Any]) -> str:
    """统一工具分发入口。"""
    executor = LOIS_TOOL_EXECUTORS.get(tool_name)
    if executor:
        try:
            return executor(args)
        except Exception as e:
            logger.error("Lois 工具 %s 执行失败：%s", tool_name, e, exc_info=True)
            return f"[工具执行错误] {tool_name}: {e}"
    logger.warning("未知 Lois 工具：%s", tool_name)
    return f"[未知工具] {tool_name}"
