import type { ResolvedLocale } from '@/lib/locale';
import { en } from './locales/en';
import { zhCN } from './locales/zh-CN';

/**
 * 聚合文案表：按域拆分为 `locales/{locale}/*.ts`，此处只做合并与 t() 入口。
 */
export const messages: Record<ResolvedLocale, Record<string, string>> = {
  'zh-CN': zhCN,
  en,
};

export function translate(locale: ResolvedLocale, key: string): string {
  const table = messages[locale];
  const fallback = messages['zh-CN'];
  return table[key] ?? fallback[key] ?? key;
}

/** 工作台 / SSE 存的是 i18n key 或后端原文；UI 层用此解析 */
export function translateWorkspaceError(
  error: string | null,
  t: (key: string) => string,
): string | null {
  if (!error) return null;
  if (error.startsWith('workspace.error.')) return t(error);
  return error;
}
