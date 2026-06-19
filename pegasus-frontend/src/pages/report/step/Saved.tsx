import React from 'react';
import { TableOutlined, HistoryOutlined, PlayCircleOutlined } from '@ant-design/icons';
import { useAppDispatch, useAppSelector } from '../../../redux/store';
import { type ReportItem, type ReportBadge } from '../Report.interface';
import { useNavigate } from 'react-router-dom';
import { validationActions } from '../../validation/Validation.reducer';

export const Saved: React.FC = () => {
  const dispatch = useAppDispatch();
  const { savedReports, searchQuery, isLoading } = useAppSelector((s) => s.report);
  const navigate = useNavigate();

  const filtered = savedReports.filter((r: ReportItem) =>
    r.jobTitle.toLowerCase().includes(searchQuery.toLowerCase())
    || r.sourceTitle.toLowerCase().includes(searchQuery.toLowerCase()),
  );

  if (isLoading) return <div style={{ padding: '32px', textAlign: 'center', color: '#64748b' }}>Loading saved mappings...</div>;
  if (filtered.length === 0) return <div style={{ padding: '32px', textAlign: 'center', color: '#64748b' }}>No saved mappings found.</div>;

  return (
    <>
      {filtered.map((report: ReportItem, index: number) => (
        <div key={report.id} style={{ display: 'flex', alignItems: 'center', gap: '16px', padding: '16px 24px', borderBottom: index !== filtered.length - 1 ? '1px solid #f1f5f9' : 'none', backgroundColor: '#fff' }}>
          <div onClick={() => navigate(`/reports/${report.id}/history`)} style={{ flex: 1, display: 'flex', alignItems: 'center', gap: '16px', cursor: 'pointer' }} onMouseEnter={(e) => { e.currentTarget.style.opacity = '0.85'; }} onMouseLeave={(e) => { e.currentTarget.style.opacity = '1'; }}>
            <div style={{ color: '#94a3b8', fontSize: '14px', width: '16px' }}>-</div>

            <div style={{ flex: 1, minWidth: '200px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                <TableOutlined style={{ color: '#64748b', fontSize: '16px' }} />
                <span style={{ fontWeight: 600, color: '#1b1b1c', fontSize: '13px', textTransform: 'uppercase', letterSpacing: '0.02em' }}>{report.sourceTitle}</span>
              </div>
              <div style={{ color: '#64748b', fontSize: '12px', fontFamily: 'var(--font-mono)' }}>{report.sourceSubtitle}</div>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', height: '40px', padding: '0 16px' }}>
              <HistoryOutlined style={{ color: '#64748b' }} />
              <div style={{ marginLeft: '16px', height: '100%', width: '1px', backgroundColor: '#f1f5f9' }} />
            </div>

            <div style={{ flex: 1, minWidth: '200px' }}>
              <div style={{ color: '#1b1b1c', fontSize: '13px', fontWeight: 500, marginBottom: '4px' }}>{report.jobTitle}</div>
              <div style={{ color: '#64748b', fontSize: '12px' }}>{report.jobSubtitle}</div>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', minWidth: '280px' }}>
              <div style={{ display: 'flex', alignItems: 'center', border: '1px solid rgba(0, 87, 194, 0.3)', borderRadius: '999px', padding: '2px 8px', color: 'var(--primary)', fontSize: '11px', fontFamily: 'var(--font-mono)' }}>
                {report.badges.map((badge: ReportBadge, bIdx: number) => (
                  <React.Fragment key={bIdx}>
                    {bIdx > 0 && <span style={{ margin: '0 6px', opacity: 0.4 }}>|</span>}
                    {badge.type === 'box' ? <span style={{ border: '1px solid rgba(0, 87, 194, 0.4)', borderRadius: '4px', padding: '0 4px', fontWeight: 700 }}>{badge.content}</span> : <span style={{ display: 'flex', alignItems: 'center' }}>{badge.content}</span>}
                  </React.Fragment>
                ))}
              </div>
            </div>
          </div>
          {report.draftRunId && (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                dispatch(validationActions.runValidationFromHistoryRequest(report.draftRunId!));
              }}
              style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '6px 12px', borderRadius: '6px', border: '1px solid #c1c6d7', background: '#fff', cursor: 'pointer', fontSize: '13px', fontWeight: 500 }}
            >
              <PlayCircleOutlined /> Run
            </button>
          )}
        </div>
      ))}
    </>
  );
};
