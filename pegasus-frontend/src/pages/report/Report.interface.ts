import { ReactNode } from 'react';

import type { MismatchSampleRow, ValidationHistoryDetail } from '../../shared/api/Api';

export type TabType = 'Active' | 'Completed' | 'Saved';

export interface ReportBadge {
  type: 'text' | 'icon' | 'box';
  content: ReactNode | string;
}

export interface ReportItem {
  id: string;
  sourcePath: string;
  targetPath: string;
  sourceTitle: string;
  sourceSubtitle: string;
  jobTitle: string;
  jobSubtitle: string;
  badges: ReportBadge[];
  latestRunId: string | null;
  latestIsMatch: boolean | null;
  /** In-flight validation job (Active tab). */
  jobId?: string | null;
  /** Saved draft run id (Saved tab). */
  draftRunId?: string | null;
}

export interface AsyncListState<T> {
  data: T[];
  isFetching: boolean;
  error: string | null;
}

export interface ReportState {
  activeTab: TabType;
  searchQuery: string;
  activeReports: AsyncListState<ReportItem>;
  completedReports: AsyncListState<ReportItem>;
  savedReports: AsyncListState<ReportItem>;
  historyRunState: {
    runId: string | null;
    data: ValidationHistoryDetail | null;
    isFetching: boolean;
    error: string | null;
  };
  mismatchesState: {
    runId: string | null;
    items: MismatchSampleRow[];
    total: number;
    isFetching: boolean;
    isComplete: boolean;
    progressMessage: string;
    error: string | null;
  };
}
