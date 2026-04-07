'use client';

import type { Dispatch, SetStateAction } from 'react';
import type { HistoryItem } from '@/types';
import styles from './WorkspaceHistorySidebar.module.css';

type TFn = (key: string) => string;

export interface WorkspaceHistorySidebarProps {
  historyOpen: boolean;
  onClose: () => void;
  historyGroups: { label: string; items: HistoryItem[] }[];
  /** 正在拉取历史记录 — 此状态下不显示"暂无会话记录" */
  historyLoading?: boolean;
  sessionId: string;
  resolvedLocale: string;
  historyMenuOpenId: string | null;
  setHistoryMenuOpenId: (id: string | null) => void;
  onNavigateSession: (sessionId: string) => void;
  onRename: (item: HistoryItem) => void;
  onPin: (item: HistoryItem) => void;
  onShare: (item: HistoryItem) => void;
  onDelete: (item: HistoryItem) => void;
  t: TFn;
}

export function WorkspaceHistorySidebar({
  historyOpen,
  onClose,
  historyGroups,
  historyLoading = false,
  sessionId,
  resolvedLocale,
  historyMenuOpenId,
  setHistoryMenuOpenId,
  onNavigateSession,
  onRename,
  onPin,
  onShare,
  onDelete,
  t,
}: WorkspaceHistorySidebarProps) {
  return (
    <>
      {historyOpen && <div className={styles.historyOverlay} onClick={onClose} />}

      <aside className={`${styles.historySidebar} ${historyOpen ? styles.historySidebarOpen : ''}`}>
        <div className={styles.historyHeader}>
          <span className={styles.historyTitle}>{t('workspace.historyTitle')}</span>
          <button type="button" className={styles.historyCloseBtn} onClick={onClose} title={t('workspace.close')}>
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
              <path d="M1 1L13 13M13 1L1 13" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
            </svg>
          </button>
        </div>

        <div className={styles.historyBody}>
          {historyLoading ? (
            /* NOTE: 加载骨架屏 — 避免 API 请求期间闪现「暂无会话记录」 */
            <div className={styles.historySkeletons}>
              {[1, 2, 3].map((i) => (
                <div key={i} className={styles.historySkeleton} />
              ))}
            </div>
          ) : historyGroups.length === 0 ? (
            <p className={styles.historyEmpty}>{t('workspace.historyEmpty')}</p>
          ) : (
            historyGroups.map((group) => (
              <div key={group.label} className={styles.historyGroup}>
                <p className={styles.historyGroupLabel}>{group.label}</p>
                {group.items.map((item, itemIndex) => (
                  <div
                    key={`${group.label}-${itemIndex}-${item.sessionId}`}
                    className={`${styles.historyItemRow} ${item.sessionId === sessionId ? styles.historyItemRowActive : ''}`}
                  >
                    <button
                      type="button"
                      className={styles.historyItemMain}
                      onClick={() => {
                        setHistoryMenuOpenId(null);
                        onClose();
                        if (item.sessionId !== sessionId) {
                          onNavigateSession(item.sessionId);
                        }
                      }}
                    >
                      <span className={styles.historyItemTitle}>{item.title}</span>
                      <span className={styles.historyItemTime}>
                        {new Date(item.createdAt).toLocaleDateString(
                          resolvedLocale === 'en' ? 'en-US' : 'zh-CN',
                          { month: 'numeric', day: 'numeric' },
                        )}
                      </span>
                    </button>
                    <div className={styles.historyMenuRoot} data-history-menu-root>
                      <button
                        type="button"
                        className={`${styles.historyItemMore} ${historyMenuOpenId === item.sessionId ? styles.historyItemMoreOpen : ''}`}
                        aria-expanded={historyMenuOpenId === item.sessionId}
                        aria-haspopup="menu"
                        title={t('workspace.history.more')}
                        onClick={(e) => {
                          e.stopPropagation();
                          setHistoryMenuOpenId(historyMenuOpenId === item.sessionId ? null : item.sessionId);
                        }}
                      >
                        <span className={styles.historyItemMoreDots} aria-hidden>
                          ⋯
                        </span>
                      </button>
                      {historyMenuOpenId === item.sessionId && (
                        <ul className={styles.historyDropdown} role="menu">
                          <li role="none">
                            <button
                              type="button"
                              role="menuitem"
                              className={styles.historyDropdownItem}
                              onClick={() => onRename(item)}
                            >
                              <svg
                                className={styles.historyDropdownIcon}
                                width="16"
                                height="16"
                                viewBox="0 0 24 24"
                                fill="none"
                                stroke="currentColor"
                                strokeWidth="2"
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                aria-hidden
                              >
                                <path d="M12 20h9" />
                                <path d="M16.5 3.5a2.121 2.121 0 013 3L7 19l-4 1 1-4L16.5 3.5z" />
                              </svg>
                              {t('workspace.history.rename')}
                            </button>
                          </li>
                          <li role="none">
                            <button type="button" role="menuitem" className={styles.historyDropdownItem} onClick={() => onPin(item)}>
                              <svg
                                className={styles.historyDropdownIcon}
                                width="16"
                                height="16"
                                viewBox="0 0 24 24"
                                fill="none"
                                stroke="currentColor"
                                strokeWidth="2"
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                aria-hidden
                              >
                                <g transform="rotate(-45 12 12)">
                                  <path d="M12 17v5" />
                                  <path d="M9 10.76a2 2 0 0 1-1.11 1.79l-1.78.9A2 2 0 0 0 5 15.24V16a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-.76a2 2 0 0 0-1.11-1.79l-1.78-.9A2 2 0 0 1 15 10.76V7a1 1 0 0 1 1-1 2 2 0 0 0 0-4H8a2 2 0 0 0 0 4 1 1 0 0 1 1 1z" />
                                </g>
                              </svg>
                              {t('workspace.history.pin')}
                            </button>
                          </li>
                          <li role="none">
                            <button type="button" role="menuitem" className={styles.historyDropdownItem} onClick={() => void onShare(item)}>
                              <svg
                                className={styles.historyDropdownIcon}
                                width="16"
                                height="16"
                                viewBox="0 0 24 24"
                                fill="none"
                                stroke="currentColor"
                                strokeWidth="2"
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                aria-hidden
                              >
                                <circle cx="18" cy="5" r="3" />
                                <circle cx="6" cy="12" r="3" />
                                <circle cx="18" cy="19" r="3" />
                                <path d="M8.59 13.51l6.83 3.98M15.41 6.51l-6.82 3.98" />
                              </svg>
                              {t('workspace.history.share')}
                            </button>
                          </li>
                          <li role="none">
                            <button
                              type="button"
                              role="menuitem"
                              className={`${styles.historyDropdownItem} ${styles.historyDropdownItemDanger}`}
                              onClick={() => onDelete(item)}
                            >
                              <svg className={styles.historyDropdownIcon} width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
                                <path d="M3 6h18M8 6V4a2 2 0 012-2h4a2 2 0 012 2v2M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6M10 11v6M14 11v6" />
                              </svg>
                              {t('workspace.history.delete')}
                            </button>
                          </li>
                        </ul>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            ))
          )}
        </div>
      </aside>
    </>
  );
}
