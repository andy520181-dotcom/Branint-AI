import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import styles from '../WorkspaceFeed.module.css';

export interface MarkdownRendererProps {
  output: string;
}

/**
 * 移除 Agent 输出中的 <handoff>...</handoff> 交接摘要
 */
export function stripHandoff(text: string): string {
  return text.replace(/<handoff>[\s\S]*?<\/handoff>/gi, '').trimEnd();
}

/**
 * 纯 Markdown 渲染器，作为所有 Agent 的通用回退兜底组件
 */
export function MarkdownRenderer({ output }: MarkdownRendererProps) {
  if (!output) {
    return (
      <div className={`${styles.cardOutput} markdown-body`}>
        <span style={{ color: 'var(--text-muted)', fontSize: '13px' }}>—</span>
      </div>
    );
  }

  return (
    <div className={`${styles.cardOutput} markdown-body`}>
      <ReactMarkdown remarkPlugins={[remarkGfm]}>
        {stripHandoff(output)}
      </ReactMarkdown>
    </div>
  );
}
