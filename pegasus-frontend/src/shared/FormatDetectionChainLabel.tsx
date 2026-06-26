import React from 'react';
import { Tooltip } from 'antd';
import { formatDetectionChainDisplay } from './formatDisplayLabel';

type Props = {
  format: string | null | undefined;
  style?: React.CSSProperties;
};

/** Renders `TAR → TAR → ZIP → Delimited file`, or `TAR → … → Delimited file` when 5+ layers. */
export const FormatDetectionChainLabel: React.FC<Props> = ({ format, style }) => {
  const { short, middle } = formatDetectionChainDisplay(format);

  if (!middle) {
    return <span style={style}>{short}</span>;
  }

  return (
    <Tooltip title={middle}>
      <span style={style}>{short}</span>
    </Tooltip>
  );
};

export const formatDetectionChainTitle = (format: string | null | undefined): string =>
  formatDetectionChainDisplay(format).full;
