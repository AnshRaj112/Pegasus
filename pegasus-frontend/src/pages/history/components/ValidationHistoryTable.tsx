import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAppSelector, useAppDispatch } from '../../../redux/store';
import { historyActions } from '../History.reducer';
import styles from '../History.module.scss';

export const ValidationHistoryTable: React.FC = () => {
  const navigate = useNavigate();
  const dispatch = useAppDispatch();
  const [activePopoverId, setActivePopoverId] = useState<string | null>(null);
  
  const { data: logs } = useAppSelector((state) => state.history.validationLogs);
  const searchQuery = useAppSelector((state) => state.history.searchQuery);

  const filteredLogs = logs.filter(log => 
    log.sourceFile.toLowerCase().includes(searchQuery.toLowerCase()) || 
    log.targetTable.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const handleDeleteRecord = (id: string) => {
    dispatch(historyActions.deleteValidationLog(id));
    setActivePopoverId(null);
  };

  const getStatusBadge = (status: string) => {
    if (status === 'Fail') {
      return (
        <span style={{ padding: '2px 8px', borderRadius: '999px', fontSize: '12px', backgroundColor: '#fff1f0', color: '#cf1322', border: '1px solid #ffa39e', display: 'inline-flex', alignItems: 'center', gap: '6px', fontWeight: 600 }}>
          <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#cf1322' }}></span> Fail
        </span>
      );
    }
    return (
      <span style={{ padding: '2px 8px', borderRadius: '999px', fontSize: '12px', backgroundColor: '#f6ffed', color: '#389e0d', border: '1px solid #b7eb8f', display: 'inline-flex', alignItems: 'center', gap: '6px', fontWeight: 600 }}>
        <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#389e0d' }}></span> {status === 'Success' ? 'Success' : 'Pass'}
      </span>
    );
  };

  return (
    <div className={styles.historyTableScrollFrame}>
      <table className={styles.antTableLayout}>
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
          {filteredLogs.length === 0 ? (
            <tr>
              <td colSpan={6} style={{ textAlign: 'center', padding: '32px', color: '#727786' }}>
                No validation history records found.
              </td>
            </tr>
          ) : filteredLogs.map(row => (
            <tr key={row.id} className={styles.antTableRow}>
              <td>
                <div className={styles.rowDetailsGroup} style={{ gap: '4px' }}>
                  <span style={{ fontWeight: 600, color: '#1b1b1c' }}>{row.sourceFile}</span>
                  <span className={styles.rowTruncateCode} title={row.sourceUri}>{row.sourceUri}</span>
                </div>
              </td>
              <td>
                <div className={styles.rowDetailsGroup} style={{ gap: '4px' }}>
                  <span style={{ fontWeight: 600, color: '#1b1b1c' }}>{row.targetTable}</span>
                  <span className={styles.rowTruncateCode} title={row.targetUri}>{row.targetUri}</span>
                </div>
              </td>
              <td>
                <span style={{ background: '#f0eded', padding: '4px 8px', borderRadius: '4px', fontSize: '12px', fontFamily: 'var(--font-mono)' }}>
                  {row.rowCount}
                </span>
              </td>
              <td style={{ textAlign: 'center' }}>
                <span style={{ color: '#414755', fontFamily: 'var(--font-mono)', fontSize: '12px' }}>{row.duration}</span>
              </td>
              <td style={{ textAlign: 'center' }}>
                {getStatusBadge(row.status)}
              </td>
              <td style={{ textAlign: 'right' }}>
                <div style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', gap: '16px' }}>
                  <button 
                    type="button" 
                    onClick={() => navigate(`/validation/report/${row.id}`)}
                    style={{ color: '#0057c2', background: 'none', border: 'none', cursor: 'pointer', fontSize: '14px', fontWeight: 500 }}
                  >
                    {row.status === 'Fail' ? 'View Errors' : 'View Report'}
                  </button>
                  
                  <div style={{ position: 'relative', display: 'inline-block' }}>
                    <button 
                      type="button"
                      onClick={() => setActivePopoverId(activePopoverId === row.id ? null : row.id)}
                      style={{ color: '#ba1a1a', background: 'none', border: 'none', cursor: 'pointer', fontSize: '14px', fontWeight: 500 }}
                    >
                      Delete
                    </button>
                    {activePopoverId === row.id && (
                      <div className={styles.popoverBubbleContainer}>
                        <p style={{ margin: '0 0 8px 0', fontSize: '12px', color: '#1b1b1c', textAlign: 'left' }}>
                          Are you sure you want to delete this record?
                        </p>
                        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
                          <button type="button" onClick={() => setActivePopoverId(null)} style={{ fontSize: '12px', padding: '4px 8px', border: '1px solid #d9d9d9', background: '#fff', cursor: 'pointer', borderRadius: '4px' }}>
                            Cancel
                          </button>
                          <button type="button" onClick={() => handleDeleteRecord(row.id)} style={{ fontSize: '12px', padding: '4px 8px', border: 'none', background: '#ba1a1a', color: '#fff', cursor: 'pointer', borderRadius: '4px' }}>
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