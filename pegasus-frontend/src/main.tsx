import { createRoot } from 'react-dom/client'
import { ConfigProvider, theme } from 'antd'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import './index.css'
import App from './App.tsx'
import DetailedReport from './components/DetailedReport.tsx'

const antdTheme = {
  algorithm: theme.defaultAlgorithm,
  token: {
    colorPrimary: '#d83e3e',
    borderRadius: 10,
    colorBgLayout: '#fffdef',
    colorTextBase: '#111827',
    fontFamily: 'Geist, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif',
  },
  components: {
    Button: { controlHeight: 38 },
    Input: { controlHeight: 38 },
  },
}

createRoot(document.getElementById('root')!).render(
  <ConfigProvider theme={antdTheme}>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<App />} />
        <Route path="/report" element={<DetailedReport />} />
      </Routes>
    </BrowserRouter>
  </ConfigProvider>,
)