import React from 'react';
import { HistoryOutlined, PlayCircleOutlined, FileOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { useAppDispatch, useAppSelector } from '../../../redux/store';
import { ReportItem, ReportBadge } from '../Report.interface';
import { validationActions } from '../../validation/Validation.reducer';
import { TruncatedPath } from '../components/TruncatedPath';
import styles from './ReportStep.module.scss';

const renderBadges = (badges: ReportBadge[], draftTooltip?: string) => badges.map((badge, bIdx) => (
  <React.Fragment key={bIdx}>
    {bIdx > 0 && <span className={styles.badgeSep}>|</span>}
    {badge.type === 'box' ? (
      <span className={styles.badgeBox}>{badge.content}</span>
    ) : badge.type === 'icon' ? (
      <span className={styles.draftBadge} title={draftTooltip}>
        {badge.content}
      </span>
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
    || r.sourceTitle.toLowerCase().includes(searchQuery.toLowerCase())
    || r.sourcePath.toLowerCase().includes(searchQuery.toLowerCase())
    || r.targetPath.toLowerCase().includes(searchQuery.toLowerCase()),
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
                <FileOutlined className={styles.fileIcon} />
                <span className={styles.sourceTitle} title={report.sourcePath}>
                  {report.sourceTitle}
                </span>
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
              <div className={styles.jobTitle} title={report.targetPath}>
                {report.jobTitle}
              </div>
              <div className={styles.monoPath}>
                <TruncatedPath path={report.targetPath} />
              </div>
            </div>

            <div className={styles.badgesCol}>
              <div className={styles.badgePill1}>{renderBadges(report.badges, report.jobSubtitle)}</div>
            </div>
          </div>
          {report.draftRunId && (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                dispatch(validationActions.runValidationFromHistoryRequest({
                  runId: report.draftRunId!,
                  sourcePath: report.sourcePath,
                  targetPath: report.targetPath,
                  sourceTitle: report.sourceTitle,
                  targetTitle: report.jobTitle,
                }));
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
