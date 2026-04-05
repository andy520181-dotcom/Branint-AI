import React, { useMemo } from 'react';
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
}

/**
 * 解析市场研究报告末尾的 <market_citations> 数据块
 */
function parseMarketOutput(raw: string): { content: string; citations: SearchCitation[] } {
  const citationsMatch = raw.match(/<market_citations>([\s\S]*?)<\/market_citations>/);
  const content = raw.replace(/<market_citations>[\s\S]*?<\/market_citations>/, '').trim();
  let citations: SearchCitation[] = [];
  if (citationsMatch) {
    try { citations = JSON.parse(citationsMatch[1]); } catch { /* ignore */ }
  }
  return { content, citations };
}

/**
 * 市场研究 Agent（Wacksman）专属渲染器
 * 静默期：显示实时进度时间轴
 * 生成后：显示 Markdown 报告 + 来源引用卡片
 */
export function MarketRenderer({ output, isRunning, researchProgress = [] }: MarketRendererProps) {
  const { content, citations } = useMemo(() => parseMarketOutput(output), [output]);

  const marketCitations = citations.filter((c) => c.type === 'market_data');
  const competitorCitations = citations.filter((c) => c.type === 'competitor');
  const reviewCitations = citations.filter((c) => c.type === 'user_review');
  const socialCitations = citations.filter((c) => c.type === 'social_review');

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
      const key = (c as any).platform ?? 'cross_platform';
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
              Wacksman 研究引擎运行中
            </span>
            <span className={marketStyles.progressHint}>中型检索模式 · 约 20-40 秒</span>
          </div>

          {researchProgress.length === 0 ? (
            <div className={marketStyles.progressInitializing}>
              正在启动联网工具…
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
                    <span className={marketStyles.progressStepDetail}>{p.detail}</span>
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

      {/* 来源引用卡片区 */}
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
              <div className={marketStyles.citationCards}>
                {marketCitations.slice(0, 6).map((c, i) => (
                  <a
                    key={i}
                    href={c.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className={marketStyles.citationCard}
                  >
                    <span className={marketStyles.citationCardTitle}>{c.title || c.url}</span>
                    {c.snippet && (
                      <span className={marketStyles.citationCardSnippet}>
                        {c.snippet.slice(0, 80)}…
                      </span>
                    )}
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
              <div className={marketStyles.citationCards}>
                {items.slice(0, 4).map((c, i) => (
                  <a
                    key={i}
                    href={c.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className={marketStyles.citationCard}
                  >
                    <span className={marketStyles.citationCardTitle}>{c.title || c.url}</span>
                    {c.snippet && (
                      <span className={marketStyles.citationCardSnippet}>
                        {c.snippet.slice(0, 80)}…
                      </span>
                    )}
                  </a>
                ))}
              </div>
            </div>
          ))}

          {/* 电商/社区用户声音（按平台分组） */}
          {Object.entries(socialByPlatform).map(([platform, items]) => (
            <div key={platform} className={marketStyles.citationGroup}>
              <span className={`${marketStyles.citationGroupLabel} ${marketStyles.citationGroupLabelSocial}`}>
                用户声音：{platform}
              </span>
              <div className={marketStyles.citationCards}>
                {items.slice(0, 4).map((c, i) => (
                  <a
                    key={i}
                    href={c.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className={marketStyles.citationCard}
                  >
                    <span className={marketStyles.citationCardTitle}>{c.title || c.url}</span>
                    {c.snippet && (
                      <span className={marketStyles.citationCardSnippet}>
                        {c.snippet.slice(0, 80)}…
                      </span>
                    )}
                  </a>
                ))}
              </div>
            </div>
          ))}

          {/* Jina 爬虫获取的用户评价页 */}
          {reviewCitations.length > 0 && (
            <div className={marketStyles.citationGroup}>
              <span className={`${marketStyles.citationGroupLabel} ${marketStyles.citationGroupLabelReview}`}>
                电商评价页爬取
              </span>
              <div className={marketStyles.citationCards}>
                {reviewCitations.slice(0, 4).map((c, i) => (
                  <a
                    key={i}
                    href={c.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className={marketStyles.citationCard}
                  >
                    <span className={marketStyles.citationCardTitle}>{c.platform?.toUpperCase()} 用户评价</span>
                    {c.snippet && (
                      <span className={marketStyles.citationCardSnippet}>
                        {c.snippet.slice(0, 80)}…
                      </span>
                    )}
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
