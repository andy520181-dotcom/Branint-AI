import React, { useState } from 'react';

interface JourneyMapRenderProps {
  data: string[][];
}

// NOTE: 维度行对应的 emoji 图标，按常见顺序匹配
const DIMENSION_ICONS: Record<string, string> = {
  '触点': '📍',
  '情绪': '💭',
  '情感': '💭',
  '关键任务': '✅',
  '任务': '✅',
  '痛点': '😣',
  '机会': '💡',
  '行为': '👤',
};

function getDimensionIcon(name: string): string {
  for (const key of Object.keys(DIMENSION_ICONS)) {
    if (name.includes(key)) return DIMENSION_ICONS[key];
  }
  return '▸';
}

// NOTE: 关键词截断，保留约 12 字以内，超出用省略号
function truncate(text: string, max = 12): string {
  if (!text) return '—';
  const trimmed = text.trim();
  if (trimmed.length <= max) return trimmed;
  return trimmed.slice(0, max) + '…';
}

interface TooltipCellProps {
  text: string;
  isHeader?: boolean;
}

function TooltipCell({ text, isHeader }: TooltipCellProps) {
  const [showTooltip, setShowTooltip] = useState(false);
  const short = truncate(text);
  const needsTooltip = text && text.trim().length > 12;

  return (
    <div
      style={{ position: 'relative', display: 'inline-block', width: '100%' }}
      onMouseEnter={() => needsTooltip && setShowTooltip(true)}
      onMouseLeave={() => setShowTooltip(false)}
    >
      <span style={{
        fontSize: isHeader ? '13px' : '12px',
        lineHeight: '1.4',
        color: isHeader ? '#141413' : '#5e5d59',
        fontWeight: isHeader ? 600 : 400,
        cursor: needsTooltip ? 'default' : 'default',
        display: 'block',
        overflow: 'hidden',
        textOverflow: 'ellipsis',
        whiteSpace: 'nowrap',
      }}>
        {short}
      </span>

      {/* 悬浮全文浮层 */}
      {showTooltip && needsTooltip && (
        <div style={{
          position: 'absolute',
          bottom: 'calc(100% + 6px)',
          left: '50%',
          transform: 'translateX(-50%)',
          zIndex: 200,
          background: '#1f2937',
          color: '#f9fafb',
          borderRadius: '8px',
          padding: '8px 12px',
          fontSize: '12px',
          lineHeight: '1.6',
          maxWidth: '220px',
          whiteSpace: 'pre-wrap',
          wordBreak: 'break-all',
          boxShadow: '0 4px 16px rgba(0,0,0,0.18)',
          pointerEvents: 'none',
        }}>
          {text.trim()}
          {/* 小三角 */}
          <div style={{
            position: 'absolute',
            top: '100%',
            left: '50%',
            transform: 'translateX(-50%)',
            width: 0,
            height: 0,
            borderLeft: '5px solid transparent',
            borderRight: '5px solid transparent',
            borderTop: '5px solid #1f2937',
          }} />
        </div>
      )}
    </div>
  );
}

export function JourneyMapRender({ data }: JourneyMapRenderProps) {
  if (!data || data.length < 2 || data[0].length < 2) return null;

  const phases = data[0].slice(1);
  const dimensionRows = data.slice(1);

  // 列宽: 标签列 80px, 数据列每个 150px
  const colTemplate = `80px repeat(${phases.length}, minmax(150px, 1fr))`;

  return (
    <div style={{
      overflowX: 'auto',
      WebkitOverflowScrolling: 'touch',
      margin: 'var(--space-4) 0',
      borderRadius: '12px',
      border: '1px solid #f0eee6',
    }}>
      <div style={{
        display: 'grid',
        gridTemplateColumns: colTemplate,
        minWidth: `${80 + phases.length * 150}px`,
      }}>

        {/* ── Header Row ── */}
        {/* 顶部左角单元格 */}
        <div style={{
          background: '#ece9e0',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '8px',
          fontWeight: 600,
          fontSize: '12px',
          color: '#6b6a65',
          borderBottom: '1px solid #e8e5da',
          borderRight: '1px solid #e8e5da',
          position: 'sticky',
          left: 0,
          zIndex: 10,
        }}>
          {data[0][0]}
        </div>

        {/* 阶段标题 */}
        {phases.map((phase, i) => (
          <div
            key={`phase-${i}`}
            style={{
              background: '#c96442',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              padding: '8px 10px',
              fontWeight: 600,
              fontSize: '12px',
              color: '#fff',
              borderBottom: '1px solid #b85538',
              borderRight: i < phases.length - 1 ? '1px solid #b85538' : 'none',
              textAlign: 'center',
              whiteSpace: 'nowrap',
            }}
          >
            {phase}
          </div>
        ))}

        {/* ── 数据行 ── */}
        {dimensionRows.map((row, rIndex) => {
          const dimensionName = row[0];
          const rowCells = row.slice(1);
          const icon = getDimensionIcon(dimensionName);
          const isLastRow = rIndex === dimensionRows.length - 1;

          return (
            <React.Fragment key={`row-${rIndex}`}>
              {/* 行标签（固定） */}
              <div style={{
                background: '#f5f3ed',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexDirection: 'column',
                gap: '2px',
                padding: '10px 6px',
                fontWeight: 600,
                fontSize: '11px',
                color: '#5e5d59',
                borderBottom: isLastRow ? 'none' : '1px solid #ece9e0',
                borderRight: '1px solid #e8e5da',
                position: 'sticky',
                left: 0,
                zIndex: 5,
                textAlign: 'center',
              }}>
                <span style={{ fontSize: '14px' }}>{icon}</span>
                <span>{dimensionName}</span>
              </div>

              {/* 数据格 */}
              {phases.map((_, cIndex) => {
                const cellText = rowCells[cIndex] || '';
                return (
                  <div
                    key={`cell-${rIndex}-${cIndex}`}
                    style={{
                      background: '#fafaf8',
                      padding: '10px 12px',
                      borderBottom: isLastRow ? 'none' : '1px solid #ece9e0',
                      borderRight: cIndex < phases.length - 1 ? '1px solid #ece9e0' : 'none',
                      display: 'flex',
                      alignItems: 'center',
                      minHeight: '44px',
                      transition: 'background 0.12s',
                    }}
                    onMouseEnter={e => (e.currentTarget.style.background = '#f0ede6')}
                    onMouseLeave={e => (e.currentTarget.style.background = '#fafaf8')}
                  >
                    <TooltipCell text={cellText} />
                  </div>
                );
              })}
            </React.Fragment>
          );
        })}
      </div>
    </div>
  );
}
