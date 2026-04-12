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
                    "is_micro_task": {
                        "type": "boolean",
                        "description": (
                            "判断本次用户需求是否属于「微型单点任务」。"
                            "设为 true 的典型场景：起名字、写一条 Slogan、改一句文案、"
                            "画一张海报、查一个竞品、出一条创意——这些都是单点微操，绝非全案。"
                            "设为 false 的典型场景：从零打造一个完整品牌、做一整套品牌战略、"
                            "完整的市场调研+定位+视觉全案——这些属于宏大叙事的庞大全案。"
                            "当 is_micro_task=true 时，系统会强制下游 Agent 关闭长文报告模板，"
                            "直接给出简练干脆的结果；当 false 时，Agent 可以火力全开。"
                        ),
                        "default": False
                    },
                    "is_execution_brief": {
                        "type": "boolean",
                        "description": (
                            "仅对 market（Wacksman）Agent 生效。"
                            "设为 true 的典型场景：用户只需了解某单一议题的精准快报，例如："
                            "'帮我快速看一下小红书上的成分护肤竞争格局'、'给我XX品牌的竞品简报'。"
                            "触发后 Wacksman 精准调用 1-3 个工具，输出结构化快报（400-600字），而非完整报告。"
                            "注意：当 is_execution_brief=true 时，is_micro_task 通常为 false。"
                        ),
                        "default": False
                    },
                    "is_pure_advisory": {
                        "type": "boolean",
                        "description": (
                            "仅对 strategy（Trout）Agent 生效。"
                            "设为 true 的典型场景：用户提出无需数据或工具支撑的纯战略概念问答，例如："
                            "'聚焦战略和蓝海战略哪个更适合我的情况？'、'品牌定位和品牌识别有什么区别？'。"
                            "触发后 Trout 完全绕过工具调用循环，直接以资深顾问口吻流式对话，大幅降低响应延迟。"
                            "注意：当 is_pure_advisory=true 时，is_micro_task 通常为 false。"
                        ),
                        "default": False
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
                "当用户输入的是非常轻量的概念探讨、思路验证、情绪安抚与常规说明等 —— "
                "而非需要完整品牌研究工作流时，调用此工具。"
                "典型场景示例："
                "① 极其轻量的概念解释（如‘什么是定位？’）。"
                "② 针对客户简单提问的基础解答。"
                "③ 情绪按摩或进度安抚反馈。"
                "【严格禁忌】：绝对禁止使用此工具越俎代庖完成起名、写 Slogan、做品牌屋等明确属于下游专业 Agent 的实操类创意输出。遇到该类请求，必须通过 `generate_workflow_dag(is_micro_task=True)` 调度下游 Agent 执行！"
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
