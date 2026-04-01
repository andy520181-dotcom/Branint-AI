/** 用户选择的语言偏好（界面文案以 resolvedLocale 为准） */
export type LocalePreference = 'system' | 'zh-CN' | 'en';

export type ResolvedLocale = 'zh-CN' | 'en';

const STORAGE_KEY = 'woloong_lang';

export function resolveLocale(pref: LocalePreference): ResolvedLocale {
  if (typeof window === 'undefined') return 'zh-CN';
  if (pref === 'system') {
    const lang = navigator.language || navigator.languages?.[0] || 'zh-CN';
    return lang.toLowerCase().startsWith('zh') ? 'zh-CN' : 'en';
  }
  return pref === 'en' ? 'en' : 'zh-CN';
}

export function getStoredLocalePreference(): LocalePreference {
  if (typeof window === 'undefined') return 'system';
  const v = localStorage.getItem(STORAGE_KEY);
  if (v === 'system' || v === 'zh-CN' || v === 'en') return v;
  return 'system';
}

export function applyLocalePreference(pref: LocalePreference): ResolvedLocale {
  if (typeof window === 'undefined') return 'zh-CN';
  localStorage.setItem(STORAGE_KEY, pref);
  const resolved = resolveLocale(pref);
  document.documentElement.lang = resolved === 'en' ? 'en' : 'zh-CN';
  document.documentElement.setAttribute('data-locale-pref', pref);
  return resolved;
}
