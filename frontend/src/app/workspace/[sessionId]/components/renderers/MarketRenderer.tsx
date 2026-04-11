import React, { useMemo, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { stripHandoff, sharedMarkdownComponents } from './MarkdownRenderer';
import { ResearchProgressStep } from '@/store/workspaceStore';
import styles from '../WorkspaceFeed.module.css';
import marketStyles from './MarketRenderer.module.css';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { stripHandoff, sharedMarkdownComponents } from './MarkdownRenderer';
import { ResearchProgressStep } from '@/store/workspaceStore';
import styles from '../WorkspaceFeed.module.css';
import marketStyles from './MarketRenderer.module.css';

interface SearchCitation {
  type: 'market_data' | 'competitor' | 'user_review' | 'social_review';
  angle?: string;
  brand?: string;
  platform?: string;
  sentiment?: string;
  title: string;
  url: string;
  snippet: string;
}

export interface MarketRendererProps {
  output: string;
  isRunning: boolean;
  /** Wacksman 研究循环实时进度步骤 */
  researchProgress?: ResearchProgressStep[];
  /** 可选：透传 Agent ID 以复用时间轴 UI（market 或 strategy） */
  agentId?: 'market' | 'strategy';
  /** 当前语言 t 函数，缺省回退到中文默认值 */
  t?: (key: string) => string;
}

const BAD_EXTENSIONS = ['.txt', '.pdf', '.csv', '.zip', '.json', '.xml', '.rss', '.atom'];
const BAD_TITLE_SIGNALS = ['dict_', 'vocab.', '__', 'Rss', '.txt', '.pdf'];

function isValidCitation(c: SearchCitation): boolean {
  if (!c.url) return false;
  const urlLower = c.url.toLowerCase();
  if (BAD_EXTENSIONS.some(ext => urlLower.endsWith(ext))) return false;
  if (BAD_TITLE_SIGNALS.some(sig => c.title?.includes(sig))) return false;
  if (!c.snippet || c.snippet.trim().length < 10) return false;
  return true;
}

/**
 * 解析市场研究报告末尾的 <market_citations> 数据块
 */
function parseMarketOutput(raw: string): { content: string; citations: SearchCitation[] } {
  const citationsMatch = raw.match(/<market_citations>([\s\S]*?)<\/market_citations>/);
  const content = raw.replace(/<market_citations>[\s\S]*?<\/market_citations>/, '').trim();
  let citations: SearchCitation[] = [];
  if (citationsMatch) {
    try { 
      const parsed = JSON.parse(citationsMatch[1]); 
      citations = Array.isArray(parsed) ? parsed.filter(isValidCitation) : [];
    } catch { /* ignore */ }
  }
  return { content, citations };
}

/**
 * 市场研究 Agent（Wacksman）专属渲染器
 * 静默期：显示实时进度时间轴
 * 生成后：显示 Markdown 报告 + 来源引用卡片
 */
export function MarketRenderer({ output, isRunning, researchProgress = [], agentId = 'market', t }: MarketRendererProps) {
  const { content, citations } = useMemo(() => parseMarketOutput(output), [output]);

  const marketCitations = citations.filter((c) => c.type === 'market_data');
  const competitorCitations = citations.filter((c) => c.type === 'competitor');
  // NOTE: 只有真实爬虫成功抓到数据才展示，避免大模型凑假数据
  const reviewCitations = citations.filter((c) => c.type === 'user_review' && c.snippet && c.snippet.trim().length > 20);
  const socialCitations = citations.filter((c) => c.type === 'social_review' && c.snippet && c.snippet.trim().length > 20);

  // 将竞品引用按品牌分组
  const citationsByBrand = useMemo(() => {
    const map: Record<string, SearchCitation[]> = {};
    competitorCitations.forEach((c) => {
      const key = c.brand ?? '其他';
      if (!map[key]) map[key] = [];
      map[key].push(c);
    });
    return map;
  }, [competitorCitations]);

  const socialByPlatform = useMemo(() => {
    const map: Record<string, SearchCitation[]> = {};
    socialCitations.forEach((c) => {
      const key = c.platform ?? 'cross_platform';
      if (!map[key]) map[key] = [];
      map[key].push(c);
    });
    return map;
  }, [socialCitations]);

  if (!output && isRunning) {
    return (
      <div className={`${styles.cardOutput} markdown-body`}>
        {/* 实时研究进度时间轴 */}
        <div className={marketStyles.progressTimeline}>
          <div className={marketStyles.progressHeader}>
            <div className={marketStyles.searchSpinner} />
            <span className={marketStyles.progressTitle}>
              {agentId === 'strategy'
                ? (t?.('strategy.engine.title') ?? 'Trout 战略推演引擎运行中')
                : (t?.('market.engine.title') ?? 'Wacksman 研究引擎运行中')
              }
            </span>
            <span className={marketStyles.progressHint}>
              {agentId === 'strategy' ? '战略定位分析 · 约 30-50 秒' : '中型检索模式 · 约 20-40 秒'}
            </span>
          </div>

          {researchProgress.length === 0 ? (
            <div className={marketStyles.progressInitializing}>
              {agentId === 'strategy' ? '正在加载品牌战略全景框架…' : '正在启动联网工具…'}
            </div>
          ) : (
            <div className={marketStyles.progressSteps}>
              {researchProgress.map((p, i) => (
                <div
                  key={i}
                  className={`${marketStyles.progressStep} ${p.done ? marketStyles.progressStepDone : marketStyles.progressStepActive}`}
                >
                  <div className={marketStyles.progressStepDot}>
                    {p.done ? (
                      <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
                        <path d="M2 5l2.5 2.5L8 3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                      </svg>
                    ) : (
                      <div className={marketStyles.progressStepPulse} />
                    )}
                  </div>
                  <div className={marketStyles.progressStepContent}>
                    <span className={marketStyles.progressStepIndex} aria-hidden>
                      {i + 1}
                    </span>
                    <span className={marketStyles.progressStepDetail}>
                      {/* NOTE: label 是步骤标题（如"联网检索市场规模…"），detail 是搜索词等细节 */}
                      {p.label || p.detail}
                      {p.detail && p.label && p.detail !== p.label && (
                        <span className={marketStyles.progressStepSubDetail}> | {p.detail}</span>
                      )}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className={`${styles.cardOutput} markdown-body`}>
      {content && (
        <ReactMarkdown remarkPlugins={[remarkGfm]} components={sharedMarkdownComponents}>
          {stripHandoff(content)}
        </ReactMarkdown>
      )}

      {/* 来源引用区 — 始终可见，仅展示标题，省略详细内容 */}
      {citations.length > 0 && (
        <div className={marketStyles.citationsSection}>
          <p className={marketStyles.citationsTitle}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
              <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
            </svg>
            数据来源（{citations.length} 条检索引用）
          </p>

          {/* 市场数据来源 */}
          {marketCitations.length > 0 && (
            <div className={marketStyles.citationGroup}>
              <span className={marketStyles.citationGroupLabel}>市场数据</span>
              <div className={marketStyles.citationPills}>
                {marketCitations.map((c, i) => (
                  <a key={i} href={c.url} target="_blank" rel="noopener noreferrer" className={marketStyles.citationPill} title={c.title}>
                    {c.title || c.url}
                  </a>
                ))}
              </div>
            </div>
          )}

          {/* 竞品情报来源（按品牌分组） */}
          {Object.entries(citationsByBrand).map(([brand, items]) => (
            <div key={brand} className={marketStyles.citationGroup}>
              <span className={`${marketStyles.citationGroupLabel} ${marketStyles.citationGroupLabelCompetitor}`}>
                竞品：{brand}
              </span>
              <div className={marketStyles.citationPills}>
                {items.map((c, i) => (
                  <a key={i} href={c.url} target="_blank" rel="noopener noreferrer" className={`${marketStyles.citationPill} ${marketStyles.citationPillCompetitor}`} title={c.title}>
                    {c.title || c.url}
                  </a>
                ))}
              </div>
            </div>
          ))}

          {/* NOTE: 用户声音 — 只有真实抓到内容才显示，严防假数据 */}
          {Object.entries(socialByPlatform).map(([platform, items]) =>
            items.length > 0 ? (
              <div key={platform} className={marketStyles.citationGroup}>
                <span className={`${marketStyles.citationGroupLabel} ${marketStyles.citationGroupLabelSocial}`}>
                  用户声音：{platform}
                </span>
                <div className={marketStyles.citationPills}>
                  {items.map((c, i) => (
                    <a key={i} href={c.url} target="_blank" rel="noopener noreferrer" className={`${marketStyles.citationPill} ${marketStyles.citationPillSocial}`} title={c.title}>
                      {c.title || c.url}
                    </a>
                  ))}
                </div>
              </div>
            ) : null
          )}

          {/* NOTE: Jina 爬虫评价页 — 只有实际爬取成功才显示 */}
          {reviewCitations.length > 0 && (
            <div className={marketStyles.citationGroup}>
              <span className={`${marketStyles.citationGroupLabel} ${marketStyles.citationGroupLabelReview}`}>
                电商评价页爬取
              </span>
              <div className={marketStyles.citationPills}>
                {reviewCitations.map((c, i) => (
                  <a key={i} href={c.url} target="_blank" rel="noopener noreferrer" className={`${marketStyles.citationPill} ${marketStyles.citationPillReview}`} title={c.snippet}>
                    {c.platform?.toUpperCase()} 用户评价
                  </a>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
