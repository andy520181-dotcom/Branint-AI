'use client';

import type { RefObject } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { AGENT_CONFIGS } from '@/data/agentConfigs';
import { AgentId, AgentImage, AgentVideo } from '@/types';
import type { AgentConfig } from '@/types';
import { translateWorkspaceError } from '@/i18n/messages';
import type { RoundSnapshot } from '../workspaceTypes';
import styles from './WorkspaceFeed.module.css';

/**
 * 移除 Agent 输出中的 <handoff>...</handoff> 交接摘要
 * 这些是 Agent 间的内部协作数据，不展示给用户
 */
function stripHandoff(text: string): string {
  return text.replace(/<handoff>[\s\S]*?<\/handoff>/gi, '').trimEnd();
}

type TFn = (key: string) => string;

export interface WorkspaceFeedProps {
  feedRef: RefObject<HTMLDivElement | null>;
  previousRounds: RoundSnapshot[];
  userPrompt: string;
  avatarDataUrl: string | null;
  isStreaming: boolean;
  currentAgentId: AgentId | null;
  agents: Record<AgentId, { id: AgentId; status: string; output: string }>;
  visibleConfigs: AgentConfig[];
  agentImages?: AgentImage[];
  agentVideos?: AgentVideo[];
  handoffMsg: { agentId: AgentId; text: string } | null;
  error: string | null;
  t: TFn;
}

