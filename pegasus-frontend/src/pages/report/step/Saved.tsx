import React from 'react';
import { TableOutlined, HistoryOutlined, PlayCircleOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { useAppDispatch, useAppSelector } from '../../../redux/store';
import { ReportItem, ReportBadge } from '../Report.interface';
import { validationActions } from '../../validation/Validation.reducer';
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

export const Saved: React.FC = () => {
  const dispatch = useAppDispatch();
  const { data: savedReports, isFetching } = useAppSelector((s) => s.report.savedReports);
  const searchQuery = useAppSelector((s) => s.report.searchQuery);
  const navigate = useNavigate();

  const filtered = savedReports.filter((r: ReportItem) =>
    r.jobTitle.toLowerCase().includes(searchQuery.toLowerCase())
    || r.sourceTitle.toLowerCase().includes(searchQuery.toLowerCase()),
  );

  if (isFetching) return <div className={styles.empty}>Loading saved mappings...</div>;
  if (filtered.length === 0) return <div className={styles.empty}>No saved mappings found.</div>;

  return (
    <>
      {filtered.map((report: ReportItem, index: number) => (
        <div
          key={report.id}
          className={`${styles.row} ${styles.rowStatic} ${index !== filtered.length - 1 ? styles.rowBordered : ''}`}
        >
          <div
            onClick={() => navigate(`/reports/${report.id}/history`)}
            className={styles.rowInner}
          >
            <div className={styles.dash}>-</div>

            <div className={styles.column}>
              <div className={styles.titleRow}>
                <TableOutlined className={styles.fileIcon} />
                <span className={styles.sourceTitle}>{report.sourceTitle}</span>
              </div>
              <div className={styles.monoPath}>{report.sourceSubtitle}</div>
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
          {report.draftRunId && (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                dispatch(validationActions.runValidationFromHistoryRequest(report.draftRunId!));
              }}
              className={styles.runBtn}
            >
              <PlayCircleOutlined /> Run
            </button>
          )}
        </div>
      ))}
    </>
  );
};
