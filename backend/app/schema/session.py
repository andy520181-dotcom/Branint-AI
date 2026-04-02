from pydantic import BaseModel, Field

from app.config import settings


class HistoryRound(BaseModel):
    """
    一轮对话的完整记录（用户输入 + 各 Agent 输出）
    用于后续轮次向品牌顾问传递上下文，使其理解之前的分析内容
    """
    user_prompt: str = ""
    agent_outputs: dict[str, str] = {}  # {"market": "完整输出...", "strategy": "..."}


class CreateSessionRequest(BaseModel):
    user_prompt: str = Field(
        ...,
        min_length=1,
        max_length=settings.user_prompt_max_chars,
        description="用户的品牌需求描述（长度上限由配置 user_prompt_max_chars 控制）",
    )
    user_id: str = Field(..., description="Supabase Auth 用户 ID")
    # NOTE: 后续轮次对话时传入，首轮为空；包含之前所有 Agent 的完整输出
    conversation_history: list[HistoryRound] = []


class CreateSessionResponse(BaseModel):
    session_id: str
    message: str = "会话创建成功，请连接 SSE 流开始分析"


class AgentOutputEvent(BaseModel):
    id: str
    content: str


class SessionCompleteEvent(BaseModel):
    report: str
