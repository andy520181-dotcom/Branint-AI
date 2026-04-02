'use client';

import type { RefObject } from 'react';
import styles from './WorkspaceOutlineDock.module.css';
import { truncatePromptOneLine } from '../workspaceUtils';

type TFn = (key: string) => string;

export interface OutlineItem {
  id: string;
  prompt: string;
}

export interface WorkspaceOutlineDockProps {
  outlineDockRef: RefObject<HTMLElement | null>;
  outlineItems: OutlineItem[];
  activeOutlineIndex: number;
  outlinePanelOpen: boolean;
  onMouseEnter: () => void;
  onJump: (id: string) => void;
  t: TFn;
}

export function WorkspaceOutlineDock({
  outlineDockRef,
  outlineItems,
  activeOutlineIndex,
  outlinePanelOpen,
  onMouseEnter,
  onJump,
  t,
}: WorkspaceOutlineDockProps) {
  if (outlineItems.length === 0) return null;

  return (
    <nav ref={outlineDockRef} className={styles.outlineDock} aria-label={t('workspace.outlineNav')} onMouseEnter={onMouseEnter}>
      <div className={styles.outlineMinimap}>
        {outlineItems.map((item, i) => (
          <button
            key={item.id}
            type="button"
            className={styles.outlineDash}
            data-active={activeOutlineIndex === i ? 'true' : undefined}
            onClick={() => onJump(item.id)}
            title={item.prompt}
            aria-label={`${t('workspace.outlineJump')}: ${truncatePromptOneLine(item.prompt, 120)}`}
          />
        ))}
      </div>
      <div className={`${styles.outlinePanelScroll} ${outlinePanelOpen ? styles.outlinePanelScrollOpen : ''}`}>
        {outlineItems.map((item, i) => (
          <button
            key={item.id}
            type="button"
            className={styles.outlineRow}
            data-active={activeOutlineIndex === i ? 'true' : undefined}
            onClick={() => onJump(item.id)}
            title={item.prompt}
            aria-current={activeOutlineIndex === i ? 'location' : undefined}
          >
            <span className={styles.outlineRowText}>{truncatePromptOneLine(item.prompt, 44)}</span>
            <span className={styles.outlineRowMark} data-active={activeOutlineIndex === i ? 'true' : undefined} aria-hidden />
          </button>
        ))}
      </div>
    </nav>
  );
}
