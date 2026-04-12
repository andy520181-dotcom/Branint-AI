'use client';

/**
 * useGenerateAsset — 路径A视觉资产生成 Hook
 *
 * 当用户在美术指导 Agent 气泡底部点击生成按钮时调用，
 * 调用后端 /generate-asset 接口，返回图片 URL 列表。
 */

import { useState, useCallback } from 'react';

export type AssetType = 'logo' | 'poster' | 'banner';

export interface GeneratedImage {
  type: AssetType;
  mime: string;
  data_url: string;
}

interface UseGenerateAssetReturn {
  /** 正在生成中的资产类型，null 表示空闲 */
  generating: AssetType | null;
  /** 生成结果（历次累积） */
  images: GeneratedImage[];
  /** 触发生成 */
  generate: (sessionId: string, assetType: AssetType, count?: number) => Promise<void>;
  /** 清空本地结果（不影响持久化） */
  clearImages: () => void;
}

export function useGenerateAsset(): UseGenerateAssetReturn {
  const [generating, setGenerating] = useState<AssetType | null>(null);
  const [images, setImages] = useState<GeneratedImage[]>([]);

  const generate = useCallback(async (
    sessionId: string,
    assetType: AssetType,
    count = 1,
  ) => {
    if (generating) return; // 防止并发重复点击

    setGenerating(assetType);
    try {
      const res = await fetch(`/api/sessions/${sessionId}/generate-asset`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ asset_type: assetType, count }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error((err as { detail?: string }).detail ?? '生成失败');
      }

      const data = (await res.json()) as { images: GeneratedImage[] };
      setImages((prev) => [...prev, ...data.images]);
    } finally {
      setGenerating(null);
    }
  }, [generating]);

  const clearImages = useCallback(() => setImages([]), []);

  return { generating, images, generate, clearImages };
}
