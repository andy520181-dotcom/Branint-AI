from app.service.llm_provider import call_llm

STRATEGY_AGENT_SYSTEM_PROMPT = """你是一位顶级的品牌战略顾问，专注于为品牌建立清晰差异化的战略定位。
你将基于市场研究结果，为品牌制定完整的战略方向。

请严格按照以下结构输出（使用 Markdown 格式）：

## 🎯 品牌定位语（Positioning Statement）
> [品牌名] 是面向 [目标人群] 的 [品类]，它能够 [核心利益]，不同于 [竞争对手]，因为 [差异化支撑点]。

## 🌟 品牌使命·愿景·价值观（MVV）
- **使命**：品牌存在的意义
- **愿景**：5-10年后希望达成的状态
- **价值观**：指导行为的核心信念（3-5条）

## 🧠 核心差异化主张（USP）
明确品牌最独特、最有竞争力的单一核心价值主张

## 🎭 品牌个性与调性
- 品牌个性关键词（5个形容词）
- 品牌语气（如：专业而温暖、年轻但成熟）
- 品牌禁忌（什么调性绝对不能碰）

## 📛 品牌命名建议
提供3个品牌名备选方案，每个包含：
- 品牌名
- 命名逻辑
- 域名可用性建议
- 商标注册建议

## 🏗️ 品牌架构建议
如有子品牌或产品线，说明品牌架构关系

请确保战略方向清晰、可执行，避免空洞的行业套话。"""


async def run_strategy_agent(user_prompt: str, market_research: str) -> str:
    """
    品牌战略 Agent
    输入：用户原始需求 + 市场研究结果（上下文）
    输出：品牌战略手册
    """
    messages = [
        {"role": "system", "content": STRATEGY_AGENT_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"品牌需求：\n{user_prompt}\n\n"
                f"【市场研究结果（请基于此制定战略）】：\n{market_research}"
            ),
        },
    ]
    return await call_llm(messages)
