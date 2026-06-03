import React from 'react'
import { Layout, Menu, Space, Avatar, Badge, Tag, Button } from 'antd'
import { Outlet, Link, useLocation } from 'react-router-dom'
import { Shield, LayoutDashboard, FileCheck, TableProperties, History, Settings, User } from 'lucide-react'

const { Header, Content, Footer } = Layout

export const AppLayout: React.FC = () => {
  const location = useLocation()

  // Determine current active menu key based on pathname
  const getSelectedKey = () => {
    const path = location.pathname
    if (path.startsWith('/dashboard')) return 'dashboard'
    if (path.startsWith('/validation')) return 'validation'
    if (path.startsWith('/configure-mapping')) return 'mapping'
    if (path.startsWith('/history')) return 'history'
    if (path.startsWith('/admin')) return 'admin'
    return 'dashboard'
  }

  const menuItems = [
    {
      key: 'dashboard',
      icon: <LayoutDashboard size={16} />,
      label: <Link to="/dashboard">Dashboard</Link>,
    },
    {
      key: 'validation',
      icon: <FileCheck size={16} />,
      label: <Link to="/validation">System Selector</Link>,
    },
    {
      key: 'mapping',
      icon: <TableProperties size={16} />,
      label: <Link to="/configure-mapping">Configure Mapping</Link>,
    },
    {
      key: 'history',
      icon: <History size={16} />,
      label: <Link to="/history">History Logs</Link>,
    },
    {
      key: 'admin',
      icon: <Settings size={16} />,
      label: <Link to="/admin/workspaces">Admin Control</Link>,
    },
  ]

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header
        style={{
          position: 'sticky',
          top: 0,
          zIndex: 1000,
          width: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          background: '#ffffff',
          borderBottom: '1px solid #e5e7eb',
          boxShadow: '0 1px 2px 0 rgba(0, 0, 0, 0.03)',
        }}
      >
        {/* Left Side: Logo */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div
            style={{
              width: '32px',
              height: '32px',
              borderRadius: '8px',
              background: 'linear-gradient(135deg, #1677ff 0%, #1d4ed8 100%)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#ffffff',
              fontWeight: 'bold',
              fontSize: '18px',
            }}
          >
            P
          </div>
          <span style={{ fontSize: '18px', fontWeight: 700, color: '#111827', letterSpacing: '-0.02em' }}>
            Pegasus
          </span>
        </div>

        {/* Center: Menu */}
        <Menu
          mode="horizontal"
          selectedKeys={[getSelectedKey()]}
          items={menuItems}
          style={{ flex: 1, borderBottom: 'none', justifyContent: 'center', minWidth: '400px' }}
        />

        {/* Right Side: Profile Block */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          {/* Security status badge */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              background: '#f0fdf4',
              border: '1px solid #bbf7d0',
              padding: '4px 10px',
              borderRadius: '20px',
            }}
          >
            <Shield size={14} color="#16a34a" />
            <span style={{ fontSize: '12px', fontWeight: 600, color: '#15803d' }}>
              Access Controls: Enabled
            </span>
          </div>

          {/* User profile details */}
          <Space size={10} style={{ cursor: 'pointer' }}>
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', lineHeight: 1.2 }}>
              <span style={{ fontSize: '13px', fontWeight: 600, color: '#111827' }}>Super User</span>
              <span style={{ fontSize: '11px', color: '#6b7280' }}>sysadmin@pegasus.io</span>
            </div>
            <Badge dot color="#52c41a" offset={[-2, 32]}>
              <Avatar
                size={38}
                style={{ backgroundColor: '#1677ff' }}
                icon={<User size={18} />}
              />
            </Badge>
          </Space>
        </div>
      </Header>

      <Content style={{ padding: '24px', background: '#f9fafb', minHeight: 'calc(100vh - 128px)' }}>
        <div style={{ maxWidth: '1440px', margin: '0 auto' }}>
          <Outlet />
        </div>
      </Content>

      <Footer style={{ textAlign: 'center', background: '#ffffff', borderTop: '1px solid #e5e7eb', padding: '16px 24px' }}>
        <span style={{ fontSize: '13px', color: '#6b7280' }}>
          <strong>Pegasus</strong> · DataAudit Pro Enterprise Administration Panel · v1.2.0
        </span>
      </Footer>
    </Layout>
  )
}
