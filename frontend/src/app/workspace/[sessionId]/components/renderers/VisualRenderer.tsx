'use client';

import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { AgentId } from '@/types';
import { stripHandoff } from './MarkdownRenderer';
import { ImageAssetCard } from './ImageAssetCard';
import { useGenerateAsset, type AssetType } from '@/hooks/useGenerateAsset';
import styles from '../WorkspaceFeed.module.css';
import assetStyles from './VisualRenderer.module.css';

export interface VisualRendererProps {
  output: string;
  agentId: AgentId;
  sessionId: string;
  isRunning: boolean;
  /** isDone 为 true 时才显示生成按钮 */
  isDone: boolean;
}

const ASSET_BUTTONS: Array<{ type: AssetType; label: string; count: number }> = [
  { type: 'logo',   label: '生成 Logo ×2', count: 2 },
  { type: 'poster', label: '生成品牌海报', count: 1 },
  { type: 'banner', label: '生成推广 Banner', count: 1 },
];

/**
 * 专为美术指导 Agent (Scher) 设计的渲染器。
 *
 * 路径 A 架构：
 *   - 主气泡：纯文字版视觉策略报告
 *   - 气泡底部：生成按钮行（仅在 Agent 完成后显示）
 *   - 按钮点击后：在气泡正下方渲染独立的 ImageAssetCard 卡片
 */
export function VisualRenderer({
  output,
  agentId,
  sessionId,
  isRunning,
  isDone,
}: VisualRendererProps) {
  const { generating, images, generate } = useGenerateAsset();
  // NOTE: 记录已点击的按钮，避免重复触发同类型
  const [triggered, setTriggered] = useState<Set<AssetType>>(new Set());

  const handleGenerate = async (assetType: AssetType, count: number) => {
    if (triggered.has(assetType) || generating) return;
    setTriggered((prev) => new Set(prev).add(assetType));
    await generate(sessionId, assetType, count);
  };

  if (!output && isRunning) {
    return (
      <div className={`${styles.cardOutput} markdown-body`}>
        <div className={styles.thinking}>
          <span className={styles.thinkingDot} />
          <span className={styles.thinkingDot} />
          <span className={styles.thinkingDot} />
        </div>
      </div>
    );
  }

  // 按资产类型分组现有图片
  const imagesByType = images.reduce<Record<string, typeof images>>((acc, img) => {
    const key = img.type;
    if (!acc[key]) acc[key] = [];
    acc[key].push(img);
    return acc;
  }, {});

  return (
    <div className={`${styles.cardOutput} markdown-body`}>
      {output ? (
        <>
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{stripHandoff(output)}</ReactMarkdown>

          {/* 路径 A：Agent 完成后展示显式生成按钮行 */}
          {isDone && (
            <div className={assetStyles.actionBar}>
              <span className={assetStyles.actionBarLabel}>生成视觉资产</span>
              <div className={assetStyles.actionBtns}>
                {ASSET_BUTTONS.map(({ type, label, count }) => (
                  <button
                    key={type}
                    className={`${assetStyles.actionBtn} ${triggered.has(type) ? assetStyles.actionBtnTriggered : ''}`}
                    onClick={() => void handleGenerate(type, count)}
                    disabled={!!generating || triggered.has(type)}
                    title={triggered.has(type) ? '已生成，可在下方查看' : label}
                  >
                    {generating === type ? (
                      <span className={assetStyles.spinner} />
                    ) : (
                      <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                        <path d="M6 1v5M6 6l3-3M6 6L3 3" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
                        <rect x="1" y="9" width="10" height="1.5" rx="0.75" fill="currentColor"/>
                      </svg>
                    )}
                    {triggered.has(type) ? '已生成 ✓' : label}
                  </button>
                ))}
              </div>
            </div>
          )}
        </>
      ) : (
        <span className="prose-empty">—</span>
      )}

      {/* 独立图片资产卡片——位于气泡下方，与文字策略完全分离 */}
      {ASSET_BUTTONS.map(({ type }) => {
        const typeImages = imagesByType[type] ?? [];
        const isLoadingThis = generating === type;
        if (!isLoadingThis && typeImages.length === 0) return null;
        return (
          <ImageAssetCard
            key={type}
            assetType={type}
            images={typeImages}
            isLoading={isLoadingThis}
          />
        );
      })}
    </div>
  );
}
