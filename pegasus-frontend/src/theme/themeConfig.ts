import type { ThemeConfig } from 'antd'

export const themeConfig: ThemeConfig = {
  token: {
    fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
    fontSize: 14,
    borderRadius: 8,
    colorPrimary: '#1677ff', // Ant blue
    colorSuccess: '#52c41a',
    colorWarning: '#faad14',
    colorError: '#ba1a1a', // Crimson/red
    colorInfo: '#1677ff',
  },
  components: {
    Layout: {
      headerBg: '#ffffff',
      headerPadding: '0 24px',
      bodyBg: '#f9fafb',
      headerHeight: 64,
    },
    Menu: {
      horizontalItemSelectedColor: '#1677ff',
      activeBarHeight: 2,
    },
    Table: {
      headerBg: '#f3f4f6',
      headerColor: '#111827',
      rowHoverBg: '#f9fafb',
    },
  },
}
