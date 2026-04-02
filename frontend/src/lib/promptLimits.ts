/**
 * 单条用户输入与后端 CreateSessionRequest.user_prompt 对齐。
 * 默认与后端 Settings.user_prompt_max_chars 一致；可通过 NEXT_PUBLIC_USER_PROMPT_MAX_CHARS 覆盖。
 */
const raw = process.env.NEXT_PUBLIC_USER_PROMPT_MAX_CHARS;
export const USER_PROMPT_MAX_CHARS = (() => {
  if (raw === undefined || raw === '') return 500_000;
  const n = Number.parseInt(raw, 10);
  return Number.isFinite(n) && n > 0 ? n : 500_000;
})();
