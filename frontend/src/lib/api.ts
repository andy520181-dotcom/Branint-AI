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
 */
export async function createSession(
  userId: string,
  prompt: string,
  conversationHistory: ConversationRound[] = [],
  attachments: string[] = [],
): Promise<string> {
  const res = await fetch(`${API_BASE}/api/sessions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      user_id: userId,
      user_prompt: prompt,
      conversation_history: conversationHistory,
      attachments,
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
  report?: string | null;
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
