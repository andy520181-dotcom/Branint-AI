"""
Wacksman Agent（市场研究专家）的核心功能库
定义供大模型调用的工具 JSON Schema，以及 Tavily 联网检索的执行逻辑。

工作流：
  1. clarify_research_scope  — 确认研究范围（行业/地域/竞品）
  2. web_search_market_data  — 检索市场宏观数据（规模/趋势/政策）
  3. search_competitor_intel — 检索竞品具体情报（定位/价格/融资/声量）
  4. synthesize_research_report — 汇总所有数据，生成最终研究报告 + handoff
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ==========================================
# 1. Tool JSON Schema Definitions
# ==========================================

WACKSMAN_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "clarify_research_scope",
            "description": (
                "当品牌需求信息不足以锁定市场研究范围时调用（如：缺少地域、价格带、核心竞品信息），"
                "中断流程并以市场研究专家身份向用户发问。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "以市场研究专家的口吻提出具体问题，说明需要补充哪些信息才能开始研究。"
                    }
                },
                "required": ["question"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "web_search_market_data",
            "description": (
                "调用真实联网搜索引擎，检索指定品类的宏观市场数据，包括市场规模、增速、消费者趋势、"
                "政策环境等。每次只针对一个具体问题发起搜索。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "精准的检索关键词，例如：'2024年中国轻奢护肤品市场规模增速'。"
                    },
                    "research_angle": {
                        "type": "string",
                        "enum": ["market_size", "consumer_trend", "policy_environment", "channel_distribution"],
                        "description": "本次检索的研究角度，用于标注数据来源。"
                    }
                },
                "required": ["query", "research_angle"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_competitor_intel",
            "description": (
                "针对特定竞品进行专项情报检索，聚焦竞品的品牌定位、价格策略、融资状态、媒体声量、"
                "近期动态等核心维度。每次只检索一个竞品。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "brand_name": {
                        "type": "string",
                        "description": "要检索的竞品品牌名称，例如：'完美日记'、'lululemon'。"
                    },
                    "query": {
                        "type": "string",
                        "description": "针对该竞品的检索词，例如：'lululemon 中国市场定价策略 2024'。"
                    }
                },
                "required": ["brand_name", "query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "synthesize_research_report",
            "description": (
                "完成所有联网检索后调用此技能，将所有搜索结果汇总为结构化的市场研究报告，"
                "并生成供下游品牌战略 Agent（Trout）使用的精炼 handoff 交接摘要。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "research_summary": {
                        "type": "string",
                        "description": "基于检索结果的市场研究综合总结，将用作最终报告生成的数据底稿。"
                    }
                },
                "required": ["research_summary"]
            }
        }
    }
]


# ==========================================
# 2. Tavily Search Executor
# ==========================================

async def execute_tavily_search(query: str, max_results: int = 5) -> Dict[str, Any]:
    """
    调用 Tavily Search API 执行真实联网检索。
    返回结构化的检索结果，包括每条来源的 URL、标题、摘要。
    
    NOTE: Tavily 专为 AI Agent 设计，直接返回结构化摘要，无需解析 HTML。
    """
    tavily_api_key = os.environ.get("TAVILY_API_KEY", "")
    
    if not tavily_api_key or tavily_api_key.startswith("tvly-请填入"):
        logger.warning("TAVILY_API_KEY 未配置，降级为 LLM 内置知识模式")
        return {
            "query": query,
            "results": [],
            "fallback_mode": True,
            "message": "联网检索不可用，基于训练数据进行分析"
        }

    try:
        from tavily import AsyncTavilyClient
        client = AsyncTavilyClient(api_key=tavily_api_key)
        
        response = await client.search(
            query=query,
            search_depth="advanced",   # NOTE: advanced 模式获取更完整摘要
            max_results=max_results,
            include_answer=True,       # 让 Tavily 自动合成一段答案摘要
            include_raw_content=False, # 不需要原始 HTML
        )
        
        results = []
        for r in response.get("results", []):
            results.append({
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "content": r.get("content", ""),
                "score": r.get("score", 0.0),
            })
        
        return {
            "query": query,
            "answer": response.get("answer", ""),   # Tavily 的合成摘要
            "results": results,
            "fallback_mode": False,
        }

    except ImportError:
        logger.error("tavily-python 未安装，请执行 pip install tavily-python")
        return {"query": query, "results": [], "fallback_mode": True, "message": "tavily 库未安装"}
    except Exception as e:
        logger.error("Tavily 检索失败: %s", e)
        return {"query": query, "results": [], "fallback_mode": True, "message": str(e)}


# ==========================================
# 3. Tool Call Result Formatter
# ==========================================

def format_search_result_for_llm(search_result: Dict[str, Any]) -> str:
    """
    将 Tavily 的搜索结果格式化为 LLM 可读的文本，注入后续 Prompt。
    """
    if search_result.get("fallback_mode"):
        msg = search_result.get("message", "联网检索不可用")
        return f"[检索状态：{msg}，以下分析基于 AI 训练数据]\n"
    
    lines = [f"**检索词**: {search_result['query']}\n"]
    
    if search_result.get("answer"):
        lines.append(f"**Tavily 综合摘要**:\n{search_result['answer']}\n")
    
    for i, r in enumerate(search_result.get("results", [])[:5], 1):
        lines.append(f"**来源 {i}**: [{r['title']}]({r['url']})")
        if r.get("content"):
            lines.append(f"  摘要: {r['content'][:300]}...")
        lines.append("")
    
    return "\n".join(lines)


# ==========================================
# 4. Tool Parser Helper
# ==========================================

def parse_wacksman_tool_calls(tool_calls: List[dict]) -> Optional[Dict[str, Any]]:
    """
    辅助函数：解析模型返回的单次 Tool Call，返回 action + args 字典。
    """
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
        "args": args,
    }
