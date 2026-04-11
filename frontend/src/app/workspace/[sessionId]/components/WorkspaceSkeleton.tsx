import styles from './WorkspaceSkeleton.module.css';

export function WorkspaceSkeleton() {
  return (
    <div className={styles.skeletonContainer}>
      {/* 虚拟的用户气泡骨架 */}
      <div className={styles.userMsgRow}>
        <div className={styles.userBubble}>
          <div className={`${styles.userBubbleInner} ${styles.placeholder} ${styles.pulse}`} />
        </div>
        <div className={`${styles.userAvatarWrap} ${styles.placeholder} ${styles.pulse}`} />
      </div>

      {/* 虚拟的 Agent 气泡骨架 */}
      <div className={styles.feedItem}>
        <div className={styles.feedLeft}>
          <div className={`${styles.feedAvatar} ${styles.placeholder} ${styles.pulse}`} />
          <div className={`${styles.feedAgentName} ${styles.placeholder} ${styles.pulse}`} />
          <div className={`${styles.feedAgentChar} ${styles.placeholder} ${styles.pulse}`} />
        </div>

        <div className={styles.feedBubbleWrap}>
          <div className={`${styles.feedBubble} ${styles.pulse}`}>
            <div className={`${styles.line} ${styles.line1} ${styles.placeholder}`} />
            <div className={`${styles.line} ${styles.line2} ${styles.placeholder}`} />
            <div className={`${styles.line} ${styles.line3} ${styles.placeholder}`} />
          </div>
        </div>
      </div>
    </div>
  );
}
