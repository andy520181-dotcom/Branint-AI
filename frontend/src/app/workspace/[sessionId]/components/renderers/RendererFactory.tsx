import React from 'react';
import type { AgentId, AgentImage, AgentVideo } from '@/types';
import { useWorkspaceStore, ResearchProgressStep } from '@/store/workspaceStore';
import { MarkdownRenderer } from './MarkdownRenderer';
import { VisualRenderer } from './VisualRenderer';
import { MarketRenderer } from './MarketRenderer';
import styles from '../WorkspaceFeed.module.css';

// NOTE: 稳定的空数组引用，避免 selector 内 `?? []` 每次返回新对象
// 若用内联 `?? []`，Zustand 的 Object.is() 比较每次都失败 → 无限重渲染
const EMPTY_PROGRESS: ResearchProgressStep[] = [];

export interface RendererFactoryProps {
  agentId: AgentId;
  output: string;
  status: string;
  /** 当前 session ID，供美术指导 Agent 的显式生成接口使用 */
  sessionId: string;
  /** Agent 是否已完成输出，用于控制生成按钮的显隐 */
  isDone: boolean;
  agentImages?: AgentImage[];
  agentVideos?: AgentVideo[];
  assetRecommendations?: Record<AgentId, any[]>;
  /** 传入 t 函数，供 MarkdownRenderer 内的品牌屋等子组件使用 i18n */
  t?: (key: string) => string;
}

/**
 * Renderer 微内核路由调度
 * 根据当前传入的 agentId 返回对应的组件。所有复杂的排版交互在这里分发，
 * 避免 WorkspaceFeed 变成巨大的代码垃圾桶。
 */
export function RendererFactory({
  agentId,
  output,
  sessionId,
  isDone,
  status,
  agentImages = [],
  agentVideos = [],
  assetRecommendations = {},
  t,
}: RendererFactoryProps) {
  const isRunning = status === 'running';
  // NOTE: 读取当前 agent 的实时进度
  // 使用模块级常量 EMPTY_PROGRESS 作为 fallback，保证引用稳定
  const researchProgress = useWorkspaceStore(
    (s) => s.agents[agentId]?.researchProgress
  ) ?? EMPTY_PROGRESS;

  // 过滤掉后端用于结构化处理的修补标签，避免暴露给用户
  // 响应【90/10法则】的 90% 严谨区：全局强制剃毛，剥离所有 emoji 确保商务高层汇报视觉基调
  const displayOutput = output
    .replace(/<PATCH_BLOCK>/g, '')
    .replace(/<\/PATCH_BLOCK>/g, '')
    .replace(/[\p{Emoji_Presentation}\p{Extended_Pictographic}]/gu, '');

  // 当还未生成内容且在 "thinking" 时统一使用点点点动画
  // NOTE: market 和 visual 有自己的等待态，这里排除
  if (!displayOutput && isRunning && agentId !== 'visual' && agentId !== 'market' && agentId !== 'strategy') {
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

  // 1. 市场研究 Agent：带来源引用卡片 + 实时进度时间轴的专属渲染器
  if (agentId === 'market') {
    return <MarketRenderer output={displayOutput} isRunning={isRunning} researchProgress={researchProgress} />;
  }
  
  // 1.5 战略推演 Agent：利用 MarketRenderer 的时间轴结构展示分析进度
  if (agentId === 'strategy') {
    if (!displayOutput && isRunning) {
      // 在生成具体文本前，调用 MarketRenderer 仅展示推演进度
      return <MarketRenderer output={displayOutput} isRunning={isRunning} researchProgress={researchProgress} agentId="strategy" />;
    }
  }

  // 2. 拦截美术指导 Agent，交由路径 A 专有的纯文本+独立图片卡片视图负责
  if (agentId === 'visual') {
    return (
      <VisualRenderer
        agentId={agentId}
        output={displayOutput}
        sessionId={sessionId}
        isDone={isDone}
        isRunning={isRunning}
        assetRecommendations={assetRecommendations}
      />
    );
  }

  // 3. 默认兜底：常规的 Markdown
  return <MarkdownRenderer output={displayOutput} t={t} />;
}
