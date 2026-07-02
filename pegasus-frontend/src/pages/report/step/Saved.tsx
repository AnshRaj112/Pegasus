import React, { useEffect, useMemo, useRef, useState } from 'react';
import { HistoryOutlined, PlayCircleOutlined, FileOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { useAppDispatch, useAppSelector } from '../../../redux/store';
import { ReportItem, ReportBadge } from '../Report.interface';
import { validationActions } from '../../validation/Validation.reducer';
import { TruncatedPath } from '../components/TruncatedPath';
import styles from './ReportStep.module.scss';

const ITEMS_PER_PAGE = 10;

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

const ReportSkeleton: React.FC = () => (
  <div className={styles.skeletonList} role="status" aria-live="polite" aria-label="Loading saved mappings">
    <div className={styles.loadingText}>Loading saved mappings...</div>
    {Array.from({ length: 3 }).map((_, index) => (
      <div key={`saved-skeleton-${index}`} className={styles.skeletonRow}>
        <div className={styles.skeletonBlock} />
        <div className={styles.skeletonBlockWide} />
        <div className={styles.skeletonBlockShort} />
      </div>
    ))}
  </div>
);

export const Saved: React.FC = () => {
  const dispatch = useAppDispatch();
  const { data: savedReports, isFetching } = useAppSelector((s) => s.report.savedReports);
  const searchQuery = useAppSelector((s) => s.report.searchQuery);
  const navigate = useNavigate();
  const listRef = useRef<HTMLDivElement | null>(null);
  const [page, setPage] = useState(0);

  const filtered = useMemo(() => savedReports.filter((r: ReportItem) =>
    r.jobTitle.toLowerCase().includes(searchQuery.toLowerCase())
    || r.sourceTitle.toLowerCase().includes(searchQuery.toLowerCase())
    || r.sourcePath.toLowerCase().includes(searchQuery.toLowerCase())
    || r.targetPath.toLowerCase().includes(searchQuery.toLowerCase()),
  ), [savedReports, searchQuery]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / ITEMS_PER_PAGE));
  const currentPage = Math.min(page, totalPages - 1);

  useEffect(() => {
    setPage(0);
  }, [searchQuery, filtered.length]);

  useEffect(() => {
    listRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }, [currentPage]);
  const pagedReports = useMemo(() => filtered.slice(
    currentPage * ITEMS_PER_PAGE,
    (currentPage + 1) * ITEMS_PER_PAGE,
  ), [currentPage, filtered]);

  if (isFetching && filtered.length === 0) return <ReportSkeleton />;
  if (filtered.length === 0) return <div className={styles.empty}>No saved mappings found.</div>;

  return (
    <div ref={listRef} className={styles.listShell}>
      {pagedReports.map((report: ReportItem, index: number) => (
        <div
          key={report.id}
          className={`${styles.row} ${styles.rowStatic} ${index !== pagedReports.length - 1 ? styles.rowBordered : ''}`}
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

      {totalPages > 1 && (
        <div className={styles.paginationRow}>
          <span className={styles.paginationInfo}>
            Page {currentPage + 1} of {totalPages}
          </span>
          <div className={styles.paginationActions}>
            <button
              type="button"
              className={`${styles.paginationBtn} ${currentPage <= 0 ? styles.paginationBtnDisabled : ''}`}
              onClick={() => setPage((value) => Math.max(0, value - 1))}
              disabled={currentPage <= 0}
            >
              Previous
            </button>
            <button
              type="button"
              className={`${styles.paginationBtn} ${currentPage >= totalPages - 1 ? styles.paginationBtnDisabled : ''}`}
              onClick={() => setPage((value) => Math.min(totalPages - 1, value + 1))}
              disabled={currentPage >= totalPages - 1}
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
