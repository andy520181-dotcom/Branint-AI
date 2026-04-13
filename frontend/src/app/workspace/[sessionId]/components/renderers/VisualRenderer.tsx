'use client';

import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { AgentId } from '@/types';
import { stripHandoff } from './MarkdownRenderer';
import { useGenerateAsset, type AssetType } from '@/hooks/useGenerateAsset';
import { useGenerateVideo } from '@/hooks/useGenerateVideo';
import styles from '../WorkspaceFeed.module.css';
import assetStyles from './VisualRenderer.module.css';

export interface VisualRendererProps {
  output: string;
  agentId: AgentId;
  sessionId: string;
  isRunning: boolean;
  isDone: boolean;
  assetRecommendations?: Record<AgentId, any[]>;
}

/**
 * 专为美术指导 Agent (Scher) 设计的渲染器。
 * 路径 B 架构：主气泡展示纯文字视觉策略 + 胶囊操作按钮；图片/视频在气泡外独立渲染。
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
  const { generating: generatingVideo, generate: generateVideo } = useGenerateVideo();

  // NOTE: 记录已点击的按钮下标，避免重复触发同一按钮
  const [triggered, setTriggered] = useState<Set<string>>(new Set());
  const [videoTriggered, setVideoTriggered] = useState(false);

  const handleGenerate = async (assetType: AssetType, count: number, keyStr: string) => {
    if (triggered.has(keyStr) || generating) return;
    setTriggered((prev) => new Set(prev).add(keyStr));
    await generate(sessionId, assetType, count);
  };

  const handleGenerateVideo = async () => {
    if (videoTriggered || generatingVideo) return;
    setVideoTriggered(true);
    await generateVideo(sessionId);
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

  const recs = assetRecommendations[agentId] || [];

  return (
    <div className={`${styles.cardOutput} markdown-body`}>
      {output ? (
        <>
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{stripHandoff(output)}</ReactMarkdown>

          {isDone && (
            <div className={assetStyles.actionBar}>
              <div className={assetStyles.actionBtns}>
                {/* 图片推荐按钮列表（Scher 动态推荐） */}
                {Array.from(new Set(recs.map(r => r.type))).map((type, idx) => {
                  const keyStr = `${type}-${idx}`;
                  const { label, count } = recs.find(r => r.type === type) || { label: '', count: 1 };
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

                {/* NOTE: 品牌概念视频生成按钮（固定展示，不依赖推荐列表；Kling AI / 即梦，生成约1-3分钟） */}
                <button
                  className={`${assetStyles.actionBtn} ${assetStyles.actionBtnVideo} ${videoTriggered ? assetStyles.actionBtnTriggered : ''}`}
                  onClick={() => void handleGenerateVideo()}
                  disabled={generatingVideo || videoTriggered}
                  title={videoTriggered ? '视频生成中，需要30-180秒，请等待…' : '生成品牌概念视频（5秒，约需1-3分钟）'}
                >
                  {generatingVideo ? (
                    <span className={assetStyles.spinner} />
                  ) : (
                    <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                      <rect x="1" y="2.5" width="7" height="7" rx="1.2" stroke="currentColor" strokeWidth="1.3"/>
                      <path d="M8.5 4.5L11 3v6l-2.5-1.5V4.5z" fill="currentColor"/>
                    </svg>
                  )}
                  {videoTriggered
                    ? (generatingVideo ? '视频生成中…' : '视频已生成 ✓')
                    : '生成品牌视频'}
                </button>
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
