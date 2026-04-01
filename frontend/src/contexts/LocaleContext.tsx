'use client';

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';
import {
  type LocalePreference,
  type ResolvedLocale,
  applyLocalePreference,
  getStoredLocalePreference,
  resolveLocale,
} from '@/lib/locale';
import { translate } from '@/i18n/messages';

type LocaleContextValue = {
  /** 用户选择：跟随系统 / 简中 / 英 */
  preference: LocalePreference;
  /** 实际用于文案的语言 */
  resolvedLocale: ResolvedLocale;
  setPreference: (pref: LocalePreference) => void;
  t: (key: string) => string;
};

const LocaleContext = createContext<LocaleContextValue | null>(null);

export function LocaleProvider({ children }: { children: React.ReactNode }) {
  // NOTE: SSR 阶段始终使用默认值 'zh-CN'，客户端 mount 后才读取实际偏好
  // 这样服务端渲染的 HTML 与客户端首次渲染完全一致，避免 hydration mismatch
  const [mounted, setMounted] = useState(false);
  const [preference, setPref] = useState<LocalePreference>('system');
  const [resolvedLocale, setResolved] = useState<ResolvedLocale>('zh-CN');

  const sync = useCallback((pref: LocalePreference) => {
    const resolved = applyLocalePreference(pref);
    setPref(pref);
    setResolved(resolved);
  }, []);

  useEffect(() => {
    // 客户端 mount 后立即读取实际语言偏好
    sync(getStoredLocalePreference());
    setMounted(true);
  }, [sync]);

  /** 跟随系统时，浏览器语言变化 */
  useEffect(() => {
    if (preference !== 'system') return;
    const onLang = () => {
      const r = resolveLocale('system');
      setResolved(r);
      document.documentElement.lang = r === 'en' ? 'en' : 'zh-CN';
    };
    window.addEventListener('languagechange', onLang);
    return () => window.removeEventListener('languagechange', onLang);
  }, [preference]);

  const setPreference = useCallback(
    (pref: LocalePreference) => {
      sync(pref);
    },
    [sync],
  );

  // NOTE: mount 前使用 'zh-CN' 的 t 函数，与服务端渲染保持一致
  const activeLocale: ResolvedLocale = mounted ? resolvedLocale : 'zh-CN';

  const t = useCallback(
    (key: string) => translate(activeLocale, key),
    [activeLocale],
  );

  const value = useMemo(
    () => ({ preference, resolvedLocale: activeLocale, setPreference, t }),
    [preference, activeLocale, setPreference, t],
  );

  return <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>;
}

export function useLocale() {
  const ctx = useContext(LocaleContext);
  if (!ctx) {
    throw new Error('useLocale must be used within LocaleProvider');
  }
  return ctx;
}

/** 无 Provider 时（极少数场景）的安全降级 */
export function useOptionalLocale(): LocaleContextValue | null {
  return useContext(LocaleContext);
}
