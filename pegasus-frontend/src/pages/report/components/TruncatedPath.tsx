import React from 'react';

import styles from './TruncatedPath.module.scss';

type TruncatedPathProps = {
  path: string;
  className?: string;
  prefix?: string;
};

export const TruncatedPath: React.FC<TruncatedPathProps> = ({ path, className, prefix }) => {
  if (!path) return null;

  const pathNode = (
    <span className={`${styles.path} ${className ?? ''}`.trim()}>
      {path}
    </span>
  );

  const content = prefix ? (
    <span className={styles.labelRow}>
      <span className={styles.prefix}>{prefix}</span>
      <span className={`${styles.wrap} ${styles.labelPath}`}>{pathNode}</span>
    </span>
  ) : (
    <span className={styles.wrap}>{pathNode}</span>
  );

  return (
    <span className={styles.tooltipWrap} title={path}>
      {content}
    </span>
  );
};
