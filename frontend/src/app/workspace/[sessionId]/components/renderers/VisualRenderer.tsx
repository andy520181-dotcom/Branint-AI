'use client';

import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { AgentId } from '@/types';
import { stripHandoff } from './MarkdownRenderer';
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
  /** 动态推荐的生成资产项 */
  assetRecommendations?: Record<AgentId, any[]>;
}

/**
 * 专为美术指导 Agent (Scher) 设计的渲染器。
 *
 * 路径 B 架构（方案 B）：
 *   - 主气泡：纯文字版视觉策略报告 + 胶囊操作按钮行
 *   - 图片：生成后写入 workspaceStore，由 WorkspaceFeed 在气泡外作为独立卡片渲染
 */
export function VisualRenderer({
  output,
  agentId,
  sessionId,
  isRunning,
  isDone,
  assetRecommendations = {},
}: VisualRendererProps) {
  const { generating, generate } = useGenerateAsset();
  // NOTE: 记录已点击的按钮下标，避免重复触发同一按钮
  const [triggered, setTriggered] = useState<Set<string>>(new Set());

  const handleGenerate = async (assetType: AssetType, count: number, keyStr: string) => {
    if (triggered.has(keyStr) || generating) return;
    setTriggered((prev) => new Set(prev).add(keyStr));
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

  return (
    <div className={`${styles.cardOutput} markdown-body`}>
      {output ? (
        <>
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{stripHandoff(output)}</ReactMarkdown>

          {/* 路径 B：Agent 完成后展示显式生成按钮行（图片在气泡外独立显示） */}
          {isDone && (assetRecommendations[agentId] || []).length > 0 && (
            <div className={assetStyles.actionBar}>
              <div className={assetStyles.actionBtns}>
                {Array.from(new Set((assetRecommendations[agentId] || []).map(r => r.type))).map((type, idx) => {
                  const keyStr = `${type}-${idx}`;
                  const { label, count } = (assetRecommendations[agentId] || []).find(r => r.type === type) || { label: '', count: 1 };
                  return (
                    <button
                      key={keyStr}
                      className={`${assetStyles.actionBtn} ${triggered.has(keyStr) ? assetStyles.actionBtnTriggered : ''}`}
                      onClick={() => void handleGenerate(type, count, keyStr)}
                      disabled={!!generating || triggered.has(keyStr)}
                      title={triggered.has(keyStr) ? '已生成，见下方卡片' : label}
                    >
                      {generating === type ? (
                        <span className={assetStyles.spinner} />
                      ) : (
                        <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                          <path d="M6 1v5M6 6l3-3M6 6L3 3" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
                          <rect x="1" y="9" width="10" height="1.5" rx="0.75" fill="currentColor"/>
                        </svg>
                      )}
                      {triggered.has(keyStr) ? '已生成 ✓' : label}
                    </button>
                  );
                })}
              </div>
            </div>
          )}
        </>
      ) : (
        <span className="prose-empty">—</span>
      )}
    </div>
  );
}
