import React from 'react';
import { Tooltip } from 'antd';
import { formatDetectionChainDisplay } from './formatDisplayLabel';

type Props = {
  format: string | null | undefined;
  style?: React.CSSProperties;
};

/** Renders `tar → … → csv`; hovering `…` shows the middle path (e.g. `tar → zip`). */
export const FormatDetectionChainLabel: React.FC<Props> = ({ format, style }) => {
  const { short, middle } = formatDetectionChainDisplay(format);

  if (!middle) {
    return <span style={style}>{short}</span>;
  }

  const parts = short.split('…');
  if (parts.length !== 2) {
    return (
      <Tooltip title={middle}>
        <span style={style}>{short}</span>
      </Tooltip>
    );
  }

  return (
    <Tooltip title={middle}>
      <span style={style}>
        {parts[0]}
        <span style={{ cursor: 'help', textDecoration: 'underline dotted', textUnderlineOffset: '3px' }}>…</span>
        {parts[1]}
      </span>
    </Tooltip>
  );
};

export const formatDetectionChainTitle = (format: string | null | undefined): string =>
  formatDetectionChainDisplay(format).full;
