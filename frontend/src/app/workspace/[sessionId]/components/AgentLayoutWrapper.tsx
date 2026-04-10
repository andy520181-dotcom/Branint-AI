import React from 'react';
import type { AgentConfig, AgentId } from '@/types';
import styles from './WorkspaceFeed.module.css';

export interface AgentLayoutWrapperProps {
  cfg: AgentConfig;
  status: 'waiting' | 'running' | 'completed' | 'error' | string;
  isCurrent?: boolean;
  hasNext?: boolean;
  hasConnector?: boolean;
  isTransferring?: boolean;
  handoffMsg?: { agentId: AgentId; text: string } | null;
  /** 首轮 consultant_plan：无边框气泡，与列表内其它 Agent 卡片风格对齐 */
  /** 供操作底栏使用的原始数据 */
  rawOutput?: string;
  t: (key: string) => string;
  children: React.ReactNode;
}

/**
 * 封装各个 Agent 卡片的外部壳子 (Shell)
 * 提取了左侧头像、加载动画、状态标识以及下方的连接线(Connector)逻辑。
 */
export function AgentLayoutWrapper({
  cfg,
  status,
  isCurrent,
  hasConnector,
  isTransferring,
  handoffMsg,
  rawOutput,
  plainBubble,
  t,
  children,
}: AgentLayoutWrapperProps) {
  const [copied, setCopied] = React.useState(false);

  if (status === 'waiting') return null;

  const isRunning = status === 'running';
  const isDone = status === 'completed';

  const handleCopy = () => {
    if (!rawOutput) return;
    navigator.clipboard.writeText(rawOutput);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownload = () => {
    alert('【敬请期待】一键打包品牌套件（PPT大课件/综合报告）大模型排版功能火热开发中！🚀');
  };

  const lineClass = [
    styles.feedLeftLine,
    isTransferring ? styles.connectorActive : '',
    isDone && !isTransferring ? styles.connectorDone : '',
  ].join(' ');

  const connector = hasConnector ? (
    <div className={styles.feedConnector}>
      <div className={styles.connectorTrack}>
        <div
          className={`${styles.connectorLine} ${isTransferring ? styles.connectorActive : ''} ${isDone && !isTransferring ? styles.connectorDone : ''}`}
        />
      </div>
      {handoffMsg?.agentId === cfg.id && (
        <div className={styles.handoffBubble}>
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
            <path d="M6 1v7M6 8l-3-3M6 8l3-3" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          {handoffMsg.text}
        </div>
      )}
    </div>
  ) : null;

  return (
    <div key={cfg.id}>
      <div className={styles.feedItem}>
        <div className={styles.feedLeft}>
          <div
            className={`${styles.feedAvatar} ${isCurrent ? styles.feedAvatarActive : ''}`}
            style={{ '--agent-color': cfg.color } as React.CSSProperties}
          >
            <img src={cfg.avatar} alt={cfg.charName} />
            {isCurrent && <span className={styles.feedSpinner} />}
            {isDone && (
              <span className={styles.feedDoneCheck}>
                <svg width="8" height="6" viewBox="0 0 8 6" fill="none">
                  <path d="M1 3L3 5L7 1" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </span>
            )}
          </div>
          <div className={styles.feedAgentInfo}>
            <span className={styles.feedAgentName}>{t(`agent.${cfg.id}.name`)}</span>
            <span className={styles.feedAgentChar}>{cfg.charName}</span>
          </div>
          {hasConnector && (
            <div className={lineClass}>
              {isTransferring && <span className={styles.connectorParticle} />}
            </div>
          )}
        </div>

        <div className={styles.feedBubbleWrap}>
          {(isRunning || isDone) && (
            <div className={styles.feedBubbleStatus}>
              {isRunning && (
                <div className={styles.feedRunning}>
                  <span className={styles.runningDot} style={{ background: cfg.color }} />
                  {t('workspace.analyzing')}
                </div>
              )}
              {isDone && (
                <div className={styles.feedDone} style={{ color: cfg.color }}>
                  {t('workspace.done')}
                </div>
              )}
            </div>
          )}
          <div
            className={`${styles.feedBubble} ${plainBubble ? styles.feedBubblePlain : ''} ${isRunning ? styles.feedBubbleActive : ''}`}
            style={{ '--agent-color': cfg.color } as React.CSSProperties}
          >
            {children}
            
            {/* 智能体操作底栏：任务完成且不处于首轮打底时显示 */}
            {isDone && !plainBubble && (
              <div className={styles.feedActions}>
                <button className={styles.actionBtn} onClick={handleCopy} title="复制生成内容">
                  {copied ? (
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M20 6L9 17l-5-5" />
                    </svg>
                  ) : (
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                      <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
                    </svg>
                  )}
                </button>
                <button className={`${styles.actionBtn} ${styles.primaryActionBtn}`} onClick={handleDownload} title="获取综合排版报告">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                    <polyline points="7 10 12 15 17 10"></polyline>
                    <line x1="12" y1="15" x2="12" y2="3"></line>
                  </svg>
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
      {connector}
    </div>
  );
}
