import React, { useRef } from 'react';
import { Modal } from 'antd';
import { DatabaseOutlined, FileTextOutlined } from '@ant-design/icons';
import styles from './OverviewArchivePreview.module.scss';

type OverviewArchivePreviewProps = {
  open: boolean;
  sourceEntries: string[];
  targetEntries: string[];
  sourceLabel: string;
  targetLabel: string;
  onClose: () => void;
};

const renderPanel = (
  entries: string[],
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
      {entries.length === 0 ? (
        <p className={styles.emptyText}>No archive entries listed.</p>
      ) : (
        <ul className={styles.entryList}>
          {entries.map((entry) => (
            <li key={entry} className={styles.entryItem}>{entry}</li>
          ))}
        </ul>
      )}
    </div>
  </div>
);

export const OverviewArchivePreview: React.FC<OverviewArchivePreviewProps> = ({
  open,
  sourceEntries,
  targetEntries,
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
      title="Archive preview"
      classNames={{ body: styles.modalBody }}
    >
      <p className={styles.description}>
        Sample archive member paths from each container (metadata only — no decompression).
      </p>

      <div className={styles.panelsRow}>
        {renderPanel(
          sourceEntries,
          sourceRef,
          handleSourceScroll,
          <FileTextOutlined />,
          `Source · ${sourceLabel}`,
          'dark',
        )}
        {renderPanel(
          targetEntries,
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
