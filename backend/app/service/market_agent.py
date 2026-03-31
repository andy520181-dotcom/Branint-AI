from __future__ import annotations

from collections.abc import AsyncGenerator

from app.service.llm_provider import call_llm, call_llm_stream

# 市场研究 Agent 系统提示词
MARKET_AGENT_SYSTEM_PROMPT = """你是一位顶级的市场研究专家，拥有丰富的品牌咨询经验。
你的任务是对用户提供的品牌需求进行深度市场研究分析。

请严格按照以下结构输出（使用 Markdown 格式）：

## 🔍 市场概况与规模
- 目标市场的整体规模（估算）
- 近3年增长趋势
- 关键市场驱动因素

## 👥 目标消费者画像（TA Profile）
- 核心人群：年龄、性别、职业、收入
- 生活方式与消费习惯
- 痛点与核心需求
- 消费决策路径

## 🏆 竞品分析（3-5个主要竞品）
| 竞品名称 | 定位 | 优势 | 劣势 | 价格区间 |
|---------|------|------|------|---------|
（填写竞品信息）

## 💡 市场机会点
- 现有市场空白
- 差异化切入机会
- 用户未被满足的需求

## ⚠️ 市场挑战与风险
- 主要竞争壁垒
- 潜在市场风险

请保持专业、数据驱动的分析风格，内容详尽具体。"""


async def run_market_agent(user_prompt: str) -> str:
    """
    市场研究 Agent（非流式，用于上下文传递）
    输入：用户原始品牌需求描述
    输出：结构化市场研究报告
    """
    messages = [
        {"role": "system", "content": MARKET_AGENT_SYSTEM_PROMPT},
        {"role": "user", "content": f"请对以下品牌需求进行深度市场研究分析：\n\n{user_prompt}"},
    ]
    return await call_llm(messages)


async def run_market_agent_stream(user_prompt: str) -> AsyncGenerator[str, None]:
    """
    市场研究 Agent（流式）
    yield 每个 token，供 orchestrator 实时推送给前端
    """
    messages = [
        {"role": "system", "content": MARKET_AGENT_SYSTEM_PROMPT},
        {"role": "user", "content": f"请对以下品牌需求进行深度市场研究分析：\n\n{user_prompt}"},
    ]
    async for chunk in call_llm_stream(messages):
        yield chunk
