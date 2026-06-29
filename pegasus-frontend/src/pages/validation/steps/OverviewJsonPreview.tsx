import React, { useRef } from 'react';
import { Modal } from 'antd';
import { DatabaseOutlined, FileTextOutlined } from '@ant-design/icons';
import styles from './OverviewJsonPreview.module.scss';

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
  <div className={styles.panel}>
    <div className={`${styles.panelHeader} ${headerTone === 'dark' ? styles.panelHeaderDark : styles.panelHeaderLight}`}>
      {headerIcon}
      <span className={styles.panelHeaderLabel}>
        {headerLabel}
      </span>
    </div>
    <div
      ref={scrollRef}
      onScroll={onScroll}
      className={styles.panelBody}
    >
      <pre className={styles.jsonPre}>
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
      classNames={{ body: styles.modalBody }}
    >
      <p className={styles.description}>
        First ~64 KB of each file, pretty-printed. Scroll in either panel to keep both in sync.
      </p>

      <div className={styles.panelsRow}>
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
