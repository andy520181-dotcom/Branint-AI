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
): Promise<string> {
  const res = await fetch(`${API_BASE}/api/sessions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      user_id: userId,
      user_prompt: prompt,
      conversation_history: conversationHistory,
    }),
  });
  if (!res.ok) throw new Error(`创建会话失败 (${res.status})`);
  const data = await res.json() as { session_id: string };
  return data.session_id;
}

/** 获取已完成会话的报告 */
export async function fetchReport(sessionId: string): Promise<{ session_id: string; report: string }> {
  const res = await fetch(`${API_BASE}/api/sessions/${sessionId}/report`);
  if (!res.ok) throw new Error(`获取报告失败 (${res.status})`);
  return res.json() as Promise<{ session_id: string; report: string }>;
}
