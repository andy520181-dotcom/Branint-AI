import React from 'react';
import type { AgentId, AgentImage, AgentVideo } from '@/types';
import { MarkdownRenderer } from './MarkdownRenderer';
import { VisualRenderer } from './VisualRenderer';
import { MarketRenderer } from './MarketRenderer';
import styles from '../WorkspaceFeed.module.css';

export interface RendererFactoryProps {
  agentId: AgentId;
  output: string;
  status: string;
  agentImages?: AgentImage[];
  agentVideos?: AgentVideo[];
}

/**
 * Renderer 微内核路由调度
 * 根据当前传入的 agentId 返回对应的组件。所有复杂的排版交互在这里分发，
 * 避免 WorkspaceFeed 变成巨大的代码垃圾桶。
 */
export function RendererFactory({
  agentId,
  output,
  status,
  agentImages = [],
  agentVideos = [],
}: RendererFactoryProps) {
  const isRunning = status === 'running';

  // 当还未生成内容且在 "thinking" 时统一使用点点点动画
  // NOTE: market 和 visual 有自己的等待态，这里排除
  if (!output && isRunning && agentId !== 'visual' && agentId !== 'market') {
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

  // 1. 市场研究 Agent：带来源引用卡片的专属渲染器
  if (agentId === 'market') {
    return <MarketRenderer output={output} isRunning={isRunning} />;
  }

  // 2. 拦截美术指导 Agent，交由专有的多媒体视图负责
  if (agentId === 'visual') {
    return (
      <VisualRenderer
        agentId={agentId}
        output={output}
        agentImages={agentImages}
        agentVideos={agentVideos}
        isRunning={isRunning}
      />
    );
  }

  // 3. 默认兜底：常规的 Markdown
  return <MarkdownRenderer output={output} />;
}
