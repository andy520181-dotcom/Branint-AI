import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { Components } from 'react-markdown';
import { EChartsRenderer } from './EChartsRenderer';
import { JourneyMapRender } from './JourneyMapRender';
import { BrandHouseRender } from './BrandHouseRender';
import styles from '../WorkspaceFeed.module.css';

// Helper to extract 2D text array from react-markdown rehype ast table node
function extractTableData(node: any): string[][] {
  const data: string[][] = [];
  if (!node || !node.children) return data;

  for (const child of node.children) {
    if (child.tagName === 'thead' || child.tagName === 'tbody') {
      for (const row of child.children) {
        if (row.tagName === 'tr') {
          const rowData: string[] = [];
          for (const cell of row.children) {
            if (cell.tagName === 'th' || cell.tagName === 'td') {
              let cellText = '';
              const extractText = (n: any) => {
                if (n.type === 'text' && n.value) {
                  cellText += n.value;
                }
                if (n.children) {
                  n.children.forEach(extractText);
                }
              };
              extractText(cell);
              rowData.push(cellText.trim());
            }
          }
          if (rowData.length > 0) {
            data.push(rowData);
          }
        }
      }
    }
  }
  return data;
}

export const sharedMarkdownComponents: Components = {
  /**
   * NOTE: 所有 Markdown 表格统一包裹进 .prose-table-wrap 容器，
   * 实现横向滚动（用户旅程地图等宽表格在窄屏下不溢出）
   */
  table(props: any) {
    const { children, node, ...rest } = props;
    
    // 如果是匹配特定格式的表格（如用户旅程地图），使用卡片网格渲染
    if (node) {
      try {
        const tableData = extractTableData(node);
        if (tableData.length > 1 && tableData[0].length > 1 && tableData[0][0] === '阶段') {
          return <JourneyMapRender data={tableData} />;
        }
      } catch (e) {
        console.error("Error extracting table data for Journey Map:", e);
      }
    }

    return (
      <div className="prose-table-wrap">
        <table {...rest}>{children}</table>
      </div>
    );
  },
  code(props: any) {
    const { children, className, node, ...rest } = props;
    const match = /language-(\w+)/.exec(className || '');
    
    let codeStr = '';
    if (typeof children === 'string') {
      codeStr = children;
    } else if (Array.isArray(children)) {
      codeStr = children.join('');
    } else if (children !== undefined && children !== null) {
      codeStr = String(children);
    }
    
    if (match && match[1] === 'echarts') {
      return <EChartsRenderer optionsJsonStr={codeStr.replace(/\n$/, '')} />;
    }
    
    if (match && match[1] === 'jsonbrandhouse') {
      try {
        const data = JSON.parse(codeStr);
        // NOTE: t 由外部通过 makeMarkdownComponents(t) 传入，此处是模块级默认版本（无 t）
        return <BrandHouseRender data={data} />;
      } catch (e) {
        console.error('Brand House JSON parse error:', e);
        // 如果断流中 JSON 生成不完整，降级返回普通的思考中或代码块
      }
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
  /** 可选：传入 t 函数后品牌屋等子组件会使用 i18n 文案；缺省则回退到中文默认值 */
  t?: (key: string) => string;
}

/**
 * 创建携带 t 函数的 Markdown 组件集合。
 * 仅当需要 i18n 支持时调用（如带 t 的 MarkdownRenderer）；
 * MarketRenderer 等继续使用模块级 sharedMarkdownComponents 以保持向后兼容。
 */
export function makeMarkdownComponents(t: (key: string) => string): Components {
  return {
    ...sharedMarkdownComponents,
    code(props: any) {
      const { children, className, node, ...rest } = props;
      const match = /language-(\w+)/.exec(className || '');

      let codeStr = '';
      if (typeof children === 'string') codeStr = children;
      else if (Array.isArray(children)) codeStr = children.join('');
      else if (children != null) codeStr = String(children);

      if (match?.[1] === 'echarts') {
        return <EChartsRenderer optionsJsonStr={codeStr.replace(/\n$/, '')} />;
      }

      if (match?.[1] === 'jsonbrandhouse') {
        try {
          const data = JSON.parse(codeStr);
          return <BrandHouseRender data={data} t={t} />;
        } catch (e) {
          console.error('Brand House JSON parse error:', e);
        }
      }

      return (
        <code {...rest} className={className}>
          {children}
        </code>
      );
    },
  };
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
export function MarkdownRenderer({ output, t }: MarkdownRendererProps) {
  // NOTE: 仅当 t 传入时才创建带 i18n 的组件集合，否则复用模块级常量避免重复对象创建
  const components = t ? makeMarkdownComponents(t) : sharedMarkdownComponents;

  if (!output) {
    return (
      <div className={`${styles.cardOutput} markdown-body`}>
        <span className="prose-empty">—</span>
      </div>
    );
  }

  return (
    <div className={`${styles.cardOutput} markdown-body`}>
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {stripHandoff(output)}
      </ReactMarkdown>
    </div>
  );
}
