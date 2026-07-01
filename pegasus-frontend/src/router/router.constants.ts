export const PATHS = {
  LOGIN: '/login',
  DASHBOARD: '/',
  VALIDATIONS: '/validations',
  VALIDATIONS_WILDCARD: '/validations/*',
  REPORTS: '/reports',
  REPORT_HISTORY: '/reports/:mappingId/history',
  REPORT_SNIPPET: '/reports/:mappingId/history/:runId/snippet',
  ADMIN: '/admin',
  ADMIN_WORKSPACE: '/admin/workspace-management',
  ADMIN_CONFIGURE_STORE: '/admin/configure-store',
  ADMIN_SETTINGS: '/admin/settings',
  PROFILE: '/profile',
  SETTING: '/setting',
} as const;

export type AppPath = (typeof PATHS)[keyof typeof PATHS];
