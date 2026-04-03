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
                        "description": "本次需要调用的 Agent 列表。注意先后顺序或并发关系由服务端解析。"
                    },
                    "plan_explanation": {
                        "type": "string",
                        "description": "向用户解释为什么这么安排流程的话术文本（Markdown）。"
                    }
                },
                "required": ["routing_sequence", "plan_explanation"]
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
