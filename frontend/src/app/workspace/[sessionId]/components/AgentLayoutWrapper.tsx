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
  t,
  children,
}: AgentLayoutWrapperProps) {
  if (status === 'waiting') return null;

  const isRunning = status === 'running';
  const isDone = status === 'completed';

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
          <div className={`${styles.feedBubble} ${isRunning ? styles.feedBubbleActive : ''}`} style={{ '--agent-color': cfg.color } as React.CSSProperties}>
            {children}
          </div>
        </div>
      </div>
      {connector}
    </div>
  );
}
