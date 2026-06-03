import React from 'react'
import { createRoot } from 'react-dom/client'
import { useRoutes, BrowserRouter } from 'react-router-dom'
import { ConfigProvider } from 'antd'
import { themeConfig } from './theme/themeConfig'
import { routes } from './routes'
import './index.css'

const AppRoutes = () => {
  return useRoutes(routes)
}

const rootElement = document.getElementById('root')
if (!rootElement) {
  throw new Error('Failed to find the root element')
}

createRoot(rootElement).render(
  <React.StrictMode>
    <ConfigProvider theme={themeConfig}>
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
    </ConfigProvider>
  </React.StrictMode>
)
