import React, { useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { stripHandoff } from './MarkdownRenderer';
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
}

/**
 * 解析市场研究报告末尾的 <market_citations> 数据块
 * 返回干净的 Markdown 内容 + 结构化来源列表
 */
function parseMarketOutput(raw: string): { content: string; citations: SearchCitation[] } {
  const citationsMatch = raw.match(/<market_citations>([\s\S]*?)<\/market_citations>/);
  const content = raw.replace(/<market_citations>[\s\S]*?<\/market_citations>/, '').trim();
  
  let citations: SearchCitation[] = [];
  if (citationsMatch) {
    try {
      citations = JSON.parse(citationsMatch[1]);
    } catch {
      // 解析失败则不展示引用
    }
  }
  return { content, citations };
}

/**
 * 市场研究 Agent（Wacksman）专属渲染器
 * 在标准 Markdown 基础上增加：
 * - 搜索来源引用卡片（按市场数据 / 竞品情报分类）
 * - 联网检索运行态（等待期展示"正在联网检索..."）
 */
export function MarketRenderer({ output, isRunning }: MarketRendererProps) {
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
        <div className={marketStyles.searchingState}>
          <div className={marketStyles.searchSpinner} />
          <span className={marketStyles.searchingText}>Wacksman 正在联网检索市场数据…</span>
        </div>
        <div className={marketStyles.searchingHint}>
          中型检索模式：市场宏观数据 + 竞品情报，约需 20-40 秒
        </div>
      </div>
    );
  }

  return (
    <div className={`${styles.cardOutput} markdown-body`}>
      {content && (
        <ReactMarkdown remarkPlugins={[remarkGfm]}>
          {stripHandoff(content)}
        </ReactMarkdown>
      )}

      {/* 来源引用卡片区 */}
      {citations.length > 0 && (
        <div className={marketStyles.citationsSection}>
          <div className={marketStyles.citationsDivider} />
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
