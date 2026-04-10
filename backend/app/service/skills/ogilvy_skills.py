"""
Ogilvy Agent (品牌顾问) 的核心功能库 (Tools/Skills Definition)
定义供大模型调用的工具 JSON Schema 以及配套的回调逻辑协议。
"""

from typing import Any, Optional, Dict, List

# ==========================================
# 1. Tool JSON Schema Definitions
# ==========================================

OGILVY_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "clarify_requirement",
            "description": "当用户输入的需求过于模糊，缺乏核心品牌要素（如：只说'我要做个女装品牌'，却不说明人群和定位）时调用此技能，中断流程并向用户发问，索取关键信息。",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "以首席品牌顾问的口吻，向用户提出具体的问题文本，要求其补充信息。"
                    }
                },
                "required": ["question"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "request_human_approval",
            "description": "当出现多个可行的战略方向，必须由客户决策后（例如：战略阶段产出了3个slogan，需要选一个）才能向下游推进视觉/内容设计时，调用此功能悬停系统并等待用户回复。",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "向用户说明目前的多个选项，并询问对方倾向哪一个方案的话术文本。"
                    }
                },
                "required": ["question"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_workflow_dag",
            "description": "当需求足够清晰，或用户已给出明确方向时调用。基于需求，产出下游 Agent (market, strategy, content, visual) 的详细工作流依赖，并正式启动后置流程。",
            "parameters": {
                "type": "object",
                "properties": {
                    "routing_sequence": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": ["market", "strategy", "content", "visual"]
                        },
                        "description": (
                            "本次需要调用的 Agent 顺序列表。"
                            "根据用户实际需求精准选择，只唤醒真正需要的 Agent，不多不少。"
                            "可选值：market（市场研究）、strategy（品牌战略）、"
                            "content（内容策划）、visual（视觉设计）。"
                            "NOTE：Agent 间的上游数据依赖由系统自动处理，"
                            "你只需根据用户需求判断哪些 Agent 应该被调用即可。"
                        )
                    },
                    "plan_explanation": {
                        "type": "string",
                        "description": (
                            "对本次路由安排的简短说明，应包含行业标签及偏重分析方向，"
                            "供下游 Agent 接收到更精准的分析指令上下文。例如："
                            "'消费品·食品饮料赛道，健康化趋势 + 情绪价值打法，先做竞争格局扫描，再落品牌战略。'"
                        )
                    }
                },
                "required": ["routing_sequence"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "direct_response",
            "description": (
                "当用户输入的是轻量咋询、概念探讨、命名建议、思路趋应、递交与说明等 —— "
                "而非需要完整品牌研究工作流时，调用此工具。"
                "典型场景示例："
                "① 命名/拼写建议（如‘这个名字如何？’）。"
                "② 品牌概念解释。"
                "③ 递交语言建议或优化。"
                "④ 轻量的动手前咒语或思路趋应。"
                "⑤ 单一问题的咨询解答。"
                "瞫勿调用此工具处理需要市场研究、品牌战略、内容制作或视觉设计的完整项目。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "response_prompt": {
                        "type": "string",
                        "description": (
                            "一段精准描述你将要回答的角度和要点的提示语（即你准备具体说什么）。"
                            "示例：'分析 Brandin 作为品牌咨询智能体名字的适合性，主要从语言学和品牌脉络分析。'"
                        )
                    }
                },
                "required": ["response_prompt"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_uploaded_asset",
            "description": "遇到用户上传图片、商业计划书、竞品海报等材料时调用。目前系统先做底层请求拦截，用以未来支持多模态分析提取。",
            "parameters": {
                "type": "object",
                "properties": {
                    "asset_focus": {
                        "type": "string",
                        "description": "你想让系统从这个文件中提取关注什么维度的信息？例如：'提取竞品海报的视觉风格' 或 '总结该计划书的主流消费群体'。"
                    }
                },
                "required": ["asset_focus"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "conduct_brand_diligence",
            "description": "当用户的需求中提到了真实存在的成熟品牌、或者是正在市面上运作的新创立品牌，且当前会话中尚未查寻过该品牌时调用。系统将去全网抽调该品牌的底层商业结构、客群和近况，生成《核心参谋部·品牌背调档案》供你和全组使用。调研结束后，你仍需继续规划下一步动作。",
            "parameters": {
                "type": "object",
                "properties": {
                    "search_query": {
                        "type": "string",
                        "description": "为了充分摸底该品牌而在搜索引擎上使用的精确关键字。例如：'茶颜悦色 品牌定位 核心受众'"
                    },
                    "intent_statement": {
                        "type": "string",
                        "description": "严格遵照【90/10法则】，用一句极具高管顾问气场的从容开场白（可带些许点评或幽默幽默感），告诉客户你正在去全网摸底该品牌的基本盘。例如：'这个品牌的打法有点意思。给我几秒钟，我先去各大平台扫一眼它目前的声量底盘... 🔎'"
                    }
                },
                "required": ["search_query", "intent_statement"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "lightweight_web_search",
            "description": "当回答需要新鲜、时效性强的外部数据支撑（如最新政策、特斯拉下月发布会、近期竞品动态）时调用。会动用后端的 Tavily 搜索引擎抓取内容后再回答。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "要搜索的精准互联网关键词。"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "export_final_deliverable",
            "description": "当用户说 '帮我导出一份结案报告' 或 '整理成一份PDF下载' 时调用。系统会打包所有成果生成一份正式报告给用户下载。",
            "parameters": {
                "type": "object",
                "properties": {
                    "document_title": {
                        "type": "string",
                        "description": "生成的正式文档标题"
                    }
                },
                "required": ["document_title"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "revert_to_checkpoint",
            "description": "当用户明确要求撤销重来，或指明要『退回到第X版的建议』时调用。系统将物理擦除之后的失败轮次数据，瞬间恢复干净记录。",
            "parameters": {
                "type": "object",
                "properties": {
                    "target_round": {
                        "type": "integer",
                        "description": "想要回滚到的具体历史轮次数字（基于自然回答，如第一版就是 1）。"
                    },
                    "explanation": {
                        "type": "string",
                        "description": "告诉用户系统已恢复到哪一版的话术"
                    }
                },
                "required": ["target_round", "explanation"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delegate_agent_patch",
            "description": "当用户基于历史生成的跑通了的专业报告（例如品牌屋、分析图），给出非常明确细微的【局部热更新】要求时调用（例如：把品牌屋的口号换了、第二点改年轻点）。这会启动隐形无感流转。",
            "parameters": {
                "type": "object",
                "properties": {
                    "agent": {
                        "type": "string",
                        "enum": ["market", "strategy", "content", "visual"],
                        "description": "要委托去进行局部修改的专业模型。例如如果是针对战略屋、Slogan的修改，填 strategy。"
                    },
                    "task": {
                        "type": "string",
                        "description": "具体要求专业模型执行的局部修改任务指令（例如：'将品牌屋的 Roof 愿景改为更加激进的口号'）。"
                    }
                },
                "required": ["agent", "task"]
            }
        }
    }
]

# ==========================================
# 2. Tool Parser Helper
# ==========================================

def parse_ogilvy_tool_calls(tool_calls: List[dict]) -> Optional[Dict[str, Any]]:
    """
    辅助函数：解析模型返回的 Tool Calls
    优先获取第一个调用的函数并返回其方法和参数。
    """
    import json
    
    if not tool_calls:
        return None
        
    first_tool = tool_calls[0]
    func_name = first_tool.get("function", {}).get("name")
    args_str = first_tool.get("function", {}).get("arguments", "{}")
    
    try:
        args = json.loads(args_str)
    except Exception:
        args = {}
        
    return {
        "action": func_name,
        "args": args
    }
