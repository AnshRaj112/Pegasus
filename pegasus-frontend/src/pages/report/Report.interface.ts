import { type ReactNode } from 'react';

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

export interface ReportState {
  activeTab: TabType;
  searchQuery: string;
  activeReports: ReportItem[];
  completedReports: ReportItem[];
  savedReports: ReportItem[];
  isLoading: boolean;
  error: string | null;
}