import React, { useRef } from 'react';
import { Modal } from 'antd';
import { DatabaseOutlined, FileTextOutlined } from '@ant-design/icons';

type OverviewJsonPreviewProps = {
  open: boolean;
  sourcePreview: string | null;
  targetPreview: string | null;
  sourceLabel: string;
  targetLabel: string;
  onClose: () => void;
};

const renderPanel = (
  preview: string | null,
  scrollRef: React.RefObject<HTMLDivElement | null>,
  onScroll: (e: React.UIEvent<HTMLDivElement>) => void,
  headerIcon: React.ReactNode,
  headerLabel: string,
  headerTone: 'dark' | 'light',
) => (
  <div
    style={{
      flex: 1,
      display: 'flex',
      flexDirection: 'column',
      backgroundColor: '#fff',
      borderRadius: '12px',
      border: '1px solid #d9d9d9',
      overflow: 'hidden',
      minWidth: 0,
    }}
  >
    <div
      style={{
        backgroundColor: headerTone === 'dark' ? '#234B5F' : '#f0eded',
        padding: '12px 16px',
        display: 'flex',
        alignItems: 'center',
        gap: '8px',
        color: headerTone === 'dark' ? '#fff' : '#1b1b1c',
      }}
    >
      {headerIcon}
      <span style={{ fontSize: '13px', fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {headerLabel}
      </span>
    </div>
    <div
      ref={scrollRef}
      onScroll={onScroll}
      style={{
        overflow: 'auto',
        maxHeight: 'min(52vh, 480px)',
        padding: '16px',
        backgroundColor: '#f8fafc',
      }}
    >
      <pre
        style={{
          margin: 0,
          fontSize: '12px',
          lineHeight: 1.5,
          fontFamily: 'var(--font-mono)',
          color: '#1b1b1c',
          whiteSpace: 'pre-wrap',
          wordBreak: 'break-word',
        }}
      >
        {preview?.trim() || 'No preview available.'}
      </pre>
    </div>
  </div>
);

export const OverviewJsonPreview: React.FC<OverviewJsonPreviewProps> = ({
  open,
  sourcePreview,
  targetPreview,
  sourceLabel,
  targetLabel,
  onClose,
}) => {
  const sourceRef = useRef<HTMLDivElement>(null);
  const targetRef = useRef<HTMLDivElement>(null);

  const handleSourceScroll = (e: React.UIEvent<HTMLDivElement>) => {
    if (targetRef.current) {
      targetRef.current.scrollTop = e.currentTarget.scrollTop;
    }
  };

  const handleTargetScroll = (e: React.UIEvent<HTMLDivElement>) => {
    if (sourceRef.current) {
      sourceRef.current.scrollTop = e.currentTarget.scrollTop;
    }
  };

  return (
    <Modal
      open={open}
      onCancel={onClose}
      footer={null}
      width="min(1200px, 92vw)"
      centered
      destroyOnHidden={false}
      title="JSON preview"
      styles={{ body: { paddingTop: 8 } }}
    >
      <p style={{ margin: '0 0 16px 0', fontSize: '12px', color: '#727786' }}>
        First ~64 KB of each file, pretty-printed. Scroll in either panel to keep both in sync.
      </p>

      <div style={{ display: 'flex', gap: '16px', alignItems: 'stretch' }}>
        {renderPanel(
          sourcePreview,
          sourceRef,
          handleSourceScroll,
          <FileTextOutlined />,
          `Source · ${sourceLabel}`,
          'dark',
        )}
        {renderPanel(
          targetPreview,
          targetRef,
          handleTargetScroll,
          <DatabaseOutlined />,
          `Target · ${targetLabel}`,
          'light',
        )}
      </div>
    </Modal>
  );
};
