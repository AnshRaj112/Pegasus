import React, { useState } from 'react';
import {
  OrderedListOutlined,
  UnorderedListOutlined,
  ColumnWidthOutlined,
  CalendarOutlined,
  StopOutlined,
  EyeOutlined,
  EyeInvisibleOutlined,
  DownOutlined,
  RightOutlined,
} from '@ant-design/icons';

import type { FixedWidthColumnPreview } from '../../../shared/api/Api';
import { DATE_FORMAT_OPTIONS } from '../fixedWidthFormat';

const thStyle: React.CSSProperties = {
  textAlign: 'left',
  padding: '10px 12px',
  fontSize: '11px',
  fontWeight: 700,
  textTransform: 'uppercase',
  color: '#727786',
  borderBottom: '2px solid #e5e2e1',
  backgroundColor: '#f6f3f2',
};

const tdStyle: React.CSSProperties = {
  padding: '10px 12px',
  fontSize: '13px',
  borderBottom: '1px solid #f0eded',
  verticalAlign: 'top',
};

const mono: React.CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: '12px',
};

const truncate = (value: string, max = 48): string => {
  const trimmed = value.trim();
  if (trimmed.length <= max) return trimmed || '—';
  return `${trimmed.slice(0, max)}…`;
};

const maskSample = (value: string, sensitive: boolean): string => {
  const t = value.trim();
  if (!t) return '—';
  return sensitive ? '*'.repeat(Math.min(t.length, 24)) : truncate(t);
};

const DateFormatEditor: React.FC<{
  label: string;
  value: string;
  onChange: (next: string) => void;
}> = ({ label, value, onChange }) => (
  <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', minWidth: '140px' }}>
    <span style={{ fontSize: '10px', fontWeight: 600, color: '#727786', textTransform: 'uppercase' }}>{label}</span>
    <select
      value={DATE_FORMAT_OPTIONS.includes(value as (typeof DATE_FORMAT_OPTIONS)[number]) ? value : ''}
      onChange={(e) => {
        if (e.target.value) onChange(e.target.value);
      }}
      style={{
        padding: '6px 8px',
        borderRadius: '4px',
        border: '1px solid #c1c6d7',
        fontSize: '12px',
        backgroundColor: '#fff',
      }}
    >
      <option value="">Custom…</option>
      {DATE_FORMAT_OPTIONS.map((fmt) => (
        <option key={fmt} value={fmt}>{fmt}</option>
      ))}
    </select>
    <input
      type="text"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder="e.g. DD/MM/YYYY"
      style={{
        padding: '6px 8px',
        borderRadius: '4px',
        border: '1px solid #c1c6d7',
        fontSize: '12px',
        fontFamily: 'var(--font-mono)',
      }}
    />
  </div>
);

const iconBtn = (active: boolean, danger?: boolean): React.CSSProperties => ({
  padding: '4px 6px',
  borderRadius: '4px',
  border: 'none',
  background: active ? (danger ? 'rgba(186, 26, 26, 0.12)' : '#414755') : 'transparent',
  color: active ? (danger ? '#ba1a1a' : '#fff') : '#727786',
  cursor: 'pointer',
  fontSize: '14px',
});

