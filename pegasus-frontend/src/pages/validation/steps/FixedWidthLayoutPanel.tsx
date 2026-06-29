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
import styles from './FixedWidthLayoutPanel.module.scss';

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
  <div className={styles.dateEditor}>
    <span className={styles.dateEditorLabel}>{label}</span>
    <select
      value={DATE_FORMAT_OPTIONS.includes(value as (typeof DATE_FORMAT_OPTIONS)[number]) ? value : ''}
      onChange={(e) => {
        if (e.target.value) onChange(e.target.value);
      }}
      className={styles.dateSelect}
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
      className={styles.dateInput}
    />
  </div>
);

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
      <div className={styles.loadingMessage}>
        Detecting fixed-width column layout…
      </div>
    );
  }

  if (error) {
    return (
      <div className={styles.errorBanner}>
        {error}
      </div>
    );
  }

  if (columns.length === 0) {
    return (
      <div className={styles.warningBanner}>
        No fixed-width columns could be inferred from the sample lines.
      </div>
    );
  }

  const comparedCount = columns.filter((c) => c.compare_enabled !== false && c.field_name !== joinColumn).length;

  return (
    <div className={styles.root}>
      <div className={styles.header}>
        <div>
          <h4 className={styles.title}>
            Fixed-width layout
          </h4>
          <p className={styles.subtitle}>
            {columns.length} column(s) detected · {comparedCount} compared · per-side slices and date formats supported
          </p>
        </div>
        {lineWidth != null && lineWidth > 0 && (
          <span className={styles.lineWidth}>
            <ColumnWidthOutlined />
            Line width: <strong>{lineWidth}</strong> chars
          </span>
        )}
      </div>

      <div className={styles.tableWrap}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th className={styles.th} />
              <th className={styles.th}>Field</th>
              <th className={styles.th}>Source slice</th>
              <th className={styles.th}>Target slice</th>
              <th className={styles.th}>Type</th>
              <th className={styles.th}>Source sample</th>
              <th className={styles.th}>Target sample</th>
              <th className={styles.th}>Date formats</th>
              <th className={styles.th}>Actions</th>
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

              const rowClass = isJoin
                ? styles.dataRowJoin
                : isIgnored
                  ? styles.dataRowIgnored
                  : undefined;

              return (
                <React.Fragment key={rowKey}>
                  <tr className={rowClass}>
                    <td className={`${styles.td} ${styles.tdNarrow}`}>
                      <button
                        type="button"
                        onClick={() => toggleExpanded(rowKey)}
                        className={styles.expandBtn}
                        title="Expression transforms"
                      >
                        {isExpanded ? <DownOutlined /> : <RightOutlined />}
                      </button>
                    </td>
                    <td className={styles.td}>
                      <div className={`${styles.fieldName} ${isIgnored ? styles.fieldNameIgnored : ''}`}>{col.field_name}</div>
                      {isJoin && (
                        <span className={styles.joinKeyLabel}>JOIN KEY</span>
                      )}
                      {isIgnored && !isJoin && (
                        <span className={styles.ignoredLabel}>Ignored</span>
                      )}
                    </td>
                    <td className={`${styles.td} ${styles.tdMono}`}>
                      [{col.source_start}, {col.source_end})
                    </td>
                    <td className={`${styles.td} ${styles.tdMono}`}>
                      [{col.target_start}, {col.target_end})
                    </td>
                    <td className={styles.td}>
                      <span className={styles.typeBadge}>
                        {col.field_type}
                      </span>
                    </td>
                    <td className={`${styles.td} ${styles.tdMono} ${styles.tdMonoTruncate}`}>
                      {maskSample(col.source_sample ?? '', Boolean(col.is_sensitive))}
                    </td>
                    <td className={`${styles.td} ${styles.tdMono} ${styles.tdMonoTruncate}`}>
                      {maskSample(col.target_sample ?? '', Boolean(col.is_sensitive))}
                    </td>
                    <td className={styles.td}>
                      {isDate ? (
                        <div className={styles.dateFormats}>
                          <CalendarOutlined className={styles.calendarIcon} />
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
                        <span className={styles.mutedText}>—</span>
                      )}
                    </td>
                    <td className={styles.td}>
                      <div className={styles.actions}>
                        {!isJoin && (
                          <button
                            type="button"
                            onClick={() => updateColumn(index, { compare_enabled: isIgnored })}
                            className={`${styles.iconBtn} ${isIgnored ? styles.iconBtnActive : ''}`}
                            title={isIgnored ? 'Include in compare' : 'Ignore field'}
                          >
                            <StopOutlined />
                          </button>
                        )}
                        <button
                          type="button"
                          onClick={() => updateColumn(index, { is_sensitive: !col.is_sensitive })}
                          className={`${styles.iconBtn} ${col.is_sensitive ? styles.iconBtnDangerActive : ''}`}
                          title="Mask sensitive values in reports"
                        >
                          {col.is_sensitive ? <EyeInvisibleOutlined /> : <EyeOutlined />}
                        </button>
                        {onJoinColumnChange && (
                          <button
                            type="button"
                            onClick={() => onJoinColumnChange(col.field_name)}
                            disabled={isJoin}
                            className={`${styles.joinBtn} ${isJoin ? styles.joinBtnActive : ''}`}
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
                            className={`${styles.orderBtn} ${col.structured_order_sensitive ? styles.orderBtnActive : ''}`}
                          >
                            {col.structured_order_sensitive ? <OrderedListOutlined /> : <UnorderedListOutlined />}
                            Order
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                  {isExpanded && (
                    <tr className={styles.expandedRow}>
                      <td colSpan={9} className={styles.expandedCell}>
                        <div className={styles.expressionGrid}>
                          <div>
                            <div className={styles.expressionLabel}>Source expression (regex)</div>
                            <input
                              type="text"
                              value={col.source_regex_pattern ?? ''}
                              onChange={(e) => updateColumn(index, { source_regex_pattern: e.target.value || null })}
                              placeholder="Pattern e.g. ^0+"
                              className={`${styles.expressionInput} ${styles.expressionInputSpaced}`}
                            />
                            <input
                              type="text"
                              value={col.source_regex_replacement ?? ''}
                              onChange={(e) => updateColumn(index, { source_regex_replacement: e.target.value })}
                              placeholder="Replacement"
                              className={styles.expressionInput}
                            />
                          </div>
                          <div>
                            <div className={styles.expressionLabel}>Target expression (regex)</div>
                            <input
                              type="text"
                              value={col.target_regex_pattern ?? ''}
                              onChange={(e) => updateColumn(index, { target_regex_pattern: e.target.value || null })}
                              placeholder="Pattern"
                              className={`${styles.expressionInput} ${styles.expressionInputSpaced}`}
                            />
                            <input
                              type="text"
                              value={col.target_regex_replacement ?? ''}
                              onChange={(e) => updateColumn(index, { target_regex_replacement: e.target.value })}
                              placeholder="Replacement"
                              className={styles.expressionInput}
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
