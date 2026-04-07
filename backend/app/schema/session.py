from pydantic import BaseModel, Field

from app.config import settings


class HistoryRound(BaseModel):
    """
    一轮对话的完整记录（用户输入 + 各 Agent 输出）
    用于后续轮次向品牌顾问传递上下文，使其理解之前的分析内容
    """
    user_prompt: str = ""
    agent_outputs: dict[str, str] = {}  # {"market": "完整输出...", "strategy": "..."}

from typing import Optional
from datetime import datetime

class SessionListItem(BaseModel):
    session_id: str
    title: str
    is_pinned: bool
    created_at: datetime
    updated_at: datetime

class SessionMetaUpdate(BaseModel):
    title: Optional[str] = None
    is_pinned: Optional[bool] = None


class CreateSessionRequest(BaseModel):
    session_id: Optional[str] = Field(default=None, description="前端生成的 UUID，若不传则后端生成")
    title: Optional[str] = Field(default=None, description="会话标题，若不传则自动截取第一句")
    user_prompt: str = Field(
        ...,
        min_length=1,
        max_length=settings.user_prompt_max_chars,
        description="用户的品牌需求描述（长度上限由配置 user_prompt_max_chars 控制）",
    )
    user_id: str = Field(..., description="Supabase Auth 用户 ID")
    # NOTE: 后续轮次对话时传入，首轮为空；包含之前所有 Agent 的完整输出
    conversation_history: list[HistoryRound] = []
    # NOTE: 本次对话附带的资产文件 URL列表（图片/PDF/文档），由前端上传并存儲后返回
    attachments: list[str] = []
    # NOTE: 战略追问的回答和轮数（若有）
    strategy_clarification_answers: Optional[str] = Field(default=None, description="战略重放澄清回答")
    strategy_clarify_round: Optional[int] = Field(default=0, description="目前所属的澄清轮数")


class CreateSessionResponse(BaseModel):
    session_id: str
    message: str = "会话创建成功，请连接 SSE 流开始分析"


class AgentOutputEvent(BaseModel):
    id: str
    content: str


class SessionCompleteEvent(BaseModel):
    report: str
