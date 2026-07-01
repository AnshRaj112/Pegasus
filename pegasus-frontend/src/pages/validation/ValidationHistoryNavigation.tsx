import React, { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';

import { useAppDispatch, useAppSelector } from '../../redux/store';
import { ReportService } from '../report/Report.service';

import { validationActions } from './Validation.reducer';

/** Redirects after validation is queued (Reports → Active) or completes (execution history). */
export const ValidationHistoryNavigation: React.FC = () => {
  const dispatch = useAppDispatch();
  const navigate = useNavigate();
  const pendingReports = useAppSelector((s) => s.validation.pendingReportsNavigation);
  const pendingHistory = useAppSelector((s) => s.validation.pendingHistoryNavigation);

  useEffect(() => {
    if (!pendingReports) return;
    navigate('/reports');
    dispatch(validationActions.clearPendingReportsNavigation());
  }, [pendingReports, navigate, dispatch]);

  useEffect(() => {
    if (!pendingHistory) return;
    let cancelled = false;

    void (async () => {
      try {
        const mappingId = await ReportService.getMappingIdForPaths(
          pendingHistory.sourcePath,
          pendingHistory.targetPath,
        );
        if (!cancelled) {
          navigate(`/reports/${mappingId}/history`);
        }
      } finally {
        if (!cancelled) {
          dispatch(validationActions.clearPendingHistoryNavigation());
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [pendingHistory, navigate, dispatch]);

  return null;
};
