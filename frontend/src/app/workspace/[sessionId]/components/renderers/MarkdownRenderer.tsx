import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { Components } from 'react-markdown';
import { EChartsRenderer } from './EChartsRenderer';
import styles from '../WorkspaceFeed.module.css';

export const sharedMarkdownComponents: Components = {
  code(props: any) {
    const { children, className, node, ...rest } = props;
    const match = /language-(\w+)/.exec(className || '');
    if (match && match[1] === 'echarts') {
      let codeStr = '';
      if (typeof children === 'string') {
        codeStr = children;
      } else if (Array.isArray(children)) {
        codeStr = children.join('');
      } else if (children !== undefined && children !== null) {
        codeStr = String(children);
      }
      return <EChartsRenderer optionsJsonStr={codeStr.replace(/\n$/, '')} />;
    }
    return (
      <code {...rest} className={className}>
        {children}
      </code>
    );
  },
  img(props: any) {
    const { src, alt, node, ...rest } = props;
    if (!src) return null;
    return (
      <figure className="markdown-figure">
        <img {...rest} src={src} alt={alt ?? ''} className="markdown-img" loading="lazy" decoding="async" />
        {alt ? <figcaption className="markdown-figcaption">{alt}</figcaption> : null}
      </figure>
    );
  },
  video(props: any) {
    const { src, node, ...rest } = props;
    return (
      <figure className="markdown-figure">
        <video {...rest} src={src} className="markdown-video" controls playsInline />
      </figure>
    );
  },
};

export interface MarkdownRendererProps {
  output: string;
}

/**
 * 移除 Agent 输出中的 <handoff>...</handoff> 交接摘要
 * 支持流式输出时未闭合标签的实时隐藏
 */
export function stripHandoff(text: string): string {
  // 1. 首先尝试剥离所有完整的 <handoff>...</handoff> 模块
  let stripped = text.replace(/<handoff>[\s\S]*?<\/handoff>/gi, '');
  // 2. 剥离可能因为处于流式生成中（或大模型粗心）而尚未闭合的 <handoff> 及后续所有内容
  stripped = stripped.replace(/<handoff>[\s\S]*$/i, '');
  return stripped.trimEnd();
}

/**
 * 纯 Markdown 渲染器，作为所有 Agent 的通用回退兜底组件
 */
export function MarkdownRenderer({ output }: MarkdownRendererProps) {
  if (!output) {
    return (
      <div className={`${styles.cardOutput} markdown-body`}>
        <span className="prose-empty">—</span>
      </div>
    );
  }

  return (
    <div className={`${styles.cardOutput} markdown-body`}>
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={sharedMarkdownComponents}>
        {stripHandoff(output)}
      </ReactMarkdown>
    </div>
  );
}
