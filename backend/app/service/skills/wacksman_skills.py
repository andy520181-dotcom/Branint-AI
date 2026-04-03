"""
Wacksman Agent（市场研究专家）的核心功能库
定义供大模型调用的工具 JSON Schema，以及 Tavily 联网检索和 Jina 爬虫的执行逻辑。

工作流：
  1. clarify_research_scope  — 确认研究范围（行业/地域/竞品）
  2. web_search_market_data  — 检索市场宏观数据（规模/趋势/政策）
  3. search_competitor_intel — 检索竞品具体情报（定位/价格/融资/声量）
  4. scrape_review_url       — 统娱分析第三方平台特定页面的用户评论内容
  5. search_social_reviews   — 针对电商/短视频/社区平台的已公开用户声音检索
  6. synthesize_research_report — 汇总所有数据，生成最终研究报告 + handoff
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional

from app.service.integrations.nlp_service import nlp_client

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
    },
    {
        "type": "function",
        "function": {
            "name": "scrape_review_url",
            "description": (
                "爬取电商平台（Amazon、京东、Lazada）或内容平台（Reddit、知乎、小红书公开箔记）某一具体 URL "
                "的页面内容，提取用户评论、主观感受和打分数据。仅支持公开可访问的页面，不支持需登录的内容。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "要爬取的具体页面 URL，例如 Amazon 商品评价页、Reddit 帖子、知乎问题等。"
                    },
                    "platform": {
                        "type": "string",
                        "enum": ["amazon", "jd", "reddit", "zhihu", "xiaohongshu", "other"],
                        "description": "来源平台类型，主要用于标注数据类型和展示。"
                    },
                    "focus": {
                        "type": "string",
                        "description": "爬取重点，例如：'用户评价和打分分布'、'主要吘怨点'、'多次购买用户的口碑'。"
                    }
                },
                "required": ["url", "platform", "focus"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_social_reviews",
            "description": (
                "在电商平台、短视频平台、社区论坛等平台上搜索用户评论和真实用户声音。"
                "能检索大众点评、倣测返回、小红书笔记、Reddit 论坛帖子、知乎回答等已公开被索引的内容。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "检索词，建议包含平台限定词，例如：'site:xiaohongshu.com 护肤品各大评测'、'Amazon reviews lululemon leggings complaints'。"
                    },
                    "platform_focus": {
                        "type": "string",
                        "enum": ["xiaohongshu", "douyin", "weibo", "amazon", "reddit", "zhihu", "taobao_review", "cross_platform"],
                        "description": "目标平台类型，用于自动优化检索词并标注数据来源。"
                    },
                    "sentiment_focus": {
                        "type": "string",
                        "enum": ["positive", "negative", "neutral", "all"],
                        "description": "情感倾向过滤，例如 negative 专门搜集吙怨和痛点。"
                    }
                },
                "required": ["query", "platform_focus", "sentiment_focus"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "mine_consumer_persona",
            "description": (
                "将搜索到的消费者言论、反馈数据深度汇总，构建清晰的目标消费者画像。\n"
                "本能力将代替低维的 NLP，通过大模型进行高维交叉验证，输出 Demographic 与决策心理路径的结构化分析总结。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "target_audience": {
                        "type": "string",
                        "description": "目标人群画像概括描述，例如：'一二线城市 25-35 岁高知女性'。"
                    },
                    "core_pain_points": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "痛点与核心动机提取。"
                    }
                },
                "required": ["target_audience", "core_pain_points"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_semantic_sentiment",
            "description": (
                "利用大模型强大的理解力替代传统百度/阿里云 NLP 情感分析。\n"
                "对搜索收集到的全部商品好评/差评、社媒讨论及反馈进行语义聚类，提取正面口碑关键词和负面抱怨词云分布。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sentiment_summary": {
                        "type": "string",
                        "description": "一段总结性的文字，描述该类目或该竞品整体的情感倾向分布。"
                    },
                    "positive_topics": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "排序前三的正向话题（如：'包装高档'，'吸收快'）。"
                    },
                    "negative_topics": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "排序前三的负向抱怨点（如：'容易拔干'，'气味刺鼻'）。"
                    }
                },
                "required": ["sentiment_summary", "positive_topics", "negative_topics"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "identify_opportunities",
            "description": (
                "基于对行业、竞品、用户舆情的交叉对比，识别品牌入局的市场机会缺口。\n"
                "指出哪些需求未被满足、哪些场景能够切入、哪些人群具有未触达价值。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "opportunities_list": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "提炼的具体市场机会点列表。"
                    }
                },
                "required": ["opportunities_list"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_data_visualization",
            "description": (
                "通知系统将当前某一组结构化数据转换为图表展现（支持 ECharts)。\n"
                "注意：调用此工具相当于做标记，你应该在最终撰写 Markdown 报告时，直接使用 ```echarts ... ``` 语法生成图表。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "chart_type": {
                        "type": "string",
                        "enum": ["radar", "bar", "pie", "line", "scatter"],
                        "description": "准备生成的图表类型"
                    },
                    "intent_description": {
                        "type": "string",
                        "description": "图表所要表达的核心分析观点"
                    }
                },
                "required": ["chart_type", "intent_description"]
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
# 3b. Jina AI Reader Scraper
# ==========================================

async def execute_jina_scrape(url: str, platform: str, focus: str) -> Dict[str, Any]:
    """
    通过 Jina AI Reader（r.jina.ai）抓取目标页面并转换为干净 Markdown 文本。
    
    NOTE: Jina Reader 是免费的开放服务，将任意公网页面转为 LLM 友好的 Markdown，
    特别适合抓取 Amazon 商品评价页、Reddit 帖子、知乎问答、公开小红书笔记。
    不支持需要登录或强反爬（Taobao/Douyin 实时评论接口）的内容。
    """
    import httpx
    
    jina_url = f"https://r.jina.ai/{url}"
    
    headers = {
        "Accept": "text/plain",
        # NOTE: 设置 X-Return-Format 让 Jina 返回纯文本而非 HTML
        "X-Return-Format": "markdown",
        # NOTE: 可选：设置 X-With-Links-Summary 获取页内链接汇总
    }
    
    logger.info("Jina Reader 开始抓取: %s [平台: %s]", url, platform)
    
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(jina_url, headers=headers, follow_redirects=True)
            
            if resp.status_code != 200:
                logger.warning("Jina Reader 返回非 200: %d, URL: %s", resp.status_code, url)
                return {
                    "url": url,
                    "platform": platform,
                    "content": "",
                    "success": False,
                    "message": f"HTTP {resp.status_code}，页面可能需要登录或已被保护",
                }
            
            raw_text = resp.text
            
            # NOTE: Jina 返回的文本可能很长，截取重点内容供 LLM 分析
            # 超过 4000 字则只取前 2000 + 后 2000（通常评论在末尾）
            if len(raw_text) > 4000:
                content = raw_text[:2000] + "\n...[中间内容省略]...\n" + raw_text[-2000:]
            else:
                content = raw_text
            
            logger.info("Jina 抓取成功: %s，内容长度 %d 字", url, len(raw_text))
            
            return {
                "url": url,
                "platform": platform,
                "focus": focus,
                "content": content,
                "raw_length": len(raw_text),
                "success": True,
            }
    
    except httpx.TimeoutException:
        logger.error("Jina Reader 超时: %s", url)
        return {"url": url, "platform": platform, "content": "", "success": False, "message": "请求超时（20s）"}
    except Exception as e:
        logger.error("Jina Reader 失败: %s — %s", url, e)
        return {"url": url, "platform": platform, "content": "", "success": False, "message": str(e)}


def format_jina_result_for_llm(jina_result: Dict[str, Any]) -> str:
    """
    将 Jina 抓取结果格式化为 LLM 可读文本，标注平台来源。
    """
    if not jina_result.get("success"):
        msg = jina_result.get("message", "页面抓取失败")
        return f"[爬取状态：{msg}，URL: {jina_result.get('url', '')}]\n"
    
    platform_label = {
        "amazon": "Amazon 商品评价",
        "jd": "京东商品评价",
        "reddit": "Reddit 论坛",
        "zhihu": "知乎问答",
        "xiaohongshu": "小红书笔记",
        "other": "第三方页面",
    }.get(jina_result.get("platform", "other"), "第三方页面")
    
    return (
        f"## 【{platform_label}】页面内容（来源: {jina_result['url']}）\n"
        f"**抓取重点**: {jina_result.get('focus', '')}\n\n"
        f"{jina_result.get('content', '')}\n"
    )


# ==========================================
# 3c. Social Review Targeted Search
# ==========================================

# NOTE: 各平台的 Tavily 优化检索词模板
# 通过在查询词中加入 site: 限定词，提升目标平台结果的精准度
PLATFORM_QUERY_TEMPLATES: Dict[str, str] = {
    "xiaohongshu": "{query} site:xiaohongshu.com OR 小红书 {query} 评测 真实",
    "douyin": "{query} 抖音 评论 用户反馈 site:douyin.com OR 抖音 {query}",
    "weibo": "{query} 微博 用户讨论 site:weibo.com",  
    "amazon": "{query} amazon reviews site:amazon.com OR site:amazon.co.uk",
    "reddit": "{query} reddit reviews users experience site:reddit.com",
    "zhihu": "{query} 知乎 用户评价 真实使用感受 site:zhihu.com",
    "taobao_review": "{query} 淘宝评论 购买心得 用户真实反馈",
    "cross_platform": "{query} 用户评价 使用心得 真实口碑 评测",
}

SENTIMENT_KEYWORDS: Dict[str, str] = {
    "positive": " 好用 推荐 满意 五星 回购",
    "negative": " 踩雷 不好用 失望 差评 退货",
    "neutral": "",
    "all": "",
}


async def execute_social_review_search(
    query: str,
    platform_focus: str,
    sentiment_focus: str,
    max_results: int = 5,
) -> Dict[str, Any]:
    """
    使用 Tavily Search 定向检索社交媒体和电商平台的用户评论与真实声音。
    
    通过平台限定词模板 + 情感关键词自动优化原始 query，提升相关性。
    """
    # NOTE: 根据平台和情感倾向自动优化检索词
    template = PLATFORM_QUERY_TEMPLATES.get(platform_focus, "{query}")
    optimized_query = template.format(query=query)
    sentiment_kw = SENTIMENT_KEYWORDS.get(sentiment_focus, "")
    final_query = f"{optimized_query}{sentiment_kw}".strip()
    
    logger.info(
        "社交评论检索: 原始=%s → 优化后=%s [平台=%s, 情感=%s]",
        query, final_query, platform_focus, sentiment_focus,
    )
    
    search_result = await execute_tavily_search(final_query, max_results=max_results)
    
    # 在返回结果中携带平台和情感元数据
    search_result["platform_focus"] = platform_focus
    search_result["sentiment_focus"] = sentiment_focus
    search_result["original_query"] = query
    search_result["optimized_query"] = final_query
    
    return search_result


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

# ==========================================
# 5. New Skill Execution Stubs
# ==========================================

async def execute_mine_consumer_persona(target_audience: str, core_pain_points: List[str]) -> Dict[str, Any]:
    """挖掘消费者画像：记录大模型的阶段性思考成果，便于在时间轴上展示进度"""
    return {
        "success": True,
        "message": "消费者画像提炼完毕，已为您梳理核心痛点，将在最终报告中呈现详细分析网络。",
        "target_audience": target_audience,
        "pain_points": core_pain_points,
    }

async def execute_analyze_semantic_sentiment(sentiment_summary: str, positive_topics: List[str], negative_topics: List[str]) -> Dict[str, Any]:
    """语义情感分析：对接 NLP 服务替代或增强分析结果"""
    # NOTE: 这里集成真实的 NLP SDK
    text_corpus = "" # 如果有采集池可以传整个语料
    nlp_res = await nlp_client.analyze_sentiment(
        text_corpus=text_corpus,
        fallback_summary=sentiment_summary,
        fallback_pos=positive_topics,
        fallback_neg=negative_topics,
    )
    
    return {
        "success": True,
        "message": f"已通过 {nlp_res['source']} 云端计算情感倾向，话题聚类结果已生成（包括正负向分布），将在最终报告可视化呈现。",
        "nlp_results": nlp_res,
    }

async def execute_identify_opportunities(opportunities_list: List[str]) -> Dict[str, Any]:
    """机会识别"""
    return {
        "success": True,
        "message": f"机会点缺口识别完成，共发现并锚定了 {len(opportunities_list)} 个切入场景或需求缺口。",
        "opportunities": opportunities_list,
    }

async def execute_generate_data_visualization(chart_type: str, intent_description: str) -> Dict[str, Any]:
    """数据可视化：指导模型准备生成 ECharts"""
    return {
        "success": True,
        "message": f"图表 [{chart_type}] 的渲染指令已就绪。请您在撰写 Markdown 报告时务必内嵌 ```echarts 代码块呈现该 {intent_description}。",
    }

