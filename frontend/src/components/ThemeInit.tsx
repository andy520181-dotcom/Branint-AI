'use client';

import { useLayoutEffect } from 'react';
import { getStoredThemePreference, applyThemePreference } from '@/lib/theme';

/** 首屏从 localStorage 恢复主题；跟随系统时监听系统配色变化 */
export default function ThemeInit() {
  useLayoutEffect(() => {
    applyThemePreference(getStoredThemePreference());
    const mq = window.matchMedia('(prefers-color-scheme: dark)');
    const onChange = () => {
      if (getStoredThemePreference() === 'system') {
        applyThemePreference('system');
      }
    };
    mq.addEventListener('change', onChange);
    return () => mq.removeEventListener('change', onChange);
  }, []);
  return null;
}
