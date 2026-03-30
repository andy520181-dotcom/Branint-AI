from app.service.llm_provider import call_llm

CONTENT_AGENT_SYSTEM_PROMPT = """你是一位顶级的品牌内容策划专家，擅长将品牌战略转化为具体可执行的内容方向。
你将基于市场研究和品牌战略，制定全面的内容营销计划。

请严格按照以下结构输出（使用 Markdown 格式）：

## ✍️ 品牌故事（Brand Story）
用300字左右讲述一个真实、有温度的品牌故事，包含：
- 品牌诞生的背景与初心
- 解决了什么问题
- 对消费者的承诺

## 💬 核心 Slogan（5个备选）
每个 Slogan 附上创作思路说明

## 📱 社交媒体内容矩阵
| 渠道 | 内容方向 | 发布频率 | 内容形式 | 核心目的 |
|------|---------|---------|---------|---------|
| 小红书 | | | | |
| 微信公众号 | | | | |
| 抖音/视频号 | | | | |
| 微博 | | | | |

## 📅 30天内容日历（框架）
- 第1周主题：
- 第2周主题：
- 第3周主题：
- 第4周主题：

## 🔑 关键词策略
- 核心品牌词（5个）
- 长尾关键词（10个）
- 营销话题标签 Hashtag（10个）

## 🤝 KOL/KOC 合作策略
- 推荐合作的博主类型
- 合作内容形式建议
- 预算分配建议

请确保内容策略具体可落地，避免泛泛而谈。"""


async def run_content_agent(
    user_prompt: str,
    market_research: str,
    brand_strategy: str,
) -> str:
    """
    内容策划 Agent
    输入：用户原始需求 + 市场研究 + 品牌战略（完整上下文）
    输出：内容营销策划手册
    """
    messages = [
        {"role": "system", "content": CONTENT_AGENT_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"品牌需求：\n{user_prompt}\n\n"
                f"【市场研究结果】：\n{market_research}\n\n"
                f"【品牌战略方向】：\n{brand_strategy}"
            ),
        },
    ]
    return await call_llm(messages)
