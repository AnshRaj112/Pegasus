import React from 'react';
import { Tooltip } from 'antd';
import { formatDetectionChainDisplay } from './formatDisplayLabel';
import styles from './FormatDetectionChainLabel.module.scss';

type Props = {
  format: string | null | undefined;
  className?: string;
};

/** Renders `TAR → TAR → ZIP → Delimited file`, or `TAR → … → Delimited file` when 5+ layers. */
export const FormatDetectionChainLabel: React.FC<Props> = ({ format, className }) => {
  const { short, middle } = formatDetectionChainDisplay(format);
  const labelClass = className ? `${styles.label} ${className}` : styles.label;

  if (!middle) {
    return <span className={labelClass}>{short}</span>;
  }

  return (
    <Tooltip title={middle}>
      <span className={labelClass}>{short}</span>
    </Tooltip>
  );
};

export const formatDetectionChainTitle = (format: string | null | undefined): string =>
  formatDetectionChainDisplay(format).full;
