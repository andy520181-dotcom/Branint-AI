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
  slogan?: string;
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
      {/* 纯屋顶层 - 几何顶帽 */}
      <div className={styles.roof}>
        <div className={styles.roofTitle}>品牌战略</div>
      </div>

      {/* 战略层模块 (包含愿景等顶层属性以及定位) */}
      {(data.roof || data.positioning) && (
        <div className={styles.modulesContainer} style={{ borderBottom: 'none' }}>
          <div className={styles.module}>
            {/* 左侧(现改为左侧渲染具体的行群) */}
            <div className={styles.rowsContainer}>
              {/* 屋顶拆分出来的行 - 愿景、理念、使命、价值观 */}
              {data.roof && Object.keys(data.roof).length > 0 && (
                <div className={styles.roofRowsContainer}>
                  {data.roof.vision && (
                    <div className={styles.roofDetailRow}>
                      <div className={styles.roofDetailLabel}>愿景</div>
                      <div className={styles.roofDetailValue}>{data.roof.vision}</div>
                    </div>
                  )}
                  {data.roof.mission && (
                    <div className={styles.roofDetailRow}>
                      <div className={styles.roofDetailLabel}>使命</div>
                      <div className={styles.roofDetailValue}>{data.roof.mission}</div>
                    </div>
                  )}
                  {data.roof.values && (
                    <div className={styles.roofDetailRow}>
                      <div className={styles.roofDetailLabel}>价值观</div>
                      <div className={styles.roofDetailValue}>{data.roof.values}</div>
                    </div>
                  )}
                </div>
              )}

              {/* 品牌定位 */}
              {data.positioning && (
                <div className={styles.positioningRow}>
                  <div className={styles.positioningLabel}>品牌定位</div>
                  <div className={styles.positioningValue}>{data.positioning}</div>
                </div>
              )}

              {/* 品牌口号 */}
              {data.slogan && (
                <div className={styles.positioningRow}>
                  <div className={styles.positioningLabel}>品牌口号</div>
                  <div className={styles.positioningValue}>{data.slogan}</div>
                </div>
              )}
            </div>

            {/* 原左侧、现移至右侧侧的垂直向文字标签与边界括号 */}
            <div className={styles.categoryCol}>
              <div className={styles.categoryBracket}></div>
              <span className={styles.categoryText}>战略层</span>
            </div>
          </div>
        </div>
      )}

      {/* 主体模块容器 */}
      {data.modules && data.modules.length > 0 && (
        <div className={styles.modulesContainer}>
          {data.modules.map((mod, modIdx) => (
            <div key={modIdx} className={styles.module}>
              {/* 行群优先渲染，放在左边 */}
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

              {/* 左侧变右侧：垂直向文字标签与边界括号 */}
              <div className={styles.categoryCol}>
                <div className={styles.categoryBracket}></div>
                {/* 仅当提供 category 且不为空时渲染 */}
                {mod.category && <span className={styles.categoryText}>{mod.category}</span>}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
