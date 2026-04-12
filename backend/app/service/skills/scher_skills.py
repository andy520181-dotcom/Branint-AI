import logging
from typing import Any

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════
# 1. Tool Schemas（大模型可见的工具定义）
# ══════════════════════════════════════════════════════════════

SCHER_TOOLS: list[dict] = [
    # ① 通用打回工具
    {
        "type": "function",
        "function": {
            "name": "clarify_visual_requirement",
            "description": (
                "遇到用户指定的单兵短任务（例如'画个Logo'、'生成一张海报'），且缺乏关键品牌调性、"
                "颜色偏好、核心传播诉求等前提信息时调用。调用此工具将立即挂起当前流水线，由你向用户反问。"
            ),
            "parameters": {
                "type": "object",
                "required": ["question"],
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "以顶尖美术指导的口吻向用户提出一个极其精准、有针对性的问题。不要废话，直击核心盲区。",
                    }
                },
            },
        },
    },

    # ② 品牌色彩体系
    {
        "type": "function",
        "function": {
            "name": "define_color_system",
            "description": "基于前序 Agent 交接的品牌调性，定义或优化品牌核心及辅助色彩矩阵。",
            "parameters": {
                "type": "object",
                "required": ["primary_color_hex", "primary_color_rationale", "secondary_colors"],
                "properties": {
                    "primary_color_hex": {
                        "type": "string",
                        "description": "品牌主色提取（必须是 #RRGGBB 格式）"
                    },
                    "primary_color_rationale": {
                        "type": "string",
                        "description": "为何选择此作为主色？从受众心理及商业竞争角度解读（限50字）。"
                    },
                    "secondary_colors": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "辅助色或禁忌色定义及搭配场景简述。"
                    }
                }
            }
        }
    },

    # ③ 品牌字体规范
    {
        "type": "function",
        "function": {
            "name": "define_typography_system",
            "description": "配置全案品牌字体框架，规范阅读感知与层级视觉秩序。",
            "parameters": {
                "type": "object",
                "required": ["heading_font", "body_font", "rationale"],
                "properties": {
                    "heading_font": {
                        "type": "string",
                        "description": "中文与英文主标题推荐字体名称（例如：'优设标题黑 / Montserrat'）"
                    },
                    "body_font": {
                        "type": "string",
                        "description": "正文阅读字体建议（例如：'思源黑体 / Inter'）"
                    },
                    "rationale": {
                        "type": "string",
                        "description": "字体对品牌质感的影响考量（限50字）。"
                    }
                }
            }
        }
    },

    # ④ 核心视觉资产（图片生图）
    {
        "type": "function",
        "function": {
            "name": "generate_brand_image",
            "description": (
                "【执行类工具】调度后端 AI 生图模型出图！根据前序策略决定的调性，生成品牌主张海报、Logo概念草图或核心物料概念图。"
                "注意：你作为美术指导，需输出高质量的主体景致和配色 prompt 供底层模型生成图像。"
            ),
            "parameters": {
                "type": "object",
                "required": ["image_type", "midjourney_prompt", "aspect_ratio"],
                "properties": {
                    "image_type": {
                        "type": "string",
                        "enum": ["logo", "banner", "poster"],
                        "description": "要生成的图像类别。"
                    },
                    "midjourney_prompt": {
                        "type": "string",
                        "description": "全英文的高清详细提示词。包含主体、动作、材质、灯光环境、色彩基调、相机视角。例如：Minimalist logo design, gradient geometric shape, clean white background, high end branding, vector style."
                    },
                    "aspect_ratio": {
                        "type": "string",
                        "enum": ["1:1", "16:9", "9:16", "4:3"],
                        "description": "期望的图像比例。Banner选16:9，海报选9:16或3:4，Logo选1:1。"
                    }
                }
            }
        }
    },

    # ⑤ 影视媒体创作（视频生图）
    {
        "type": "function",
        "function": {
            "name": "generate_concept_video",
            "description": (
                "【执行类工具】调度后端视频大模型生成一段 5 秒级别的品牌概念视觉短片。"
                "适用于需要极具动感和情绪价值的多媒体表现（例如：高燃赛博朋克过店流，微距产品特写，宏大叙事场景）。"
            ),
            "parameters": {
                "type": "object",
                "required": ["cinematic_prompt"],
                "properties": {
                    "cinematic_prompt": {
                        "type": "string",
                        "description": "全英文的精准视频运镜提示词，重点描述：画面主体、主体运动轨迹、摄影机运镜方式、光影与情绪。注意不能包含任何不相关的文字！"
                    }
                }
            }
        }
    },

    # ⑥ 最终结案汇编
    {
        "type": "function",
        "function": {
            "name": "synthesize_visual_report",
            "description": (
                "【执行循环最后一环】总结由你（Scher）执行出的所有策略规范与视觉结果，"
                "渲染为具备层级结构的视觉识别总结规范文档。并进行最终全案宣告。"
            ),
            "parameters": {
                "type": "object",
                "required": ["executed_tools", "core_visual_theme"],
                "properties": {
                    "executed_tools": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "本次执行的视觉工具列表。"
                    },
                    "core_visual_theme": {
                        "type": "string",
                        "description": "对本品牌未来所有视觉资产延展的一句话终极准则口诀。"
                    }
                }
            }
        }
    }
]

# 单点轻量化任务白名单（不再加载全套 VIS 思维逻辑）
SCHER_EXECUTION_TOOLS: list[dict] = [t for t in SCHER_TOOLS if t["function"]["name"] in {
    "clarify_visual_requirement",
    "generate_brand_image",
    "generate_concept_video",
}]


# ══════════════════════════════════════════════════════════════
# 2. Tool Executor Functions（纯文本转化逻辑，物理侧拦截处理在 Agent 中实现）
# ══════════════════════════════════════════════════════════════

def execute_clarify_visual_requirement(args: dict[str, Any]) -> str:
    return f"__CLARIFY_REQUIRED__:{args.get('question', '')}"

def execute_define_color_system(args: dict[str, Any]) -> str:
    return f"色彩定义完毕。主色值 {args.get('primary_color_hex')}。\n策略因由：{args.get('primary_color_rationale')}"

def execute_define_typography_system(args: dict[str, Any]) -> str:
    return f"字体架构敲定。标题采用 {args.get('heading_font')}，正文采用 {args.get('body_font')}。"

def execute_synthesize_visual_report(args: dict[str, Any]) -> str:
    return f"__FINAL_REPORT_READY__:{args.get('core_visual_theme')}"
