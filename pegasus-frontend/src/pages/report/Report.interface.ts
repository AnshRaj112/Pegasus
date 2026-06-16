import { type ReactNode } from 'react';

export type TabType = 'Active' | 'Completed' | 'Saved';

export interface ReportBadge {
  type: 'text' | 'icon' | 'box';
  content: ReactNode | string;
}

export interface ReportItem {
  id: string;
  sourceTitle: string;
  sourceSubtitle: string;
  jobTitle: string;
  jobSubtitle: string;
  badges: ReportBadge[];
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