export const FixedWidthLayoutPanel: React.FC<{
  columns: FixedWidthColumnPreview[];
  loading?: boolean;
  error?: string | null;
  joinColumn?: string;
  lineWidth?: number;
  onChange: (columns: FixedWidthColumnPreview[]) => void;
  onJoinColumnChange?: (joinColumn: string) => void;
}> = ({
  columns,
  loading = false,
  error = null,
  joinColumn,
  lineWidth,
  onChange,
  onJoinColumnChange,
}) => {
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});

  const updateColumn = (index: number, patch: Partial<FixedWidthColumnPreview>) => {
    const next = columns.map((col, i) => (i === index ? { ...col, ...patch } : col));
    onChange(next);
  };

  const toggleExpanded = (key: string) => {
    setExpanded((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  if (loading) {
    return (
      <div style={{ padding: '24px', textAlign: 'center', color: '#727786', fontSize: '13px' }}>
        Detecting fixed-width column layout…
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ padding: '16px', borderRadius: '8px', backgroundColor: '#fef2f2', border: '1px solid #fecaca', color: '#ba1a1a', fontSize: '13px' }}>
        {error}
      </div>
    );
  }

  if (columns.length === 0) {
    return (
      <div style={{ padding: '16px', borderRadius: '8px', backgroundColor: '#fffbeb', border: '1px solid #fde68a', color: '#92400e', fontSize: '13px' }}>
        No fixed-width columns could be inferred from the sample lines.
      </div>
    );
  }

  const comparedCount = columns.filter((c) => c.compare_enabled !== false && c.field_name !== joinColumn).length;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px' }}>
        <div>
          <h4 style={{ margin: 0, fontSize: '15px', fontWeight: 700, color: '#1b1b1c' }}>
            Fixed-width layout
          </h4>
          <p style={{ margin: '4px 0 0', fontSize: '12px', color: '#727786' }}>
            {columns.length} column(s) detected · {comparedCount} compared · per-side slices and date formats supported
          </p>
        </div>
        {lineWidth != null && lineWidth > 0 && (
          <span style={{ fontSize: '12px', color: '#414755', display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
            <ColumnWidthOutlined />
            Line width: <strong>{lineWidth}</strong> chars
          </span>
        )}
      </div>

      <div style={{ overflowX: 'auto', border: '1px solid #d9d9d9', borderRadius: '8px' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: '960px' }}>
          <thead>
            <tr>
              <th style={thStyle} />
              <th style={thStyle}>Field</th>
              <th style={thStyle}>Source slice</th>
              <th style={thStyle}>Target slice</th>
              <th style={thStyle}>Type</th>
              <th style={thStyle}>Source sample</th>
              <th style={thStyle}>Target sample</th>
              <th style={thStyle}>Date formats</th>
              <th style={thStyle}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {columns.map((col, index) => {
              const rowKey = `${col.field_name}-${col.source_start}`;
              const isJoin = joinColumn === col.field_name;
              const isIgnored = col.compare_enabled === false;
              const isDate = col.field_type === 'date';
              const isStructured = col.field_type === 'structured';
              const isExpanded = Boolean(expanded[rowKey]);
              const sourceDate = col.source_date_format ?? col.date_format ?? '';
              const targetDate = col.target_date_format ?? col.date_format ?? '';

              return (
                <React.Fragment key={rowKey}>
                  <tr style={{
                    backgroundColor: isJoin ? '#f0f9ff' : isIgnored ? '#fcf9f8' : undefined,
                    opacity: isIgnored ? 0.65 : 1,
                  }}
                  >
                    <td style={{ ...tdStyle, width: '28px' }}>
                      <button
                        type="button"
                        onClick={() => toggleExpanded(rowKey)}
                        style={{ border: 'none', background: 'none', cursor: 'pointer', color: '#727786' }}
                        title="Expression transforms"
                      >
                        {isExpanded ? <DownOutlined /> : <RightOutlined />}
                      </button>
                    </td>
                    <td style={tdStyle}>
                      <div style={{ fontWeight: 600, textDecoration: isIgnored ? 'line-through' : 'none' }}>{col.field_name}</div>
                      {isJoin && (
                        <span style={{ fontSize: '10px', color: '#234B5F', fontWeight: 700 }}>JOIN KEY</span>
                      )}
                      {isIgnored && !isJoin && (
                        <span style={{ fontSize: '10px', color: '#727786' }}>Ignored</span>
                      )}
                    </td>
                    <td style={{ ...tdStyle, ...mono }}>
                      [{col.source_start}, {col.source_end})
                    </td>
                    <td style={{ ...tdStyle, ...mono }}>
                      [{col.target_start}, {col.target_end})
                    </td>
                    <td style={tdStyle}>
                      <span style={{
                        backgroundColor: '#f6f3f2',
                        border: '1px solid #c1c6d7',
                        padding: '2px 8px',
                        borderRadius: '4px',
                        fontSize: '11px',
                        fontWeight: 600,
                        textTransform: 'capitalize',
                      }}
                      >
                        {col.field_type}
                      </span>
                    </td>
                    <td style={{ ...tdStyle, ...mono, maxWidth: '180px' }}>
                      {maskSample(col.source_sample ?? '', Boolean(col.is_sensitive))}
                    </td>
                    <td style={{ ...tdStyle, ...mono, maxWidth: '180px' }}>
                      {maskSample(col.target_sample ?? '', Boolean(col.is_sensitive))}
                    </td>
                    <td style={tdStyle}>
                      {isDate ? (
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', alignItems: 'flex-start' }}>
                          <CalendarOutlined style={{ color: '#234B5F', marginTop: '20px' }} />
                          <DateFormatEditor
                            label="Source"
                            value={sourceDate}
                            onChange={(next) => updateColumn(index, {
                              source_date_format: next || null,
                              date_format: next || null,
                            })}
                          />
                          <DateFormatEditor
                            label="Target"
                            value={targetDate}
                            onChange={(next) => updateColumn(index, {
                              target_date_format: next || null,
                            })}
                          />
                        </div>
                      ) : (
                        <span style={{ color: '#727786' }}>—</span>
                      )}
                    </td>
                    <td style={tdStyle}>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px', alignItems: 'center' }}>
                        {!isJoin && (
                          <button
                            type="button"
                            onClick={() => updateColumn(index, { compare_enabled: isIgnored })}
                            style={iconBtn(isIgnored)}
                            title={isIgnored ? 'Include in compare' : 'Ignore field'}
                          >
                            <StopOutlined />
                          </button>
                        )}
                        <button
                          type="button"
                          onClick={() => updateColumn(index, { is_sensitive: !col.is_sensitive })}
                          style={iconBtn(Boolean(col.is_sensitive), true)}
                          title="Mask sensitive values in reports"
                        >
                          {col.is_sensitive ? <EyeInvisibleOutlined /> : <EyeOutlined />}
                        </button>
                        {onJoinColumnChange && (
                          <button
                            type="button"
                            onClick={() => onJoinColumnChange(col.field_name)}
                            disabled={isJoin}
                            style={{
                              padding: '4px 8px',
                              fontSize: '11px',
                              borderRadius: '4px',
                              border: '1px solid #c1c6d7',
                              backgroundColor: isJoin ? '#e5e2e1' : '#fff',
                              cursor: isJoin ? 'default' : 'pointer',
                            }}
                          >
                            {isJoin ? 'Join' : 'Set join'}
                          </button>
                        )}
                        {isStructured && (
                          <button
                            type="button"
                            onClick={() => updateColumn(index, {
                              structured_order_sensitive: !col.structured_order_sensitive,
                            })}
                            title={col.structured_order_sensitive ? 'Require list/dict order' : 'Ignore element order'}
                            style={{
                              padding: '4px 8px',
                              borderRadius: '4px',
                              border: `1px solid ${col.structured_order_sensitive ? '#234B5F' : '#c1c6d7'}`,
                              backgroundColor: col.structured_order_sensitive ? '#234B5F' : '#fff',
                              color: col.structured_order_sensitive ? '#fff' : '#414755',
                              fontSize: '11px',
                              cursor: 'pointer',
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '4px',
                            }}
                          >
                            {col.structured_order_sensitive ? <OrderedListOutlined /> : <UnorderedListOutlined />}
                            Order
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                  {isExpanded && (
                    <tr style={{ backgroundColor: '#fafafa' }}>
                      <td colSpan={9} style={{ padding: '12px 16px' }}>
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                          <div>
                            <div style={{ fontSize: '11px', fontWeight: 700, color: '#414755', marginBottom: '6px' }}>Source expression (regex)</div>
                            <input
                              type="text"
                              value={col.source_regex_pattern ?? ''}
                              onChange={(e) => updateColumn(index, { source_regex_pattern: e.target.value || null })}
                              placeholder="Pattern e.g. ^0+"
                              style={{ width: '100%', marginBottom: '6px', padding: '8px', fontFamily: 'var(--font-mono)', fontSize: '12px', borderRadius: '4px', border: '1px solid #c1c6d7' }}
                            />
                            <input
                              type="text"
                              value={col.source_regex_replacement ?? ''}
                              onChange={(e) => updateColumn(index, { source_regex_replacement: e.target.value })}
                              placeholder="Replacement"
                              style={{ width: '100%', padding: '8px', fontFamily: 'var(--font-mono)', fontSize: '12px', borderRadius: '4px', border: '1px solid #c1c6d7' }}
                            />
                          </div>
                          <div>
                            <div style={{ fontSize: '11px', fontWeight: 700, color: '#414755', marginBottom: '6px' }}>Target expression (regex)</div>
                            <input
                              type="text"
                              value={col.target_regex_pattern ?? ''}
                              onChange={(e) => updateColumn(index, { target_regex_pattern: e.target.value || null })}
                              placeholder="Pattern"
                              style={{ width: '100%', marginBottom: '6px', padding: '8px', fontFamily: 'var(--font-mono)', fontSize: '12px', borderRadius: '4px', border: '1px solid #c1c6d7' }}
                            />
                            <input
                              type="text"
                              value={col.target_regex_replacement ?? ''}
                              onChange={(e) => updateColumn(index, { target_regex_replacement: e.target.value })}
                              placeholder="Replacement"
                              style={{ width: '100%', padding: '8px', fontFamily: 'var(--font-mono)', fontSize: '12px', borderRadius: '4px', border: '1px solid #c1c6d7' }}
                            />
                          </div>
                        </div>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};
