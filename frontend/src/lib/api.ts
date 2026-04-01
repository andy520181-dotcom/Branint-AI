/**
 * 统一 API 客户端
 * 所有 fetch / EventSource 请求都从这里引用 BASE_URL 和封装函数
 */

export const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

/** 创建品牌咨询会话，返回 session_id */
export async function createSession(userId: string, prompt: string): Promise<string> {
  const res = await fetch(`${API_BASE}/api/sessions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_id: userId, user_prompt: prompt }),
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
