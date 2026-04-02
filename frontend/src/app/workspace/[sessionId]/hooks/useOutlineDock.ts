'use client';

import { useState, useEffect, useCallback, useMemo, useRef } from 'react';

export interface OutlineItem {
  id: string;
  prompt: string;
}

export interface UseOutlineDockReturn {
  outlineItems: OutlineItem[];
  activeOutlineIndex: number;
  outlinePanelOpen: boolean;
  setOutlinePanelOpen: (v: boolean) => void;
  outlineDockRef: React.RefObject<HTMLElement | null>;
  jumpToRound: (id: string) => void;
}

export interface UseOutlineDockOptions {
  previousRoundPrompts: string[];
  userPrompt: string;
}

/**
 * 封装右侧 Outline Dock 的滚动跟踪、锚点跳转与面板开关逻辑
 */
export function useOutlineDock({ previousRoundPrompts, userPrompt }: UseOutlineDockOptions): UseOutlineDockReturn {
  const outlineDockRef = useRef<HTMLElement | null>(null);
  const [outlinePanelOpen, setOutlinePanelOpen] = useState(false);
  const [activeOutlineIndex, setActiveOutlineIndex] = useState(0);

  const outlineItems = useMemo<OutlineItem[]>(() => {
    const items: OutlineItem[] = [];
    previousRoundPrompts.forEach((prompt, i) => {
      items.push({ id: `workspace-round-${i}`, prompt });
    });
    if (userPrompt?.trim()) {
      items.push({ id: 'workspace-round-active', prompt: userPrompt });
    }
    return items;
  }, [previousRoundPrompts, userPrompt]);

  const updateOutlineActive = useCallback(() => {
    if (outlineItems.length === 0) return;
    const line = Math.min(140, (typeof window !== 'undefined' ? window.innerHeight : 800) * 0.2);
    let active = 0;
    for (let i = outlineItems.length - 1; i >= 0; i--) {
      const el = document.getElementById(outlineItems[i].id);
      if (!el) continue;
      if (el.getBoundingClientRect().top <= line) {
        active = i;
        break;
      }
    }
    setActiveOutlineIndex((prev) => (prev === active ? prev : active));
  }, [outlineItems]);

  useEffect(() => {
    if (outlineItems.length === 0) return;
    updateOutlineActive();
    window.addEventListener('scroll', updateOutlineActive, { passive: true });
    window.addEventListener('resize', updateOutlineActive);
    return () => {
      window.removeEventListener('scroll', updateOutlineActive);
      window.removeEventListener('resize', updateOutlineActive);
    };
  }, [outlineItems, updateOutlineActive]);

  // 点击 Dock 面板外部时自动收起
  useEffect(() => {
    if (!outlinePanelOpen) return;
    const onDown = (e: MouseEvent) => {
      const dock = outlineDockRef.current;
      if (dock && !dock.contains(e.target as Node)) {
        setOutlinePanelOpen(false);
      }
    };
    document.addEventListener('mousedown', onDown);
    return () => document.removeEventListener('mousedown', onDown);
  }, [outlinePanelOpen]);

  const jumpToRound = useCallback((id: string) => {
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }, []);

  return {
    outlineItems,
    activeOutlineIndex,
    outlinePanelOpen,
    setOutlinePanelOpen,
    outlineDockRef,
    jumpToRound,
  };
}
