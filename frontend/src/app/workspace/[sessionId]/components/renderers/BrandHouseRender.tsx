import React from 'react';
import styles from './BrandHouseRender.module.css';

export interface BrandHouseData {
  /**
   * NOTE: 可选的明确品牌名字段（后端 handoff 段注入）。
   * 缺省时由 extractBrandName 在 modules.items 中自动搜索。
   */
  brandName?: string;
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
  t?: (key: string) => string;
}

/**
 * 去除字符串末尾的中文句号或英文句点（单个）。
 * NOTE: 只去掉最末一个标点，不影响正文中的句号。
 */
function stripTrailingPeriod(text: string): string {
  return text ? text.replace(/[。.]+$/, '') : text;
}

/**
 * 从 BrandHouseData 中推断品牌名。
 * 优先级：brandName 字段 → modules items 中标题含「品牌名」的项 → undefined
 */
function extractBrandName(data: BrandHouseData): string | undefined {
  if (data.brandName) return data.brandName;
  if (!data.modules) return undefined;
  const BRAND_NAME_KEYS = ['品牌名', '品牌名称', 'Brand Name', '推荐品牌名'];
  for (const mod of data.modules) {
    for (const row of mod.rows) {
      if (!row.items) continue;
      for (const item of row.items) {
        if (BRAND_NAME_KEYS.some(k => item.title?.includes(k)) && item.desc) {
          return item.desc;
        }
      }
    }
  }
  return undefined;
}

export function BrandHouseRender({ data, t }: BrandHouseRenderProps) {
  if (!data) return null;

  // 兼容 t 缺省的情况（如历史快照直接渲染而没有传 t 函数）
  const label = (key: string, fallback: string) => t?.(key) ?? fallback;

  // 兼容逻辑：如果数据中没有顶层的 slogan，但 items 里面有"品牌口号"，则把他提出来。
  // NOTE: 用 i18n key 匹配，但同时保留对中文字面量的兼容——后端输出的 title 字段依然是中文。
  const sloganExtractKey = label('brandHouse.slogan.extractKey', '品牌口号');
  let extractedSlogan = data.slogan;
  if (!extractedSlogan && data.modules) {
    for (const mod of data.modules) {
      for (const row of mod.rows) {
        if (!row.items) continue;
        const sloganItem = row.items.find(item => item.title === sloganExtractKey);
        if (sloganItem) {
          extractedSlogan = sloganItem.desc;
          break;
        }
      }
      if (extractedSlogan) break;
    }
  }

  // NOTE: 品牌名优先从 data.brandName 取，fallback 到 modules items 自动搜索
  const brandName = extractBrandName(data);
  // 是否为"暂定"品牌名（无 brandName 字段，仅靠 AI 推荐提取）
  const isBrandNameProvisional = !data.brandName && !!brandName;

  return (
    <div className={styles.container}>
      {/* 纯屋顶层 - 几何顶帽，标题改为品牌名；若无品牌名则回退到"品牌战略" */}
      <div className={styles.roof}>
        {brandName ? (
          <>
            <div className={styles.roofTitle}>{brandName}</div>
            {isBrandNameProvisional && (
              <div className={styles.roofSubtitle}>暂定</div>
            )}
          </>
        ) : (
          <div className={styles.roofTitle}>{label('brandHouse.roof.title', '品牌战略')}</div>
        )}
      </div>

      {/* 战略层模块 (包含愿景等顶层属性以及定位) */}
      {(data.roof || data.positioning) && (
        <div className={styles.modulesContainer} style={{ borderBottom: 'none' }}>
          <div className={styles.module}>
            <div className={styles.rowsContainer}>
              {/* 屋顶拆分出来的行 - 愿景、理念、使命、价值观 */}
              {data.roof && Object.keys(data.roof).length > 0 && (
                <div className={styles.roofRowsContainer}>
                  {data.roof.vision && (
                    <div className={styles.roofDetailRow}>
                      <div className={styles.roofDetailLabel}>{label('brandHouse.field.vision', '愿景')}</div>
                      <div className={styles.roofDetailValue}>{stripTrailingPeriod(data.roof.vision)}</div>
                    </div>
                  )}
                  {data.roof.mission && (
                    <div className={styles.roofDetailRow}>
                      <div className={styles.roofDetailLabel}>{label('brandHouse.field.mission', '使命')}</div>
                      <div className={styles.roofDetailValue}>{stripTrailingPeriod(data.roof.mission)}</div>
                    </div>
                  )}
                  {data.roof.values && (
                    <div className={styles.roofDetailRow}>
                      <div className={styles.roofDetailLabel}>{label('brandHouse.field.values', '价值观')}</div>
                      <div className={styles.roofDetailValue}>{stripTrailingPeriod(data.roof.values)}</div>
                    </div>
                  )}
                </div>
              )}

              {/* 品牌定位 */}
              {data.positioning && (
                <div className={styles.positioningRow}>
                  <div className={styles.positioningLabel}>{label('brandHouse.field.positioning', '品牌定位')}</div>
                  <div className={styles.positioningValue}>{stripTrailingPeriod(data.positioning)}</div>
                </div>
              )}

              {/* 品牌口号 */}
              {extractedSlogan && (
                <div className={styles.positioningRow}>
                  <div className={styles.positioningLabel}>{label('brandHouse.field.slogan', '品牌口号')}</div>
                  <div className={styles.positioningValue}>{stripTrailingPeriod(extractedSlogan)}</div>
                </div>
              )}
            </div>

            {/* 垂直向文字标签与边界括号 */}
            <div className={styles.categoryCol}>
              <div className={styles.categoryBracket}></div>
              <span className={styles.categoryText}>{label('brandHouse.layer.strategy', '战略层')}</span>
            </div>
          </div>
        </div>
      )}

      {/* 主体模块容器 */}
      {data.modules && data.modules.length > 0 && (
        <div className={styles.modulesContainer}>
          {data.modules.map((mod, modIdx) => {
            // NOTE: 过滤掉遗留的"商业模式"行，保持品牌屋结构干净
            const validRows = mod.rows.filter(row => row.name !== '商业模式');
            if (validRows.length === 0) return null;

            return (
              <div key={modIdx} className={styles.module}>
                {/* 行群优先渲染，放在左边 */}
                <div className={styles.rowsContainer}>
                  {validRows.map((row, rowIdx) => {
                    // NOTE: 过滤掉已提升到顶层的"品牌口号"项，避免重复展示
                    const validItems = row.items.filter(item => item.title !== sloganExtractKey);
                    if (validItems.length === 0) return null;

                    return (
                      <div key={rowIdx} className={styles.row}>
                        {/* 左侧强调名称列 */}
                        <div className={styles.rowName}>{row.name}</div>

                        {/* 右侧具体内容格（网格） */}
                        <div className={styles.itemsGrid}>
                          {validItems.map((item, itemIdx) => (
                            <div key={itemIdx} className={styles.itemCell}>
                              <div className={styles.itemTitle}>{item.title}</div>
                              <div className={styles.itemDesc}>{item.desc}</div>
                            </div>
                          ))}
                        </div>
                      </div>
                    );
                  })}
                </div>

                {/* 垂直向文字标签与边界括号 */}
                <div className={styles.categoryCol}>
                  <div className={styles.categoryBracket}></div>
                  {mod.category && <span className={styles.categoryText}>{mod.category}</span>}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
