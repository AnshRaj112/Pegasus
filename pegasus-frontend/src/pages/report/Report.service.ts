import React from 'react';
import { ClockCircleOutlined, SyncOutlined } from '@ant-design/icons';
import { type ReportItem } from './Report.interface';

// Temporary mock data so you can test the UI immediately
const MOCK_ACTIVE: ReportItem[] = [
  {
    id: '1',
    sourceTitle: 'EMPLOYEES',
    sourceSubtitle: 'EMPLOYEES_1778845600124_PROD',
    jobTitle: 'EMPLOYEES_TEST_FULL',
    jobSubtitle: 'Once on 2026-05-15 18:56',
    badges: [
      { type: 'text', content: '2026-05-15 18:56' },
      { type: 'icon', content: React.createElement(ClockCircleOutlined, { style: { fontSize: '12px' } }) },
      { type: 'box', content: 'F' }
    ]
  }
];

const MOCK_COMPLETED: ReportItem[] = [
  {
    id: '2',
    sourceTitle: 'INVENTORY_SNAPSHOT',
    sourceSubtitle: 'INV_SNAP_889210_DAILY',
    jobTitle: 'DELTA_VALIDATION_STAGING',
    jobSubtitle: 'Every 1 hr(s), starting at 2026-05-29 11:52',
    badges: [
      { type: 'icon', content: React.createElement(SyncOutlined, { style: { fontSize: '12px' } }) },
      { type: 'text', content: '1hr(s)' },
      { type: 'text', content: '2026-05-29 11:52' },
      { type: 'icon', content: React.createElement(ClockCircleOutlined, { style: { fontSize: '12px' } }) },
      { type: 'box', content: 'L' }
    ]
  }
];

export const ReportService = {
  fetchActive: async (): Promise<ReportItem[]> => {
    return new Promise((resolve) => setTimeout(() => resolve(MOCK_ACTIVE), 300));
  },
  fetchCompleted: async (): Promise<ReportItem[]> => {
    return new Promise((resolve) => setTimeout(() => resolve(MOCK_COMPLETED), 300));
  },
  fetchSaved: async (): Promise<ReportItem[]> => {
    return new Promise((resolve) => setTimeout(() => resolve([]), 300));
  }
};