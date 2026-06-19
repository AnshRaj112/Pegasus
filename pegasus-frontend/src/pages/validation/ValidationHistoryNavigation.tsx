import React, { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';

import { useAppDispatch, useAppSelector } from '../../redux/store';
import { ReportService } from '../report/Report.service';

import { validationActions } from './Validation.reducer';

/** Redirects to `/reports/:mappingId/history` after validation is queued or completes. */
export const ValidationHistoryNavigation: React.FC = () => {
  const dispatch = useAppDispatch();
  const navigate = useNavigate();
  const pending = useAppSelector((s) => s.validation.pendingHistoryNavigation);

  useEffect(() => {
    if (!pending) return;
    let cancelled = false;

    void (async () => {
      try {
        const mappingId = await ReportService.getMappingIdForPaths(
          pending.sourcePath,
          pending.targetPath,
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
  }, [pending, navigate, dispatch]);

  return null;
};
