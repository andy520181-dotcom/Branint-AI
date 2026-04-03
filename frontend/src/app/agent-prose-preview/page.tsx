'use client';

import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import feedStyles from '@/app/workspace/[sessionId]/components/WorkspaceFeed.module.css';
import { sharedMarkdownComponents } from '@/app/workspace/[sessionId]/components/renderers/MarkdownRenderer';
import styles from './page.module.css';

/**
 * 生成页 Agent Markdown 样式规范预览（设计令牌见 globals.css :root --prose-*）
 * 访问路径：/agent-prose-preview
 */
const SAMPLE_MARKDOWN = `# 一级标题：品牌战略摘要

正文段落使用 \`--prose-body-size\` 与次要文字色，行高统一为 \`--prose-body-line-height\`。

## 二级标题：市场洞察

二级标题带底部分隔线，对应「章节」层级。

### 三级标题：竞品对标

#### 四级标题：细分维度

##### 五级标题：执行要点

###### 六级标题：补充说明

有序列表（一级目录感）：

1. 第一层步骤
2. 第二层展开
   1. 子步骤甲
   2. 子步骤乙
3. 第三层
   - 无序混合
   - **加粗关键词**

无序列表：

- 一级要点
  - 二级要点
    - 三级要点

> 引用块：左侧竖线使用 \`--prose-blockquote-border\`，正文为常规体（非斜体）。

| 维度 | 说明 | 权重 |
|------|------|------|
| 品牌认知 | 目标人群触达 | 高 |
| 差异化 | 相对竞品 | 中 |

行内 \`code\` 与代码块：

\`\`\`ts
const token = "使用 --font-size-md 的 pre code";
\`\`\`

图表（ECharts JSON 代码块；流式未完整时显示占位动画）：

\`\`\`echarts
{"title":{"text":"示例"},"xAxis":{"type":"category","data":["A","B"]},"yAxis":{"type":"value"},"series":[{"type":"bar","data":[12,19]}]}
\`\`\`

---

分隔线以上为规范演示，所有字号/色值来自全局 CSS 变量，勿在组件内写死。
`;

export default function AgentProsePreviewPage() {
  return (
    <div className={styles.page}>
      <div className={styles.intro}>
        <h1>Agent 输出样式规范（效果图）</h1>
        <p>
          本页展示生成页流式 Markdown 的统一层级：一级～六级标题、列表嵌套、表格、引用、代码、图片与 ECharts。
          样式由 <code>globals.css</code> 中 <code>--prose-*</code> 令牌驱动，深色主题随 <code>[data-theme=&quot;dark&quot;]</code> 联动。
        </p>
        <p>
          路由：<code>/agent-prose-preview</code>（仅用于设计验收，可不挂导航入口）。
        </p>
      </div>
      <div className={styles.previewWrap}>
        <div className={`${feedStyles.cardOutput} markdown-body`}>
          <ReactMarkdown remarkPlugins={[remarkGfm]} components={sharedMarkdownComponents}>
            {SAMPLE_MARKDOWN}
          </ReactMarkdown>
        </div>
      </div>
    </div>
  );
}
