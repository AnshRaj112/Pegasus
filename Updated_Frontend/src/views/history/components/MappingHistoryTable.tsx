import React, { useState } from 'react';

export interface MappingLogItem {
  id: string;
  sourceSchema: string;
  sourcePath: string;
  targetSchema: string;
  targetPath: string;
  status: 'Active' | 'Draft' | 'Archived';
}

export const MappingHistoryTable: React.FC = () => {
  const [logs, setLogs] = useState<MappingLogItem[]>([
    { id: 'm1', sourceSchema: 'Legacy_Orders_Schema', sourcePath: 'mysql://legacy-orders/schema_v1_2', targetSchema: 'Modern_Unified_Orders', targetPath: 'snowflake://UNIFIED/SCHEMAS/ORDERS_CORE', status: 'Active' },
    { id: 'm2', sourceSchema: 'External_API_Payload_v4', sourcePath: 'json://api-gateway/docs/v4/users.json', targetSchema: 'USER_PROFILE_TRANSFORM', targetPath: 'bigquery://prod-data/identity/users_v4', status: 'Draft' },
    { id: 'm3', sourceSchema: 'Deprecated_Customer_Feed', sourcePath: 'ftp://legacy-reports/customer_v1.csv', targetSchema: 'ARCHIVED_CUSTOMERS', targetPath: 's3://archive-storage/2023/customers/', status: 'Archived' }
  ]);

  const getStatusBadge = (status: MappingLogItem['status']) => {
    switch (status) {
      case 'Active':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-green-100 text-green-700 border border-green-200">
            Active
          </span>
        );
      case 'Draft':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-blue-100 text-blue-700 border border-blue-200">
            Draft
          </span>
        );
      case 'Archived':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-gray-100 text-gray-700 border border-gray-200">
            Archived
          </span>
        );
    }
  };

  return (
    <div className="historyTableScrollFrame custom-scrollbar">
      <table className="antTableLayout">
        <thead>
          <tr>
            <th style={{ width: '35%' }}>Source Details</th>
            <th style={{ width: '35%' }}>Target Details</th>
            <th style={{ textAlign: 'center', width: '150px' }}>Status/Result</th>
            <th style={{ textAlign: 'right', width: '160px' }}>Actions</th>
          </tr>
        </thead>
        <tbody>
          {logs.map(row => (
            <tr key={row.id} className="antTableRow" style={{ borderBottom: '1px solid var(--outline-variant)' }}>
              <td style={{ padding: 'var(--md) var(--gutter)' }}>
                <div className="rowDetailsGroup" style={{ gap: '12px' }}>
                  <span style={{ fontWeight: 600, color: 'var(--on-surface)' }}>{row.sourceSchema}</span>
                  <span className="rowTruncateCode" title={row.sourcePath}>{row.sourcePath}</span>
                </div>
              </td>
              <td style={{ padding: 'var(--md) var(--gutter)' }}>
                <div className="rowDetailsGroup" style={{ gap: '12px' }}>
                  <span style={{ fontWeight: 600, color: 'var(--on-surface)' }}>{row.targetSchema}</span>
                  <span className="rowTruncateCode" title={row.targetPath}>{row.targetPath}</span>
                </div>
              </td>
              <td style={{ padding: 'var(--md) var(--gutter)', textAlign: 'center' }}>
                {getStatusBadge(row.status)}
              </td>
              <td style={{ padding: 'var(--md) var(--gutter)', textAlign: 'right' }}>
                <div style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', gap: 'var(--sm)' }}>
                  <button type="button" style={{ color: 'var(--primary)', background: 'none', border: 'none', cursor: 'pointer', fontFamily: 'var(--font-label-md)', fontSize: 'var(--label-md)' }}>
                    View Schema
                  </button>
                  <button 
                    type="button"
                    onClick={() => setLogs(prev => prev.filter(item => item.id !== row.id))}
                    style={{ color: 'var(--error)', background: 'none', border: 'none', cursor: 'pointer', fontFamily: 'var(--font-label-md)', fontSize: 'var(--label-md)' }}
                  >
                    Delete
                  </button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};
