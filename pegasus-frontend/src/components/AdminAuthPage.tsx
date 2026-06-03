import React from 'react'
import { Card, Button, message } from 'antd'

interface AdminAuthPageProps {
  onLogin?: (credentials: any) => void
}

export const AdminAuthPage: React.FC<AdminAuthPageProps> = ({ onLogin }) => {
  const handleLogin = () => {
    message.info('Login functionality is now handled by the main app layout')
  }

  return (
    <Card title="Admin Authentication" style={{ maxWidth: '500px', margin: '48px auto' }}>
      <p>Super User authentication is enabled via the app header</p>
      <Button type="primary" onClick={handleLogin}>
        Login
      </Button>
    </Card>
  )
}

export default AdminAuthPage
