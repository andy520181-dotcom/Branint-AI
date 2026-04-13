'use client';

/**
 * useGenerateVideo — 品牌概念视频生成 Hook
 *
 * 当用户在美术指导 Agent 气泡底部点击「生成品牌视频」按钮时调用，
 * 调用后端 /generate-video 接口，生成结果写入 workspaceStore.agentVideos。
 *
 * 视频生成耗时较长（30-180秒），需提供明确的 loading 状态给用户。
 */

import { useState, useCallback } from 'react';
import { useWorkspaceStore } from '@/store/workspaceStore';

export interface GeneratedVideo {
  type: string;
  mime: string;
  data_url: string;
}

interface UseGenerateVideoReturn {
  /** 正在生成中（true 时按钮需禁用并展示进度动画） */
  generating: boolean;
  /** 触发视频生成 */
  generate: (
    sessionId: string,
    prompt?: string,
    options?: { duration?: number; aspect_ratio?: string }
  ) => Promise<void>;
}

export function useGenerateVideo(): UseGenerateVideoReturn {
  const [generating, setGenerating] = useState(false);
  const addAgentVideo = useWorkspaceStore((s) => s.addAgentVideo);

  const generate = useCallback(
    async (
      sessionId: string,
      prompt = '',
      options: { duration?: number; aspect_ratio?: string } = {}
    ) => {
      if (generating) return; // 防止并发重复点击

      setGenerating(true);
      try {
        const apiBase = process.env.NEXT_PUBLIC_API_URL ?? '';
        const res = await fetch(
          `${apiBase}/api/sessions/${sessionId}/generate-video`,
          {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              prompt,
              duration: options.duration ?? 5,
              aspect_ratio: options.aspect_ratio ?? '16:9',
            }),
          }
        );

        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error((err as { detail?: string }).detail ?? '视频生成失败');
        }

        const data = (await res.json()) as { video: GeneratedVideo };

        // NOTE: 生成结果写入全局 Store，供独立视频卡片渲染
        addAgentVideo('visual', data.video.type, data.video.data_url);
      } finally {
        setGenerating(false);
      }
    },
    [generating, addAgentVideo]
  );

  return { generating, generate };
}
