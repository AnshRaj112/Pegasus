import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useAppSelector, useAppDispatch } from '../../../redux/store';
import { historyActions } from '../History.reducer';
import styles from '../History.module.scss';

export const MappingHistoryTable: React.FC = () => {
  const navigate = useNavigate();
  const dispatch = useAppDispatch();
  const { data: logs } = useAppSelector((state) => state.history.mappingLogs);
  const searchQuery = useAppSelector((state) => state.history.searchQuery);

  const filteredLogs = logs.filter(log => 
    log.sourceSchema.toLowerCase().includes(searchQuery.toLowerCase()) || 
    log.targetSchema.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const getStatusBadge = (status: string) => {
    if (status === 'Active') return <span style={{ padding: '2px 8px', borderRadius: '999px', fontSize: '12px', backgroundColor: '#f0fdf4', color: '#15803d', border: '1px solid #bbf7d0', fontWeight: 600 }}>Active</span>;
    if (status === 'Draft') return <span style={{ padding: '2px 8px', borderRadius: '999px', fontSize: '12px', backgroundColor: '#e6f4ff', color: '#0958d9', border: '1px solid #91caff', fontWeight: 600 }}>Draft</span>;
    return <span style={{ padding: '2px 8px', borderRadius: '999px', fontSize: '12px', backgroundColor: '#f1f5f9', color: '#475569', border: '1px solid #cbd5e1', fontWeight: 600 }}>Archived</span>;
  };

  return (
    <div className={styles.historyTableScrollFrame}>
      <table className={styles.antTableLayout}>
        <thead>
          <tr>
            <th style={{ width: '35%' }}>Source Details</th>
            <th style={{ width: '35%' }}>Target Details</th>
            <th style={{ textAlign: 'center', width: '150px' }}>Status/Result</th>
            <th style={{ textAlign: 'right', width: '160px' }}>Actions</th>
          </tr>
        </thead>
        <tbody>
          {filteredLogs.length === 0 ? (
            <tr>
              <td colSpan={4} style={{ textAlign: 'center', padding: '32px', color: '#727786' }}>
                No mapping history records found.
              </td>
            </tr>
          ) : filteredLogs.map(row => (
            <tr key={row.id} className={styles.antTableRow}>
              <td>
                <div className={styles.rowDetailsGroup} style={{ gap: '4px' }}>
                  <span style={{ fontWeight: 600, color: '#1b1b1c' }}>{row.sourceSchema}</span>
                  <span className={styles.rowTruncateCode} title={row.sourcePath}>{row.sourcePath}</span>
                </div>
              </td>
              <td>
                <div className={styles.rowDetailsGroup} style={{ gap: '4px' }}>
                  <span style={{ fontWeight: 600, color: '#1b1b1c' }}>{row.targetSchema}</span>
                  <span className={styles.rowTruncateCode} title={row.targetPath}>{row.targetPath}</span>
                </div>
              </td>
              <td style={{ textAlign: 'center' }}>
                {getStatusBadge(row.status)}
              </td>
              <td style={{ textAlign: 'right' }}>
                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '16px' }}>
                  <button
                    type="button"
                    onClick={() => navigate(`/history/mapping/${row.id}/schema`)}
                    style={{ color: '#0057c2', background: 'none', border: 'none', cursor: 'pointer', fontSize: '14px', fontWeight: 500 }}
                  >
                    View Schema
                  </button>
                  <button 
                    type="button"
                    onClick={() => dispatch(historyActions.deleteMappingLog(row.id))}
                    style={{ color: '#ba1a1a', background: 'none', border: 'none', cursor: 'pointer', fontSize: '14px', fontWeight: 500 }}
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