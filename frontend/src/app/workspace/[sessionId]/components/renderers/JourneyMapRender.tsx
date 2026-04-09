import React from 'react';

interface JourneyMapRenderProps {
  data: string[][]; // 2D array: data[rowIndex][colIndex]
}

export function JourneyMapRender({ data }: JourneyMapRenderProps) {
  if (!data || data.length < 2 || data[0].length < 2) return null;

  // Header row (Top Columns): whatever is on top
  const phases = data[0].slice(1);
  // Dimension rows (Left Rows): whatever is on the left
  const dimensionRows = data.slice(1);

  return (
    <div
      style={{
        overflowX: 'auto',
        WebkitOverflowScrolling: 'touch',
        margin: 'var(--space-4) 0',
        padding: '24px',
        background: '#faf9f5', // Claude Ivory background for the board
        borderRadius: '12px',
        border: '1px solid #f0eee6', // Border Cream
      }}
      className="journey-map-container"
    >
      <div
        style={{
          display: 'grid',
          /* NOTE: 缩小首列宽度，数据列最小宽度设为 0，允许内容自然挤压换行，保证不超出屏幕 */
          gridTemplateColumns: `90px repeat(${phases.length}, minmax(0, 1fr))`,
          gap: '12px 12px',
          width: '100%',
        }}
      >
        {/* === Header Row === */}
        {/* Top-left empty cell (or the word "阶段") */}
        <div
          style={{
            background: '#e8e6dc', // Warm sand for the origin header
            borderRadius: '20px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontWeight: 600,
            fontSize: '13px',
            color: '#141413',
            height: '36px',
          }}
        >
          {data[0][0]}
        </div>

        {/* Phase Headers */}
        {phases.map((phase, i) => (
          <div
            key={`phase-${i}`}
            style={{
              background: '#c96442', // Claude Terracotta CTA color for timeline headers
              borderRadius: '20px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontWeight: 600,
              fontSize: '13px',
              color: '#ffffff',
              height: '36px',
              boxShadow: '0 2px 4px rgba(201, 100, 66, 0.15)',
            }}
          >
            {phase}
          </div>
        ))}

        {/* === Dimension Rows === */}
        {dimensionRows.map((row, rIndex) => {
          const dimensionName = row[0];
          const rowCells = row.slice(1);

          return (
            <React.Fragment key={`row-${rIndex}`}>
              {/* Row Header (Left Y-axis) */}
              <div
                style={{
                  background: '#f0eee6', // Border Cream variant
                  borderRadius: '12px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontWeight: 600,
                  fontSize: '13px',
                  color: '#141413',
                  padding: '12px 8px',
                  textAlign: 'center',
                }}
              >
                {dimensionName}
              </div>

              {/* Data Cells */}
              {phases.map((_, cIndex) => {
                const cellText = rowCells[cIndex] || '';
                return (
                  <div
                    key={`cell-${rIndex}-${cIndex}`}
                    style={{
                      background: '#ffffff',
                      borderRadius: '12px',
                      padding: '12px',
                      fontSize: '12.5px', /* 缩小字号挤出空间 */
                      lineHeight: '1.6',
                      color: '#5e5d59', // Olive Gray
                      border: '1px solid #f0eee6',
                      boxShadow: '0 1px 3px rgba(0,0,0,0.02)',
                      display: 'flex',
                      alignItems: 'center',
                      wordBreak: 'break-word',
                      whiteSpace: 'pre-wrap',
                    }}
                  >
                    {cellText}
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
