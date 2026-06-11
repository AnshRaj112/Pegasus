import React from 'react';
import type { LucideIcon } from 'lucide-react';

interface MetricCardProps {
  // Upgraded icon property to a clean Lucide Component constructor type
  Icon: LucideIcon;
  iconColor: string;
  label: string;
  value: string;
  subtext: string;
  subtextColor?: string;
  isSpinning?: boolean;
}

export const MetricCard: React.FC<MetricCardProps> = ({
  Icon,
  iconColor,
  label,
  value,
  subtext,
  subtextColor = 'var(--on-surface-variant)',
  isSpinning = false
}) => {
  return (
    <div style={{
      background: 'var(--surface)',
      border: '1px solid var(--surface-variant)',
      padding: 'var(--md)',
      borderRadius: 'var(--lg)',
      display: 'flex',
      flexDirection: 'column',
      justifyContent: 'space-between',
      transition: 'all 0.2s ease',
      boxShadow: '0 2px 8px rgba(0,0,0,0.02)'
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--xs)', color: 'var(--on-surface-variant)' }}>
        <Icon 
          size={18} 
          style={{ color: iconColor }} 
          className={isSpinning ? "icon-spin-loop" : ""} 
        />
        <span style={{ fontFamily: 'var(--font-label-md)', fontSize: 'var(--label-md)', fontWeight: 500, marginLeft: '4px' }}>
          {label}
        </span>
      </div>
      <div style={{ marginTop: 'var(--base)' }}>
        <span style={{ fontFamily: 'var(--font-h2)', fontSize: 'var(--h2)', fontWeight: 600, color: 'var(--on-surface)' }}>
          {value}
        </span>
        <div style={{ fontFamily: 'var(--font-body-sm)', fontSize: 'var(--body-sm)', fontWeight: 500, color: subtextColor }}>
          {subtext}
        </div>
      </div>
    </div>
  );
};
