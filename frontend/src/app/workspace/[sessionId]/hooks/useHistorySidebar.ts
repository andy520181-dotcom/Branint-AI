'use client';

import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import type { HistoryItem } from '@/types';
import { useHistory } from '@/hooks/useAuth';
import { groupByDate } from '../workspaceUtils';

type TFn = (key: string) => string;

export interface UseHistorySidebarOptions {
  sessionId: string;
  t: TFn;
}

export interface UseHistorySidebarReturn {
  historyOpen: boolean;
  setHistoryOpen: (v: boolean) => void;
  historyGroups: { label: string; items: HistoryItem[] }[];
  historyMenuOpenId: string | null;
  setHistoryMenuOpenId: (id: string | null) => void;
  historyToast: string;
  handleHistoryRename: (item: HistoryItem) => void;
  handleHistoryPin: (item: HistoryItem) => void;
  handleHistoryShare: (item: HistoryItem) => Promise<void>;
  handleHistoryDelete: (item: HistoryItem) => void;
}

/**
 * 封装历史记录侧边栏的所有状态与操作
 * 包括：open/close、菜单弹出、toast、rename/pin/share/delete
 */
export function useHistorySidebar({ sessionId, t }: UseHistorySidebarOptions): UseHistorySidebarReturn {
  const router = useRouter();
  const { getHistory, updateHistoryTitle, removeHistoryItem, pinHistoryToTop } = useHistory();

  const [historyOpen, setHistoryOpen] = useState(false);
  const [historyGroups, setHistoryGroups] = useState<{ label: string; items: HistoryItem[] }[]>([]);
  const [historyMenuOpenId, setHistoryMenuOpenId] = useState<string | null>(null);
  const [historyToast, setHistoryToast] = useState('');

  const refreshHistory = useCallback(() => {
    setHistoryGroups(groupByDate(getHistory(), t));
  }, [getHistory, t]);

  const showHistoryToast = useCallback((msg: string) => {
    setHistoryToast(msg);
    setTimeout(() => setHistoryToast(''), 2200);
  }, []);

  // 侧边栏开启时刷新历史列表；关闭时收起菜单
  useEffect(() => {
    if (historyOpen) refreshHistory();
    else setHistoryMenuOpenId(null);
  }, [historyOpen, refreshHistory]);

  // 点击空白区域收起右键菜单
  useEffect(() => {
    if (!historyMenuOpenId) return;
    const onDown = (e: MouseEvent) => {
      const el = e.target as HTMLElement;
      if (el.closest('[data-history-menu-root]')) return;
      setHistoryMenuOpenId(null);
    };
    document.addEventListener('mousedown', onDown);
    return () => document.removeEventListener('mousedown', onDown);
  }, [historyMenuOpenId]);

  const handleHistoryRename = useCallback(
    (item: HistoryItem) => {
      setHistoryMenuOpenId(null);
      const next = window.prompt(t('workspace.history.renamePrompt'), item.title);
      if (next === null) return;
      const trimmed = next.trim();
      if (!trimmed) return;
      updateHistoryTitle(item.sessionId, trimmed);
      refreshHistory();
    },
    [t, updateHistoryTitle, refreshHistory],
  );

  const handleHistoryPin = useCallback(
    (item: HistoryItem) => {
      setHistoryMenuOpenId(null);
      pinHistoryToTop(item.sessionId);
      refreshHistory();
    },
    [pinHistoryToTop, refreshHistory],
  );

  const handleHistoryShare = useCallback(
    async (item: HistoryItem) => {
      setHistoryMenuOpenId(null);
      const url = `${window.location.origin}/workspace/${item.sessionId}`;
      try {
        await navigator.clipboard.writeText(url);
        showHistoryToast(t('workspace.history.shareCopied'));
      } catch {
        showHistoryToast(t('workspace.history.shareFailed'));
      }
    },
    [t, showHistoryToast],
  );

  const handleHistoryDelete = useCallback(
    (item: HistoryItem) => {
      if (!window.confirm(t('workspace.history.deleteConfirm'))) return;
      setHistoryMenuOpenId(null);
      removeHistoryItem(item.sessionId);
      refreshHistory();
      if (item.sessionId === sessionId) {
        const rest = getHistory();
        if (rest[0]) router.replace(`/workspace/${rest[0].sessionId}`);
        else router.replace('/');
      }
    },
    [t, removeHistoryItem, refreshHistory, getHistory, sessionId, router],
  );

  return {
    historyOpen,
    setHistoryOpen,
    historyGroups,
    historyMenuOpenId,
    setHistoryMenuOpenId,
    historyToast,
    handleHistoryRename,
    handleHistoryPin,
    handleHistoryShare,
    handleHistoryDelete,
  };
}
