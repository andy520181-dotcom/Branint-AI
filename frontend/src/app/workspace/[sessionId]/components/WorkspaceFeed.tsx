'use client';

import { useEffect, type RefObject } from 'react';
import { AGENT_CONFIGS } from '@/data/agentConfigs';
import type { AgentId, AgentImage, AgentVideo, AgentConfig } from '@/types';
import { translateWorkspaceError } from '@/i18n/messages';
import type { RoundSnapshot } from '../workspaceTypes';
import { UserMsgBubble } from './UserMsgBubble';
import { AgentLayoutWrapper } from './AgentLayoutWrapper';
import { RendererFactory } from './renderers/RendererFactory';
import styles from './WorkspaceFeed.module.css';

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
  assetRecommendations?: Record<AgentId, any[]>;
  handoffMsg: { agentId: AgentId; text: string } | null;
  error: string | null;
  isClarifying?: boolean;
  /** 当前 session ID，供美术指导 Agent 的显式生成接口使用 */
  sessionId: string;
  /** Toast 回调：由 page.tsx 传入，避免 AgentLayoutWrapper 使用 alert() */
  onToast?: (msg: string) => void;
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
  sessionId,
  agentImages = [],
  agentVideos = [],
  assetRecommendations = {},
  handoffMsg,
  error,
  isClarifying = false,
  onToast,
  t,
}: WorkspaceFeedProps) {
  useEffect(() => {
    if (error && onToast) {
      onToast(translateWorkspaceError(error, t));
    }
  }, [error, onToast, t]);

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
              <UserMsgBubble prompt={round.userPrompt} avatarDataUrl={avatarDataUrl} />
            </div>

            <div className={styles.roundContent}>
              {visibleRoundAgents.map((cfg, i) => {
                const state = round.agents[cfg.id as AgentId];
                const output = state?.output ?? '';
                const isDone = state?.status === 'completed';
                const hasNext = i < visibleRoundAgents.length - 1;
                return (
                  <AgentLayoutWrapper
                    key={cfg.id}
                    cfg={cfg}
                    status={state?.status ?? 'waiting'}
                    hasNext={hasNext}
                    hasConnector={hasNext}
                    rawOutput={output}
                    plainBubble={false}
                    onToast={onToast}
                    t={t}
                  >
                    <RendererFactory
                      agentId={cfg.id as AgentId}
                      output={output}
                      status={state?.status ?? 'waiting'}
                      sessionId={sessionId}
                      isDone={state?.status === 'completed'}
                      agentImages={agentImages}
                      agentVideos={agentVideos}
                      assetRecommendations={assetRecommendations}
                      t={t}
                    />
                  </AgentLayoutWrapper>
                );
              })}
            </div>
          </div>
        );
      })}

      <div ref={feedRef}>
        {userPrompt && (
          <div id="workspace-round-active" className={styles.userRoundAnchor}>
            <UserMsgBubble prompt={userPrompt} avatarDataUrl={avatarDataUrl} />
          </div>
        )}

        {isStreaming && !currentAgentId && (
          <AgentLayoutWrapper
            key={isClarifying ? "pre-strategy" : "pre-consultant"}
            cfg={isClarifying ? AGENT_CONFIGS.find(c => c.id === 'strategy')! : AGENT_CONFIGS[0]}
            status="running"
            isCurrent={true}
            hasNext={false}
            hasConnector={false}
            isTransferring={false}
            plainBubble={false}
            onToast={onToast}
            t={t}
          >
            <RendererFactory
              agentId={isClarifying ? 'strategy' : 'consultant_plan'}
              output=""
              status="running"
              sessionId={sessionId}
              isDone={false}
              t={t}
            />
          </AgentLayoutWrapper>
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
          const hasConnector = Boolean(hasNext && nextVisible);
          return (
            <AgentLayoutWrapper
              key={cfg.id}
              cfg={cfg}
              status={status}
              isCurrent={isCurrent}
              hasNext={hasNext}
              hasConnector={hasConnector}
              isTransferring={isTransferring}
              handoffMsg={handoffMsg}
              rawOutput={output}
              plainBubble={false}
              onToast={onToast}
              t={t}
            >
              <RendererFactory
                agentId={cfg.id as AgentId}
                output={output}
                status={status}
                sessionId={sessionId}
                isDone={isDone}
                agentImages={agentImages}
                agentVideos={agentVideos}
                assetRecommendations={assetRecommendations}
                t={t}
              />
            </AgentLayoutWrapper>
          );
        })}
      </div>
    </div>
  );
}
