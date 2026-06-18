import React from 'react';
import {
  PlusOutlined, TeamOutlined, DatabaseOutlined, HddOutlined,
  EditOutlined, DeleteOutlined, LeftOutlined, RightOutlined, BulbOutlined
} from '@ant-design/icons';

import { useAppSelector, useAppDispatch } from '../../../redux/store';
import { adminActions } from '../Admin.reducer';
import styles from '../Admin.module.scss';

export const WorkspaceMgmtSubView: React.FC = () => {
  const dispatch = useAppDispatch();
  const workspaces = useAppSelector((state) => state.admin.workspaces.data);

  const handleDeleteWorkspace = (id: string) => {
    dispatch(adminActions.deleteWorkspace(id));
  };

  const getStatusBadge = (status: string) => {
    if (status === 'Active') return <span style={{ padding: '2px 8px', borderRadius: '999px', fontSize: '12px', backgroundColor: '#f0fdf4', color: '#15803d', border: '1px solid #bbf7d0', display: 'inline-flex', alignItems: 'center', gap: '6px' }}><span style={{ width: '6px', height: '6px', borderRadius: '50%', backgroundColor: '#16a34a' }} /> Active</span>;
    if (status === 'Restricted') return <span style={{ padding: '2px 8px', borderRadius: '999px', fontSize: '12px', backgroundColor: '#fffbeb', color: '#b45309', border: '1px solid #fde68a', display: 'inline-flex', alignItems: 'center', gap: '6px' }}><span style={{ width: '6px', height: '6px', borderRadius: '50%', backgroundColor: '#d97706' }} /> Restricted</span>;
    return <span style={{ padding: '2px 8px', borderRadius: '999px', fontSize: '12px', backgroundColor: '#f1f5f9', color: '#475569', border: '1px solid #cbd5e1', display: 'inline-flex', alignItems: 'center', gap: '6px' }}><span style={{ width: '6px', height: '6px', borderRadius: '50%', backgroundColor: '#64748b' }} /> Archived</span>;
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '32px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h1 style={{ fontSize: '30px', fontWeight: 600, color: '#1b1b1c', margin: '0 0 4px 0', letterSpacing: '-0.01em' }}>Workspace Management</h1>
          <p style={{ fontSize: '14px', color: '#414755', margin: 0 }}>Organize environments and manage isolation boundaries for data validation workflows.</p>
        </div>
        <button style={{ backgroundColor: '#0057c2', color: '#ffffff', padding: '10px 24px', borderRadius: '8px', fontSize: '14px', fontWeight: 500, border: 'none', display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', boxShadow: '0 1px 2px rgba(0,0,0,0.05)' }}>
          <PlusOutlined style={{ fontSize: '16px' }} /> Create New Workspace
        </button>
      </div>

      <div className={styles.bentoGrid3}>
        <div className={styles.bentoCardLite}>
          <div style={{ height: '48px', width: '48px', borderRadius: '8px', backgroundColor: 'rgba(0, 87, 194, 0.1)', color: '#0057c2', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '24px' }}><TeamOutlined /></div>
          <div><p style={{ margin: 0, fontSize: '12px', fontWeight: 500, color: '#414755' }}>Total Users</p><p style={{ margin: 0, fontSize: '24px', fontWeight: 600, color: '#1b1b1c' }}>1,284</p></div>
        </div>
        <div className={styles.bentoCardLite}>
          <div style={{ height: '48px', width: '48px', borderRadius: '8px', backgroundColor: 'rgba(70, 108, 228, 0.1)', color: '#466ce4', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '24px' }}><DatabaseOutlined /></div>
          <div><p style={{ margin: 0, fontSize: '12px', fontWeight: 500, color: '#414755' }}>Active Instances</p><p style={{ margin: 0, fontSize: '24px', fontWeight: 600, color: '#1b1b1c' }}>12</p></div>
        </div>
        <div className={styles.bentoCardLite}>
          <div style={{ height: '48px', width: '48px', borderRadius: '8px', backgroundColor: 'rgba(91, 92, 92, 0.1)', color: '#5b5c5c', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '24px' }}><HddOutlined /></div>
          <div><p style={{ margin: 0, fontSize: '12px', fontWeight: 500, color: '#414755' }}>Data Volume</p><p style={{ margin: 0, fontSize: '24px', fontWeight: 600, color: '#1b1b1c' }}>4.2 TB</p></div>
        </div>
      </div>

      <div className={styles.tableShell}>
        <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
          <thead style={{ backgroundColor: '#fafafa', borderBottom: '1px solid #c1c6d7' }}>
            <tr>
              <th style={{ padding: '16px 24px', fontSize: '14px', fontWeight: 500, color: '#414755' }}>Workspace Name</th>
              <th style={{ padding: '16px 24px', fontSize: '14px', fontWeight: 500, color: '#414755' }}>Created Date</th>
              <th style={{ padding: '16px 24px', fontSize: '14px', fontWeight: 500, color: '#414755' }}>Active User Counts</th>
              <th style={{ padding: '16px 24px', fontSize: '14px', fontWeight: 500, color: '#414755' }}>Status</th>
              <th style={{ padding: '16px 24px', fontSize: '14px', fontWeight: 500, color: '#414755', textAlign: 'right' }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {workspaces.map(row => (
              <tr key={row.id} className={styles.dataTableRow}>
                <td style={{ padding: '16px 24px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <span style={{ fontSize: '14px', fontWeight: 600, color: '#1b1b1c' }}>{row.name}</span>
                    {row.isDefault && <span style={{ fontSize: '11px', fontWeight: 700, backgroundColor: 'rgba(0, 87, 194, 0.1)', color: '#0057c2', border: '1px solid rgba(0, 87, 194, 0.2)', padding: '2px 8px', borderRadius: '4px', textTransform: 'uppercase' }}>Default/Global</span>}
                  </div>
                </td>
                <td style={{ padding: '16px 24px', fontSize: '14px', color: '#414755' }}>{row.createdDate}</td>
                <td style={{ padding: '16px 24px', fontSize: '14px', color: '#414755' }}>{row.userCount}</td>
                <td style={{ padding: '16px 24px' }}>{getStatusBadge(row.status)}</td>
                <td style={{ padding: '16px 24px', textAlign: 'right' }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: '8px' }}>
                    <button style={{ border: 'none', background: 'none', padding: '8px', cursor: 'pointer', color: '#414755', borderRadius: '8px' }}><EditOutlined style={{ fontSize: '18px' }} /></button>
                    <button disabled={row.isDefault} onClick={() => handleDeleteWorkspace(row.id)} style={{ border: 'none', background: 'none', padding: '8px', cursor: row.isDefault ? 'not-allowed' : 'pointer', color: row.isDefault ? '#c1c6d7' : '#ba1a1a', opacity: row.isDefault ? 0.5 : 1, borderRadius: '8px' }}><DeleteOutlined style={{ fontSize: '18px' }} /></button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        <div style={{ padding: '16px 24px', borderTop: '1px solid #c1c6d7', display: 'flex', justifyContent: 'space-between', alignItems: 'center', backgroundColor: '#fafafa' }}>
          <span style={{ fontSize: '12px', color: '#414755' }}>Showing 1-5 of 12 Workspaces</span>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <button disabled style={{ padding: '8px', border: 'none', background: 'none', color: '#c1c6d7', cursor: 'not-allowed' }}><LeftOutlined /></button>
            <button style={{ width: '32px', height: '32px', borderRadius: '8px', backgroundColor: '#0057c2', color: '#ffffff', border: 'none', fontSize: '14px', fontWeight: 500 }}>1</button>
            <button style={{ padding: '8px', border: 'none', background: 'none', color: '#414755', cursor: 'pointer' }}><RightOutlined /></button>
          </div>
        </div>
      </div>

      <div style={{ padding: '24px', backgroundColor: 'rgba(0, 87, 194, 0.05)', border: '1px solid rgba(0, 87, 194, 0.1)', borderRadius: '12px', display: 'flex', gap: '24px', alignItems: 'flex-start' }}>
        <div style={{ padding: '8px', backgroundColor: 'rgba(0, 87, 194, 0.1)', color: '#0057c2', borderRadius: '8px' }}><BulbOutlined style={{ fontSize: '20px' }} /></div>
        <div>
          <h3 style={{ margin: '0 0 4px 0', fontSize: '14px', fontWeight: 700, color: '#1b1b1c' }}>Administrative Pro-Tip</h3>
          <p style={{ margin: 0, fontSize: '14px', color: '#414755', lineHeight: '22px' }}>Workspaces allow you to isolate validation rules and data source connections between different business units. Remember that the "Global Workspace" rules are inherited by all child workspaces unless explicitly overridden in the workspace configuration settings.</p>
        </div>
      </div>
    </div>
  );
};