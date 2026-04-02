'use client';

// 统一从全局 AuthContext 取值，避免各页面重复读 localStorage
export { useAuthContext as useAuth } from '@/contexts/AuthContext';

import { useCallback } from 'react';
import { HistoryItem } from '@/types';

export function getAuthToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem('woloong_token');
}

export function useHistory() {
  const STORAGE_KEY = 'woloong_history';

  const getHistory = useCallback((): HistoryItem[] => {
    if (typeof window === 'undefined') return [];
    try { return JSON.parse(localStorage.getItem(STORAGE_KEY) ?? '[]'); }
    catch { return []; }
  }, []);

  const addHistory = useCallback((item: HistoryItem) => {
    const history = getHistory();
    const withoutDup = history.filter((h) => h.sessionId !== item.sessionId);
    const updated = [item, ...withoutDup].slice(0, 50);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
  }, [getHistory]);

  const updateHistoryTitle = useCallback(
    (sessionId: string, title: string) => {
      const history = getHistory();
      const updated = history.map((h) =>
        h.sessionId === sessionId ? { ...h, title } : h,
      );
      localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
    },
    [getHistory],
  );

  const removeHistoryItem = useCallback(
    (sessionId: string) => {
      const updated = getHistory().filter((h) => h.sessionId !== sessionId);
      localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
    },
    [getHistory],
  );

  /** 将一条记录移到列表最前（置顶） */
  const pinHistoryToTop = useCallback(
    (sessionId: string) => {
      const history = getHistory();
      const idx = history.findIndex((h) => h.sessionId === sessionId);
      if (idx <= 0) return;
      const item = history[idx];
      const rest = history.filter((_, i) => i !== idx);
      localStorage.setItem(STORAGE_KEY, JSON.stringify([item, ...rest]));
    },
    [getHistory],
  );

  return {
    getHistory,
    addHistory,
    updateHistoryTitle,
    removeHistoryItem,
    pinHistoryToTop,
  };
}
