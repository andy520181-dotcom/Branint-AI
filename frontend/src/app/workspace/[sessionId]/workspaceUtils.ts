import type { AgentId, HistoryItem } from '@/types';

const ROUTE_MIDDLE_KEYS = new Set(['market', 'strategy', 'content', 'visual']);

/**
 * 将 snapshot 中的 selected_agents（中间段）拼成 Feed 用的完整路由，
 * 与 SSE routing_decided 后前端构造的列表一致。
 */
export function buildFeedRouteFromMiddleKeys(middle: string[] | null | undefined): AgentId[] | null {
  if (!middle?.length) return null;
  const valid = middle.filter((k): k is AgentId => ROUTE_MIDDLE_KEYS.has(k));
  if (!valid.length) return null;
  return ['consultant_plan', ...valid, 'consultant_review'];
}

/** 将历史列表按日期分组 */
export function groupByDate(
  items: HistoryItem[],
  t: (key: string) => string,
): { label: string; items: HistoryItem[] }[] {
  const now = new Date();
  const todayStr = now.toDateString();
  const weekAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
  const monthAgo = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);

  const today: HistoryItem[] = [];
  const week: HistoryItem[] = [];
  const month: HistoryItem[] = [];
  const older: HistoryItem[] = [];

  for (const item of items) {
    const d = new Date(item.createdAt);
    if (d.toDateString() === todayStr) today.push(item);
    else if (d >= weekAgo) week.push(item);
    else if (d >= monthAgo) month.push(item);
    else older.push(item);
  }

  return [
    { label: t('history.group.today'), items: today },
    { label: t('history.group.week'), items: week },
    { label: t('history.group.month'), items: month },
    { label: t('history.group.older'), items: older },
  ].filter((g) => g.items.length > 0);
}

/** 单行截断，用于导航列表与缩略划条 */
export function truncatePromptOneLine(s: string, max = 44): string {
  const t = s.replace(/\s+/g, ' ').trim();
  if (t.length <= max) return t;
  return `${t.slice(0, max)}…`;
}
