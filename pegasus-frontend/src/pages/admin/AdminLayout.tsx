import React from 'react'
import { Layout, Menu } from 'antd'
import { Outlet, useLocation, Link } from 'react-router-dom'
import { Building2, Database } from 'lucide-react'

const { Sider, Content } = Layout

export default function AdminLayout() {
  const location = useLocation()

  const getSelectedKey = () => {
    if (location.pathname.includes('/workspaces')) return 'workspaces'
    if (location.pathname.includes('/store')) return 'store'
    return 'workspaces'
  }

  const menuItems = [
    {
      key: 'workspaces',
      icon: <Building2 size={16} />,
      label: <Link to="/admin/workspaces">Workspace Management</Link>,
    },
    {
      key: 'store',
      icon: <Database size={16} />,
      label: <Link to="/admin/store">Configure Storage</Link>,
    },
  ]

  return (
    <Layout style={{ minHeight: '100%' }}>
      <Sider width={250} theme="light" style={{ background: '#ffffff', borderRight: '1px solid #e5e7eb' }}>
        <Menu
          mode="inline"
          selectedKeys={[getSelectedKey()]}
          items={menuItems}
          style={{ border: 'none' }}
        />
      </Sider>
      <Content style={{ padding: '24px', background: '#f9fafb' }}>
        <Outlet />
      </Content>
    </Layout>
  )
}
