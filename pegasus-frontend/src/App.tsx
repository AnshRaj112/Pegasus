import { useEffect, useMemo, useState } from 'react'
import { Avatar, Button, Layout, Menu, Spin, Typography } from 'antd'
import type { MenuProps } from 'antd'
import MappingWizard from './components/mapping/MappingWizard'
import History from './components/History'
import Dashboard from './components/Dashboard'
import AdminCloudConnections from './components/AdminCloudConnections'
import AdminAuthPage from './components/AdminAuthPage'
import { adminLogout, fetchAdminMe } from './api/adminAuth'
import { Compass, History as HistoryIcon, LayoutDashboard, Settings, ShieldCheck } from 'lucide-react'

const { Sider, Content } = Layout

type SectionKey = 'dashboard' | 'mapping' | 'history' | 'admin'

function App() {
  const [activeSection, setActiveSection] = useState<SectionKey>('dashboard')
  const [initialMappingData, setInitialMappingData] = useState<any>(null)
  const [authChecked, setAuthChecked] = useState(false)
  const [adminUser, setAdminUser] = useState<any>(null)

  useEffect(() => {
    fetchAdminMe()
      .then((user) => setAdminUser(user))
      .catch(() => setAdminUser(null))
      .finally(() => setAuthChecked(true))
  }, [])

  const handleLoadMapping = (data: any) => {
    setInitialMappingData(data)
    setActiveSection('mapping')
  }

  const handleSectionChange = (section: SectionKey) => {
    if (section !== 'mapping') setInitialMappingData(null)
    setActiveSection(section)
  }

  async function handleLogout() {
    try {
      await adminLogout()
    } catch {
      // ignore logout errors
    }
    setAdminUser(null)
    setAuthChecked(true)
  }

  const menuItems: MenuProps['items'] = useMemo(() => [
    { key: 'dashboard', icon: <LayoutDashboard size={16} />, label: 'Dashboard' },
    { key: 'mapping', icon: <Compass size={16} />, label: 'Mapping' },
    { key: 'history', icon: <HistoryIcon size={16} />, label: 'History' },
    { key: 'admin', icon: <Settings size={16} />, label: 'Admin' },
  ], [])

  if (!authChecked) {
    return (
      <div style={{ minHeight: '100vh', display: 'grid', placeItems: 'center', background: 'linear-gradient(135deg, #fffdef 0%, #f1f1f1 100%)' }}>
        <Spin size="large" />
      </div>
    )
  }

  if (!adminUser) {
    return <AdminAuthPage onAuthenticated={(user: any) => { setAdminUser(user); setAuthChecked(true) }} />
  }

  return (
    <Layout style={{ minHeight: '100vh', background: 'linear-gradient(135deg, #fffdef 0%, #f1f1f1 100%)' }}>
      <Sider width={280} style={{ background: 'rgba(255,255,255,0.72)', backdropFilter: 'blur(14px)', borderRight: '1px solid rgba(255,255,255,0.75)' }}>
        <div style={{ padding: 24, borderBottom: '1px solid rgba(0,0,0,0.06)', display: 'flex', alignItems: 'center', gap: 12 }}>
          <Avatar size={40} icon={<ShieldCheck size={18} />} style={{ background: '#d83e3e' }} />
          <div style={{ minWidth: 0 }}>
            <Typography.Title level={4} style={{ margin: 0 }}>Pegasus</Typography.Title>
            <Typography.Text type="secondary">Validation workspace</Typography.Text>
          </div>
        </div>

        <Menu
          mode="inline"
          selectedKeys={[activeSection]}
          items={menuItems}
          onClick={({ key }) => handleSectionChange(key as SectionKey)}
          style={{ borderInlineEnd: 'none', background: 'transparent', padding: 12 }}
        />

        <div style={{ padding: 20, borderTop: '1px solid rgba(0,0,0,0.06)', background: 'rgba(255,255,255,0.55)', display: 'flex', alignItems: 'center', gap: 12 }}>
          <Avatar src="./photo.jpg" size={40} />
          <div style={{ minWidth: 0, flex: 1 }}>
            <Typography.Text strong style={{ display: 'block' }}>Super User</Typography.Text>
            <Typography.Text type="secondary" ellipsis>{adminUser?.email || 'Admin'}</Typography.Text>
          </div>
          <Button type="text" onClick={handleLogout}>Logout</Button>
        </div>
      </Sider>

      <Layout>
        <Content style={{ padding: 32, overflow: 'auto' }}>
          {activeSection === 'mapping' && (
            <MappingWizard
              initialMappingData={initialMappingData}
              onResetInitialData={() => setInitialMappingData(null)}
            />
          )}
          {activeSection === 'history' && <History onLoadMapping={handleLoadMapping} />}
          {activeSection === 'dashboard' && <Dashboard />}
          {activeSection === 'admin' && <AdminCloudConnections />}
        </Content>
      </Layout>
    </Layout>
  )
}

export default App