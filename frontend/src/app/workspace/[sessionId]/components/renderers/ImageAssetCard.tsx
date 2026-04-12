'use client';

/**
 * ImageAssetCard — 独立图片资产卡片（路径 A）
 *
 * 以独立卡片形式展示生成的品牌视觉资产，
 * 位于美术指导 Agent 气泡下方，与文字策略报告在视觉层级上明确分离。
 * 包含：
 *   - 骨架屏加载态
 *   - 图片网格（1-4 张）
 *   - 下载按钮（将来可扩展：高清放大、去背景、变体）
 */

import styles from './ImageAssetCard.module.css';

interface ImageItem {
  type: string;
  mime: string;
  data_url: string;
}

interface ImageAssetCardProps {
  /** 资产类型（用于展示标题） */
  assetType: 'logo' | 'poster' | 'banner';
  /** 图片列表 */
  images: ImageItem[];
  /** 是否正在生成中（显示骨架屏） */
  isLoading?: boolean;
}

const ASSET_LABELS: Record<string, string> = {
  logo:   'Logo 方案',
  poster: '品牌海报',
  banner: '推广 Banner',
};

export function ImageAssetCard({ assetType, images, isLoading = false }: ImageAssetCardProps) {
  if (!isLoading && images.length === 0) return null;

  const handleDownload = (url: string, index: number) => {
    const a = document.createElement('a');
    a.href = url;
    a.download = `branin-${assetType}-${index + 1}.jpg`;
    a.target = '_blank';
    a.click();
  };

  return (
    <div className={styles.card}>
      {/* 卡片头部 */}
      <div className={styles.header}>
        <div className={styles.headerIcon}>
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <rect x="1" y="1" width="5" height="5" rx="1" fill="currentColor" opacity="0.8"/>
            <rect x="8" y="1" width="5" height="5" rx="1" fill="currentColor" opacity="0.5"/>
            <rect x="1" y="8" width="5" height="5" rx="1" fill="currentColor" opacity="0.5"/>
            <rect x="8" y="8" width="5" height="5" rx="1" fill="currentColor" opacity="0.8"/>
          </svg>
        </div>
        <span className={styles.headerTitle}>品牌视觉资产 · {ASSET_LABELS[assetType] ?? assetType}</span>
        {isLoading && <span className={styles.generatingBadge}>生成中…</span>}
      </div>

      {/* 图片网格 */}
      <div className={styles.grid} data-count={isLoading ? 1 : images.length}>
        {isLoading ? (
          /* 骨架屏 */
          <div className={styles.skeleton}>
            <div className={styles.skeletonInner} />
          </div>
        ) : (
          images.map((img, idx) => (
            <div key={idx} className={styles.imageWrap}>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={img.data_url}
                alt={`${assetType}-${idx + 1}`}
                className={styles.image}
                loading="lazy"
              />
              {/* 悬停操作栏 */}
              <div className={styles.overlay}>
                <button
                  className={styles.overlayBtn}
                  onClick={() => handleDownload(img.data_url, idx)}
                  title="下载原图"
                >
                  <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                    <path d="M7 1v8M7 9l-3-3M7 9l3-3M1 12h12" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                  下载
                </button>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
