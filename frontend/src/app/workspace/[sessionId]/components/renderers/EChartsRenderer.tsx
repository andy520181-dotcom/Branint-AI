import React, { useMemo } from 'react';
import dynamic from 'next/dynamic';

// NOTE: 动态加载 echarts-for-react，避免 SSR 时的尺寸计算报错或拖慢加载速度
const ReactECharts = dynamic(() => import('echarts-for-react'), { ssr: false });

export interface EChartsRendererProps {
  optionsJsonStr: string;
}

export function EChartsRenderer({ optionsJsonStr }: EChartsRendererProps) {
  const options = useMemo(() => {
    if (!optionsJsonStr || optionsJsonStr.trim() === '' || optionsJsonStr === 'undefined') {
      return null;
    }

    try {
      const parsed = JSON.parse(optionsJsonStr);

      return {
        ...parsed,
        textStyle: {
          fontFamily: 'var(--font-sans)',
        },
        backgroundColor: 'transparent',
        tooltip: parsed.tooltip || {
          trigger: 'axis',
        },
      };
    } catch {
      return null;
    }
  }, [optionsJsonStr]);

  if (!options) {
    return (
      <div className="prose-chart-placeholder">
        <span className="prose-chart-placeholderSpinner" aria-hidden />
        <span>图表数据正在生成中…</span>
      </div>
    );
  }

  return (
    <div className="prose-chart-wrap">
      <ReactECharts
        option={options}
        style={{ height: '100%', minHeight: 'var(--prose-chart-min-height)', width: '100%' }}
        opts={{ renderer: 'svg' }}
      />
    </div>
  );
}
