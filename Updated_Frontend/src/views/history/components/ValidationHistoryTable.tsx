import React, { useState } from 'react';

export interface ValidationLogItem {
  id: string;
  sourceFile: string;
  sourceUri: string;
  targetTable: string;
  targetUri: string;
  rowCount: string;
  duration: string;
  status: 'Success' | 'Fail' | 'Pass';
}

export const ValidationHistoryTable: React.FC = () => {
  const [activePopoverId, setActivePopoverId] = useState<string | null>(null);
  
  const [logs, setLogs] = useState<ValidationLogItem[]>([
    { id: 'v1', sourceFile: 'production_sales_v2.parquet', sourceUri: 's3://data-warehouse/raw/2024/05/22/sales/sales_v2.parquet', targetTable: 'dim_sales_fact', targetUri: 'snowflake://PROD_DB/TRANSFORMED/PUBLIC/DIM_SALES_FACT', rowCount: '42,109,221 rows', duration: '2m 14s', status: 'Success' },
    { id: 'v2', sourceFile: 'customer_master_full.csv', sourceUri: 'gs://internal-audit/temp/customers_20240520.csv', targetTable: 'CRM_CORE_STAGING', targetUri: 'postgres://prod-cluster:5432/crm/staging/customer_master', rowCount: '1,244,000 rows', duration: '48s', status: 'Fail' },
    { id: 'v3', sourceFile: 'inventory_snapshot.avro', sourceUri: 's3://supply-chain/snapshots/inventory_0521.avro', targetTable: 'STG_INVENTORY', targetUri: 'redshift://analytics-dw/sc_stg/inventory_records', rowCount: '850,200 rows', duration: '1m 05s', status: 'Pass' }
  ]);

  const handleDeleteRecord = (id: string) => {
    setLogs(prev => prev.filter(item => item.id !== id));
    setActivePopoverId(null);
  };

  const getStatusBadge = (status: ValidationLogItem['status']) => {
    if (status === 'Fail') {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-red-100 text-red-700 border border-red-200">
          <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#ba1a1a' }}></span> Fail
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-green-100 text-green-700 border border-green-200">
        <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#22c55e' }}></span> {status === 'Success' ? 'Success' : 'Pass'}
      </span>
    );
  };

  return (
    <div className="historyTableScrollFrame custom-scrollbar">
      <table className="antTableLayout">
        <thead>
          <tr>
            <th style={{ width: '25%' }}>Source Details</th>
            <th style={{ width: '25%' }}>Target Details</th>
            <th>Mapping Counts</th>
            <th style={{ textAlign: 'center', width: '120px' }}>Duration</th>
            <th style={{ textAlign: 'center', width: '120px' }}>Status</th>
            <th style={{ textAlign: 'right', width: '160px' }}>Actions</th>
          </tr>
        </thead>
        <tbody>
          {logs.map(row => (
            <tr key={row.id} className="antTableRow" style={{ borderBottom: '1px solid var(--outline-variant)' }}>
              <td style={{ padding: 'var(--md) var(--gutter)' }}>
                <div className="rowDetailsGroup" style={{ gap: '12px' }}>
                  <span style={{ fontWeight: 600, color: 'var(--on-surface)' }}>{row.sourceFile}</span>
                  <span className="rowTruncateCode" title={row.sourceUri}>{row.sourceUri}</span>
                </div>
              </td>
              <td style={{ padding: 'var(--md) var(--gutter)' }}>
                <div className="rowDetailsGroup" style={{ gap: '12px' }}>
                  <span style={{ fontWeight: 600, color: 'var(--on-surface)' }}>{row.targetTable}</span>
                  <span className="rowTruncateCode" title={row.targetUri}>{row.targetUri}</span>
                </div>
              </td>
              <td style={{ padding: 'var(--md) var(--gutter)' }}>
                <span style={{ background: 'var(--surface-container-highest)', padding: '4px var(--sm)', borderRadius: '4px', fontSize: 'var(--body-sm)', fontFamily: 'var(--font-code-sm)' }}>
                  {row.rowCount}
                </span>
              </td>
              <td style={{ padding: 'var(--md) var(--gutter)', textAlign: 'center' }}>
                <span style={{ color: 'var(--on-surface-variant)', fontFamily: 'var(--font-code-sm)' }}>{row.duration}</span>
              </td>
              <td style={{ padding: 'var(--md) var(--gutter)', textAlign: 'center' }}>
                {getStatusBadge(row.status)}
              </td>
              <td style={{ padding: 'var(--md) var(--gutter)', textAlign: 'right' }}>
                <div style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', gap: 'var(--sm)' }}>
                  <button type="button" style={{ color: 'var(--primary)', background: 'none', border: 'none', cursor: 'pointer', fontFamily: 'var(--font-label-md)', fontSize: 'var(--label-md)' }}>
                    {row.status === 'Fail' ? 'View Errors' : 'View Report'}
                  </button>
                  
                  <div style={{ position: 'relative', display: 'inline-block' }}>
                    <button 
                      type="button"
                      onClick={() => setActivePopoverId(activePopoverId === row.id ? null : row.id)}
                      style={{ color: 'var(--error)', background: 'none', border: 'none', cursor: 'pointer', fontFamily: 'var(--font-label-md)', fontSize: 'var(--label-md)' }}
                    >
                      Delete
                    </button>
                    {activePopoverId === row.id && (
                      <div className="popoverBubbleContainer">
                        <p style={{ margin: '0 0 var(--base) 0', fontSize: 'var(--body-sm)', color: 'var(--on-surface)' }}>
                          Are you sure you want to delete this record?
                        </p>
                        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
                          <button type="button" onClick={() => setActivePopoverId(null)} style={{ fontSize: '12px', padding: '4px var(--base)', border: 'none', background: 'none', cursor: 'pointer', borderRadius: '4px' }} className="paginationNumBtn">
                            Cancel
                          </button>
                          <button type="button" onClick={() => handleDeleteRecord(row.id)} style={{ fontSize: '12px', padding: '4px var(--base)', border: 'none', background: 'var(--error)', color: '#fff', cursor: 'pointer', borderRadius: '4px' }}>
                            Confirm
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};
