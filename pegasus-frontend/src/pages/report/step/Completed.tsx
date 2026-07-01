import React from 'react';
import { HistoryOutlined, FileOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { useAppSelector } from '../../../redux/store';
import { ReportItem, ReportBadge } from '../Report.interface';
import { TruncatedPath } from '../components/TruncatedPath';
import styles from './ReportStep.module.scss';

const resultBoxClass = (content: ReportBadge['content']) => {
  if (content === 'P') return styles.badgeBoxPass;
  if (content === 'F') return styles.badgeBoxFail;
  return styles.badgeBox;
};

const renderBadges = (badges: ReportBadge[]) => badges.map((badge, bIdx) => (
  <React.Fragment key={bIdx}>
    {bIdx > 0 && <span className={styles.badgeSep}>|</span>}
    {badge.type === 'box' ? (
      <span className={resultBoxClass(badge.content)}>{badge.content}</span>
    ) : (
      <span className={styles.badgeContent}>{badge.content}</span>
    )}
  </React.Fragment>
));

export const Completed: React.FC = () => {
  const { data: completedReports, isFetching } = useAppSelector((s) => s.report.completedReports);
  const searchQuery = useAppSelector((s) => s.report.searchQuery);
  const navigate = useNavigate();

  const filtered = completedReports.filter((r: ReportItem) =>
    r.jobTitle.toLowerCase().includes(searchQuery.toLowerCase())
    || r.sourceTitle.toLowerCase().includes(searchQuery.toLowerCase())
    || r.sourcePath.toLowerCase().includes(searchQuery.toLowerCase())
    || r.targetPath.toLowerCase().includes(searchQuery.toLowerCase()),
  );

  if (isFetching) return <div className={styles.empty}>Loading completed reports...</div>;
  if (filtered.length === 0) return <div className={styles.empty}>No completed reports found.</div>;

  return (
    <>
      {filtered.map((report: ReportItem, index: number) => (
        <div
          key={report.id}
          onClick={() => navigate(`/reports/${report.id}/history`)}
          className={`${styles.row} ${index !== filtered.length - 1 ? styles.rowBordered : ''}`}
        >
          <div className={styles.dash}>-</div>

          <div className={styles.column}>
            <div className={styles.titleRow}>
              <FileOutlined className={styles.fileIcon} />
              <span className={styles.sourceTitle}>{report.sourceTitle}</span>
            </div>
            <div className={styles.monoPath}>
              <TruncatedPath path={report.sourcePath} />
            </div>
          </div>

          <div className={styles.dividerCol}>
            <HistoryOutlined className={styles.historyIcon} />
            <div className={styles.vDivider} />
          </div>

          <div className={styles.column}>
            <div className={styles.titleRow}>
              <FileOutlined className={styles.fileIcon} />
              <span className={styles.sourceTitle}>{report.jobTitle}</span>
            </div>
            <div className={styles.monoPath}>
              <TruncatedPath path={report.targetPath} />
            </div>
          </div>

          <div className={styles.badgesCol}>
            <div className={styles.badgePill}>{renderBadges(report.badges)}</div>
          </div>
        </div>
      ))}
    </>
  );
};
