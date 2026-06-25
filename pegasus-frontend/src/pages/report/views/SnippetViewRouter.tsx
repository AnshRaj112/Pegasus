import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { Api } from '../../../shared/api/Api';
import { SnippetComparison } from './SnippetComparison';
import { JsonSnippetComparison } from './JsonSnippetComparison';

const isJsonRun = (delimiter?: string | null, comparedColumns?: string[] | null): boolean => {
  if ((delimiter ?? '').trim().toLowerCase() === 'json') return true;
  if (comparedColumns?.length === 1 && comparedColumns[0] === 'document') return true;
  return false;
};

export const SnippetViewRouter: React.FC = () => {
  const { runId } = useParams<{ runId: string }>();
  const [useJsonView, setUseJsonView] = useState<boolean | null>(null);

  useEffect(() => {
    if (!runId) {
      setUseJsonView(false);
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const { data } = await Api.getValidationHistoryRun(runId);
        if (!cancelled) {
          setUseJsonView(isJsonRun(data.delimiter, data.compared_columns));
        }
      } catch {
        if (!cancelled) setUseJsonView(false);
      }
    })();
    return () => { cancelled = true; };
  }, [runId]);

  if (useJsonView === null) {
    return <div style={{ padding: '24px', color: '#64748b' }}>Loading snippet view…</div>;
  }

  return useJsonView ? <JsonSnippetComparison /> : <SnippetComparison />;
};
