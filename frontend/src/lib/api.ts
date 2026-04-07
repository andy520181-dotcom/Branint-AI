/**
 * 统一 API 客户端
 * 所有 fetch / EventSource 请求都从这里引用 BASE_URL 和封装函数
 */

export const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

/** 一轮对话的历史记录（用户输入 + 各 Agent 输出） */
export interface ConversationRound {
  user_prompt: string;
  agent_outputs: Record<string, string>;
}

/**
 * 创建品牌咨询会话，返回 session_id
 * @param conversationHistory 之前轮次的对话记录，首轮为空
 * @param strategyClarifyAnswers Trout 战略追问的用户回答（非首次追问时传入）
 * @param strategyClarifyRound 本次是第几轮追问回答，用于后端控制追问上限
 */
export async function createSession(
  userId: string,
  prompt: string,
  sessionId?: string,
  title?: string,
  conversationHistory: ConversationRound[] = [],
  attachments: string[] = [],
  strategyClarifyAnswers?: string,
  strategyClarifyRound?: number,
): Promise<string> {
  const res = await fetch(`${API_BASE}/api/sessions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      user_id: userId,
      user_prompt: prompt,
      ...(sessionId && { session_id: sessionId }),
      ...(title && { title }),
      conversation_history: conversationHistory,
      attachments,
      // NOTE: 仅在 Trout 追问后继续提交时才传入，普通对话为 undefined（后端忽略）
      ...(strategyClarifyAnswers !== undefined && {
        strategy_clarification_answers: strategyClarifyAnswers,
        strategy_clarify_round: strategyClarifyRound ?? 1,
      }),
    }),
  });
  if (!res.ok) throw new Error(`创建会话失败 (${res.status})`);
  const data = await res.json() as { session_id: string };
  return data.session_id;
}

/** 上传品牌资产文件（图片/PDF/文档），返回资源访问 URL */
export async function uploadAsset(file: File): Promise<{ url: string; original_name: string }> {
  const form = new FormData();
  form.append('file', file);
  const res = await fetch(`${API_BASE}/api/assets/upload`, {
    method: 'POST',
    body: form,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: '上传失败' })) as { detail: string };
    throw new Error(err.detail ?? `上传失败 (${res.status})`);
  }
  return res.json() as Promise<{ url: string; original_name: string }>;
}


/** 获取已完成会话的报告 */
export async function fetchReport(sessionId: string): Promise<{ session_id: string; report: string }> {
  const res = await fetch(`${API_BASE}/api/sessions/${sessionId}/report`);
  if (!res.ok) throw new Error(`获取报告失败 (${res.status})`);
  return res.json() as Promise<{ session_id: string; report: string }>;
}

/** 会话快照（任意时刻均可拉取，用于刷新后数据恢复） */
export interface SessionSnapshot {
  session_id: string;
  status: 'pending' | 'running' | 'completed' | 'error';
  user_prompt: string;
  /** key = agentId，value = 该 Agent 已完成的输出文本 */
  agent_outputs: Record<string, string>;
  agent_statuses: Record<string, string>;
  agent_media?: {
    agentImages?: any[];
    agentVideos?: any[];
  };
  report?: string | null;
  /** 路由中间段（market/strategy/...），不含 consultant_plan / consultant_review */
  selected_agents?: string[];
  conversation_history?: Array<{
    user_prompt: string;
    agent_outputs: Record<string, string>;
  }>;
}

/**
 * 拉取会话快照，无论会话是否完成都能返回已落盘的数据。
 * 前端刷新后优先调用此接口，而不依赖 localStorage。
 */
export async function fetchSnapshot(sessionId: string): Promise<SessionSnapshot> {
  const res = await fetch(`${API_BASE}/api/sessions/${sessionId}/snapshot`);
  if (!res.ok) throw new Error(`获取快照失败 (${res.status})`);
  return res.json() as Promise<SessionSnapshot>;
}

export interface SessionListItem {
  session_id: string;
  title: string;
  is_pinned: boolean;
  created_at: string;
  updated_at: string;
}

/** 获取当前用户的会话列表 */
export async function fetchSessions(userId: string): Promise<SessionListItem[]> {
  const params = new URLSearchParams({ user_id: userId });
  const res = await fetch(`${API_BASE}/api/sessions?${params.toString()}`);
  if (!res.ok) throw new Error(`获取会话列表失败 (${res.status})`);
  return res.json() as Promise<SessionListItem[]>;
}

/** 修改会话元数据（标题、置顶） */
export async function updateSessionMeta(
  sessionId: string,
  meta: { title?: string; is_pinned?: boolean }
): Promise<void> {
  const res = await fetch(`${API_BASE}/api/sessions/${sessionId}/meta`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(meta),
  });
  if (!res.ok) throw new Error(`更新会话失败 (${res.status})`);
}

/** 删除会话 */
export async function deleteSession(sessionId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/sessions/${sessionId}`, {
    method: 'DELETE',
  });
  if (!res.ok) throw new Error(`删除会话失败 (${res.status})`);
}
