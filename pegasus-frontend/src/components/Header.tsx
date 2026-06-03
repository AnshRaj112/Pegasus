import React from 'react'
import { Space, Avatar, Badge } from 'antd'
import { User } from 'lucide-react'

interface HeaderProps {
  activeSection?: string
  onSectionChange?: (section: string) => void
}

export const Header: React.FC<HeaderProps> = ({ activeSection = 'dashboard', onSectionChange }) => {
  const navItems = [
    { id: 'dashboard', label: 'Dashboard' },
    { id: 'mapping', label: 'Mapping' },
    { id: 'history', label: 'History' },
  ]

  return (
    <header
      style={{
        position: 'sticky',
        top: 0,
        zIndex: 50,
        background: 'var(--surface-0)',
        borderBottom: '1px solid var(--border-1)',
        padding: '0 16px',
        display: 'flex',
        alignItems: 'center',
        height: '64px',
        gap: '24px',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', minWidth: '200px' }}>
        <div
          style={{
            width: '32px',
            height: '32px',
            borderRadius: '8px',
            background: 'linear-gradient(135deg, #1677ff 0%, #1d4ed8 100%)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#fff',
            fontWeight: 'bold',
            fontSize: '18px',
          }}
        >
          P
        </div>
        <span style={{ fontSize: '18px', fontWeight: 700, color: 'var(--text-1)', letterSpacing: '-0.02em' }}>
          Pegasus
        </span>
      </div>

      <nav style={{ display: 'flex', alignItems: 'center', gap: '2px', flex: 1 }}>
        {navItems.map(({ id, label }) => (
          <button
            key={id}
            onClick={() => onSectionChange?.(id)}
            style={{
              padding: '8px 16px',
              background: activeSection === id ? 'var(--accent-muted)' : 'transparent',
              border: 'none',
              cursor: 'pointer',
              color: activeSection === id ? 'var(--accent)' : 'var(--text-2)',
              fontWeight: activeSection === id ? 600 : 400,
              borderRadius: '4px',
              transition: 'all 0.15s',
            }}
          >
            {label}
          </button>
        ))}
      </nav>

      <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginLeft: 'auto' }}>
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
          <span style={{ fontSize: '12px', fontWeight: 600, color: '#15803d' }}>
            Admin
          </span>
        </div>

        <Space size={10} style={{ cursor: 'pointer' }}>
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', lineHeight: 1.2 }}>
            <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-1)' }}>Admin User</span>
            <span style={{ fontSize: '11px', color: 'var(--text-2)' }}>admin@pegasus.io</span>
          </div>
          <Badge dot color="#52c41a" offset={[-2, 32]}>
            <Avatar size={38} style={{ backgroundColor: '#1677ff' }} icon={<User size={18} />} />
          </Badge>
        </Space>
      </div>
    </header>
  )
}

export default Header
