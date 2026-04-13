'use client';

/**
 * useGenerateAsset — 路径A视觉资产生成 Hook
 *
 * 当用户在美术指导 Agent 气泡底部点击生成按钮时调用，
 * 调用后端 /generate-asset 接口，返回图片 URL 列表。
 * 生成结果同步写入 workspaceStore，供气泡外的独立卡片渲染使用。
 */

import { useState, useCallback } from 'react';
import { useWorkspaceStore } from '@/store/workspaceStore';

// NOTE: 与后端 ASSET_SPECS 保持同步，后端有关键词映射兜底，前端直接传 type 字符串即可
export type AssetType = 'logo' | 'poster' | 'banner' | 'digital_ad' | 'packaging' | 'presentation' | string;

export interface GeneratedImage {
  type: AssetType;
  mime: string;
  data_url: string;
}

interface UseGenerateAssetReturn {
  /** 正在生成中的资产类型，null 表示空闲 */
  generating: AssetType | null;
  /** 触发生成 */
  generate: (sessionId: string, assetType: AssetType, count?: number) => Promise<void>;
}

export function useGenerateAsset(): UseGenerateAssetReturn {
  const [generating, setGenerating] = useState<AssetType | null>(null);
  const addAgentImage = useWorkspaceStore((s) => s.addAgentImage);

  const generate = useCallback(async (
    sessionId: string,
    assetType: AssetType,
    count = 1,
  ) => {
    if (generating) return; // 防止并发重复点击

    setGenerating(assetType);
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL ?? '';
      const res = await fetch(`${apiBase}/api/sessions/${sessionId}/generate-asset`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ asset_type: assetType, count }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error((err as { detail?: string }).detail ?? '生成失败');
      }

      const data = (await res.json()) as { images: GeneratedImage[] };

      // NOTE: 生成结果写入全局 Store，供气泡外独立图片卡片渲染
      data.images.forEach((img) => {
        addAgentImage('visual', img.type, img.data_url);
      });
    } finally {
      setGenerating(null);
    }
  }, [generating, addAgentImage]);

  return { generating, generate };
}
