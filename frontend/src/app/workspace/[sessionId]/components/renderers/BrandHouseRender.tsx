import React from 'react';
import styles from './BrandHouseRender.module.css';

export interface BrandHouseData {
  roof?: {
    vision?: string;
    mission?: string;
    concept?: string;
    values?: string;
  };
  positioning?: string;
  modules?: {
    category: string;
    rows: {
      name: string;
      items: {
        title: string;
        desc: string;
      }[];
    }[];
  }[];
}

interface BrandHouseRenderProps {
  data: BrandHouseData;
}

export function BrandHouseRender({ data }: BrandHouseRenderProps) {
  if (!data) return null;

  return (
    <div className={styles.container}>
      {/* 屋顶层 - 品牌战略 */}
      {data.roof && Object.keys(data.roof).length > 0 && (
        <div className={styles.roof}>
          <div className={styles.roofTitle}>品牌战略</div>
          <div className={styles.roofGrid}>
            {data.roof.vision && (
              <div className={styles.roofItem}>
                <span className={styles.roofItemLabel}>愿景</span>
                <span className={styles.roofItemValue}>{data.roof.vision}</span>
              </div>
            )}
            {data.roof.concept && (
              <div className={styles.roofItem}>
                <span className={styles.roofItemLabel}>理念</span>
                <span className={styles.roofItemValue}>{data.roof.concept}</span>
              </div>
            )}
            {data.roof.mission && (
              <div className={styles.roofItem}>
                <span className={styles.roofItemLabel}>使命</span>
                <span className={styles.roofItemValue}>{data.roof.mission}</span>
              </div>
            )}
            {data.roof.values && (
              <div className={styles.roofItem}>
                <span className={styles.roofItemLabel}>价值观</span>
                <span className={styles.roofItemValue}>{data.roof.values}</span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* 第一行 - 品牌战略定位 (位于主体最上方，贯穿) */}
      {data.positioning && (
        <div className={styles.positioningRow}>
          <div className={styles.positioningLabel}>品牌战略定位</div>
          <div className={styles.positioningValue}>{data.positioning}</div>
        </div>
      )}

      {/* 主体模块容器 */}
      {data.modules && data.modules.length > 0 && (
        <div className={styles.modulesContainer}>
          {data.modules.map((mod, modIdx) => (
            <div key={modIdx} className={styles.module}>
              {/* 左侧垂直向文字标签与边界括号 */}
              <div className={styles.categoryCol}>
                <div className={styles.categoryBracket}></div>
                {/* 仅当提供 category 且不为空时渲染 */}
                {mod.category && <span className={styles.categoryText}>{mod.category}</span>}
              </div>

              {/* 右侧行群 */}
              <div className={styles.rowsContainer}>
                {mod.rows.map((row, rowIdx) => (
                  <div key={rowIdx} className={styles.row}>
                    {/* 左侧强调名称列 */}
                    <div className={styles.rowName}>{row.name}</div>
                    
                    {/* 右侧具体内容格（网格） */}
                    <div className={styles.itemsGrid}>
                      {row.items.map((item, itemIdx) => (
                        <div key={itemIdx} className={styles.itemCell}>
                          <div className={styles.itemTitle}>{item.title}</div>
                          <div className={styles.itemDesc}>{item.desc}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
