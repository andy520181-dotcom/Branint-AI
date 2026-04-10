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
  /**
   * 供操作底栏使用的原始数据（Markdown 文本）
   * 传入时复制按钮可用；缺省时操作栏整块隐藏
   */
  rawOutput?: string;
  /**
   * 无边框纯气泡模式（首轮 consultant_plan 占位卡片）
   * 为 true 时隐藏所有操作按钮
   */
  plainBubble?: boolean;
  /**
   * 操作按钮触发 Toast 的回调，由父级 page.tsx 统一管控
   * 替代原来的 alert() 方案，不阻塞主线程
   */
  onToast?: (msg: string) => void;
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
  onToast,
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
    // TODO: 连接品牌套件一键导出功能（PPT/综合报告），后端接口就绪后替换此占位文案
    onToast?.(t('agent.action.download.wip'));
  };

  const handleShare = () => {
    const url = window.location.href;
    navigator.clipboard.writeText(url)
      .then(() => {
        onToast?.(t('agent.action.share.copied'));
      })
      .catch(() => {
        onToast?.(t('agent.action.share.failed'));
      });
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

            <div className={styles.aiDisclaimer}>
              本回答由 AI 生成，内容仅供参考
            </div>

            {/* 智能体操作底栏：任务完成且不处于首轮打底时显示 */}
            {isDone && !plainBubble && (
              <div className={styles.feedActions}>
                <button className={styles.actionBtn} onClick={handleCopy} title="复制">
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
                <button className={styles.actionBtn} onClick={handleShare} title="分享">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="18" cy="5" r="3"></circle>
                    <circle cx="6" cy="12" r="3"></circle>
                    <circle cx="18" cy="19" r="3"></circle>
                    <line x1="8.59" y1="13.51" x2="15.42" y2="17.49"></line>
                    <line x1="15.41" y1="6.51" x2="8.59" y2="10.49"></line>
                  </svg>
                </button>
                <button className={`${styles.actionBtn} ${styles.primaryActionBtn}`} onClick={handleDownload} title="下载">
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
