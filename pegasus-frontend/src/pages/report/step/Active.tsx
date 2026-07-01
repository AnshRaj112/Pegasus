import React from 'react';
import { HistoryOutlined, FileOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { useAppSelector } from '../../../redux/store';
import { ReportItem, ReportBadge } from '../Report.interface';
import { TruncatedPath } from '../components/TruncatedPath';
import styles from './ReportStep.module.scss';

const renderBadges = (badges: ReportBadge[]) => badges.map((badge, bIdx) => (
  <React.Fragment key={bIdx}>
    {bIdx > 0 && <span className={styles.badgeSep}>|</span>}
    {badge.type === 'box' ? (
      <span className={styles.badgeBox}>{badge.content}</span>
    ) : (
      <span className={styles.badgeContent}>{badge.content}</span>
    )}
  </React.Fragment>
));

export const Active: React.FC = () => {
  const { data: activeReports, isFetching } = useAppSelector((s) => s.report.activeReports);
  const searchQuery = useAppSelector((s) => s.report.searchQuery);
  const navigate = useNavigate();

  const filtered = activeReports.filter((r: ReportItem) =>
    r.jobTitle.toLowerCase().includes(searchQuery.toLowerCase())
    || r.sourceTitle.toLowerCase().includes(searchQuery.toLowerCase()),
  );

  if (isFetching && filtered.length === 0) return <div className={styles.empty}>Loading active reports...</div>;
  if (filtered.length === 0) return <div className={styles.empty}>No active reports found.</div>;

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
              <TruncatedPath path={report.sourceSubtitle} />
            </div>
          </div>

          <div className={styles.dividerCol}>
            <HistoryOutlined className={styles.historyIcon} />
            <div className={styles.vDivider} />
          </div>

          <div className={styles.column}>
            <div className={styles.jobTitle}>{report.jobTitle}</div>
            <div className={styles.jobSubtitle}>{report.jobSubtitle}</div>
          </div>

          <div className={styles.badgesCol}>
            <div className={styles.badgePill}>{renderBadges(report.badges)}</div>
          </div>
        </div>
      ))}
    </>
  );
};
