from pydantic import BaseModel, Field


class CreateSessionRequest(BaseModel):
    user_prompt: str = Field(..., min_length=10, max_length=1000, description="用户的品牌需求描述")
    user_id: str = Field(..., description="Supabase Auth 用户 ID")


class CreateSessionResponse(BaseModel):
    session_id: str
    message: str = "会话创建成功，请连接 SSE 流开始分析"


class AgentOutputEvent(BaseModel):
    id: str
    content: str


class SessionCompleteEvent(BaseModel):
    report: str
