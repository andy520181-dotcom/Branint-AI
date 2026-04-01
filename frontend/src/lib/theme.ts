/** 主题偏好：浅色 / 深色 / 跟随系统 */
export type ThemePreference = 'light' | 'dark' | 'system';

const STORAGE_KEY = 'woloong_theme';

export function getResolvedTheme(pref: ThemePreference): 'light' | 'dark' {
  if (typeof window === 'undefined') return 'light';
  if (pref === 'system') {
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }
  return pref;
}

/** 写入 localStorage，并在 html 上设置 data-theme（解析后的 light/dark） */
export function applyThemePreference(pref: ThemePreference) {
  if (typeof window === 'undefined') return;
  localStorage.setItem(STORAGE_KEY, pref);
  const resolved = getResolvedTheme(pref);
  document.documentElement.setAttribute('data-theme', resolved);
  document.documentElement.setAttribute('data-theme-pref', pref);
}

export function getStoredThemePreference(): ThemePreference {
  if (typeof window === 'undefined') return 'light';
  const v = localStorage.getItem(STORAGE_KEY);
  if (v === 'dark' || v === 'light' || v === 'system') return v;
  return 'light';
}

export function initThemeFromStorage() {
  applyThemePreference(getStoredThemePreference());
}
