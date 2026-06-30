import React, { useEffect, useMemo } from 'react';
import { useParams } from 'react-router-dom';

import { useAppDispatch, useAppSelector } from '~/redux/store';

import { reportActions } from '../Report.reducer';
import { SnippetComparison } from './SnippetComparison';
import { JsonSnippetComparison } from './JsonSnippetComparison';
import styles from './SnippetViewRouter.module.scss';

const isJsonRun = (delimiter?: string | null, comparedColumns?: string[] | null): boolean => {
  if ((delimiter ?? '').trim().toLowerCase() === 'json') return true;
  if (comparedColumns?.length === 1 && comparedColumns[0] === 'document') return true;
  return false;
};

const SnippetViewRouter: React.FC = () => {
  const { runId } = useParams<{ runId: string }>();
  const dispatch = useAppDispatch();
  const historyRunState = useAppSelector((state) => state.report.historyRunState);

  useEffect(() => {
    if (!runId) return;
    dispatch(reportActions.fetchHistoryRunRequest(runId));
    dispatch(reportActions.fetchMismatchesRequest(runId));
  }, [runId, dispatch]);

  const useJsonView = useMemo(() => {
    if (!runId) return false;
    if (historyRunState.runId !== runId) return null;
    if (historyRunState.isFetching) return null;
    if (historyRunState.error || !historyRunState.data) return false;
    return isJsonRun(historyRunState.data.delimiter, historyRunState.data.compared_columns);
  }, [runId, historyRunState]);

  if (useJsonView === null) {
    if (historyRunState.runId === runId && historyRunState.error) {
      return <div className={styles.loading}>{historyRunState.error}</div>;
    }
    return <div className={styles.loading}>Loading snippet view…</div>;
  }

  const snippetKey = `${runId ?? 'unknown'}-${useJsonView ? 'json' : 'tabular'}`;
  return useJsonView
    ? <JsonSnippetComparison key={snippetKey} />
    : <SnippetComparison key={snippetKey} />;
};

export default SnippetViewRouter;