export function WorkspaceFeed({
  feedRef,
  previousRounds,
  userPrompt,
  avatarDataUrl,
  isStreaming,
  currentAgentId,
  agents,
  visibleConfigs,
  agentImages = [],
  agentVideos = [],
  handoffMsg,
  error,
  t,
}: WorkspaceFeedProps) {
  return (
    <div className={styles.feed}>
      {previousRounds.map((round, roundIndex) => {
        const roundConfigs = round.selectedAgents ? AGENT_CONFIGS.filter((c) => round.selectedAgents!.includes(c.id)) : AGENT_CONFIGS;
        const visibleRoundAgents = roundConfigs.filter((cfg) => {
          const s = round.agents[cfg.id as AgentId];
          return s && s.status !== 'waiting';
        });

        return (
          <div key={`round-${roundIndex}-${round.sessionId}`} className={styles.roundSection}>
            {roundIndex > 0 && (
              <div className={styles.roundSeparator}>
                <div className={styles.roundDividerLine} />
              </div>
            )}

            <div id={`workspace-round-${roundIndex}`} className={styles.userRoundAnchor}>
              <div className={styles.userMsgRow}>
                <div className={styles.userBubble}>{round.userPrompt}</div>
                <div className={styles.userAvatarWrap}>
                  {avatarDataUrl ? (
                    <img src={avatarDataUrl} alt="avatar" className={styles.userAvatarImg} />
                  ) : (
                    <svg
                      className={styles.userAvatarFallback}
                      width="20"
                      height="20"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="1.5"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    >
                      <path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2" />
                      <circle cx="12" cy="7" r="4" />
                    </svg>
                  )}
                </div>
              </div>
            </div>

            <div className={styles.roundContent}>
              {visibleRoundAgents.map((cfg, i) => {
                const state = round.agents[cfg.id as AgentId];
                const output = state?.output ?? '';
                const isDone = state?.status === 'completed';
                const hasNext = i < visibleRoundAgents.length - 1;
                return (
                  <div key={cfg.id}>
                    <div className={styles.feedItem}>
                      <div className={styles.feedLeft}>
                        <div className={styles.feedAvatar} style={{ '--agent-color': cfg.color } as React.CSSProperties}>
                          <img src={cfg.avatar} alt={cfg.charName} />
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
                        {hasNext && <div className={`${styles.feedLeftLine} ${styles.connectorDone}`} />}
                      </div>
                      <div className={styles.feedBubbleWrap}>
                        <div className={styles.feedBubble} style={{ '--agent-color': cfg.color } as React.CSSProperties}>
                          <div className={`${styles.cardOutput} markdown-body`}>
                            {output ? (
                              <ReactMarkdown remarkPlugins={[remarkGfm]}>{stripHandoff(output)}</ReactMarkdown>
                            ) : (
                              <span style={{ color: 'var(--text-muted)', fontSize: '13px' }}>—</span>
                            )}
                          </div>
                        </div>
                      </div>
                    </div>
                    {hasNext && (
                      <div className={styles.feedConnector}>
                        <div className={styles.connectorTrack}>
                          <div className={`${styles.connectorLine} ${styles.connectorDone}`} />
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        );
      })}

      <div ref={feedRef}>
        {userPrompt && (
          <div id="workspace-round-active" className={styles.userRoundAnchor}>
            <div className={styles.userMsgRow}>
              <div className={styles.userBubble}>{userPrompt}</div>
              <div className={styles.userAvatarWrap}>
                {avatarDataUrl ? (
                  <img src={avatarDataUrl} alt="avatar" className={styles.userAvatarImg} />
                ) : (
                  <svg
                    className={styles.userAvatarFallback}
                    width="20"
                    height="20"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2" />
                    <circle cx="12" cy="7" r="4" />
                  </svg>
                )}
              </div>
            </div>
          </div>
        )}

        {isStreaming && !currentAgentId && (
          <div className={styles.loadingState}>
            <div className={styles.globalSpinner} />
            <p>{t('workspace.connecting')}</p>
          </div>
        )}

        {visibleConfigs.map((cfg, i) => {
          const state = agents[cfg.id as AgentId];
          const output = state?.output ?? '';
          const status = state?.status ?? 'waiting';
          const isRunning = status === 'running';
          const isDone = status === 'completed';
          const isCurrent = cfg.id === currentAgentId;
          const hasNext = i < visibleConfigs.length - 1;
          const nextCfg = visibleConfigs[i + 1];
          const isTransferring = isDone && nextCfg?.id === currentAgentId;

          if (status === 'waiting') return null;

          const nextState = nextCfg ? agents[nextCfg.id as AgentId] : null;
          const nextVisible = nextState && nextState.status !== 'waiting';

          const hasConnector = hasNext && nextVisible;
          const lineClass = [styles.feedLeftLine, isTransferring ? styles.connectorActive : '', isDone && !isTransferring ? styles.connectorDone : ''].join(' ');

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
                    <div className={`${styles.cardOutput} markdown-body`}>
                      {output ? (
                        <>
                          <ReactMarkdown remarkPlugins={[remarkGfm]}>{stripHandoff(output)}</ReactMarkdown>
                          {agentImages.filter(img => img.agentId === cfg.id).length > 0 && (
                            <div className={styles.agentImagesContainer}>
                              {agentImages.filter(img => img.agentId === cfg.id).map((img, idx) => (
                                <img key={idx} src={img.dataUrl} alt={`Generated by ${cfg.id}`} className={styles.agentImage} />
                              ))}
                            </div>
                          )}
                          {agentVideos.filter(vid => vid.agentId === cfg.id).length > 0 && (
                            <div className={styles.agentVideosContainer}>
                              {agentVideos.filter(vid => vid.agentId === cfg.id).map((vid, idx) => (
                                <video 
                                  key={idx} 
                                  src={vid.dataUrl} 
                                  controls 
                                  className={styles.agentVideo} 
                                  poster={agentImages.find(img => img.agentId === cfg.id)?.dataUrl}
                                />
                              ))}
                            </div>
                          )}
                        </>
                      ) : (
                        <div className={styles.thinking}>
                          <span className={styles.thinkingDot} />
                          <span className={styles.thinkingDot} />
                          <span className={styles.thinkingDot} />
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              </div>
              {connector}
            </div>
          );
        })}

        {error && (
          <div className={styles.errorCard}>
            <p>⚠️ {translateWorkspaceError(error, t)}</p>
            <a href="/" className="btn-ghost">
              {t('workspace.retry')}
            </a>
          </div>
        )}
      </div>
    </div>
  );
}
