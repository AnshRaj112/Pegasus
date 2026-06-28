import React from 'react';
import {
  PlusOutlined, TeamOutlined, DatabaseOutlined, HddOutlined,
  EditOutlined, DeleteOutlined, LeftOutlined, RightOutlined, BulbOutlined
} from '@ant-design/icons';

import { useAppSelector, useAppDispatch } from '../../../redux/store';
import { adminActions } from '../Admin.reducer';
import adminStyles from '../Admin.module.scss';
import styles from './WorkspaceMgmtSubView.module.scss';

const WorkspaceMgmtSubView: React.FC = () => {
  const dispatch = useAppDispatch();
  const workspaces = useAppSelector((state) => state.admin.workspaces.data);

  const handleDeleteWorkspace = (id: string) => {
    dispatch(adminActions.deleteWorkspace(id));
  };

  const getStatusBadge = (status: string) => {
    if (status === 'Active') {
      return (
        <span className={`${styles.statusBadge} ${styles.statusActive}`}>
          <span className={styles.statusDot} /> Active
        </span>
      );
    }
    if (status === 'Restricted') {
      return (
        <span className={`${styles.statusBadge} ${styles.statusRestricted}`}>
          <span className={styles.statusDot} /> Restricted
        </span>
      );
    }
    return (
      <span className={`${styles.statusBadge} ${styles.statusArchived}`}>
        <span className={styles.statusDot} /> Archived
      </span>
    );
  };

  return (
    <div className={styles.root}>
      <div className={styles.pageHeader}>
        <div>
          <h1 className={styles.pageTitle}>Workspace Management</h1>
          <p className={styles.pageSubtitle}>Organize environments and manage isolation boundaries for data validation workflows.</p>
        </div>
        <button type="button" className={styles.primaryBtn}>
          <PlusOutlined className={styles.primaryBtnIcon} /> Create New Workspace
        </button>
      </div>

      <div className={adminStyles.bentoGrid3}>
        <div className={adminStyles.bentoCardLite}>
          <div className={`${styles.statIcon} ${styles.statIconUsers}`}><TeamOutlined /></div>
          <div>
            <p className={styles.statLabel}>Total Users</p>
            <p className={styles.statValue}>1,284</p>
          </div>
        </div>
        <div className={adminStyles.bentoCardLite}>
          <div className={`${styles.statIcon} ${styles.statIconInstances}`}><DatabaseOutlined /></div>
          <div>
            <p className={styles.statLabel}>Active Instances</p>
            <p className={styles.statValue}>12</p>
          </div>
        </div>
        <div className={adminStyles.bentoCardLite}>
          <div className={`${styles.statIcon} ${styles.statIconVolume}`}><HddOutlined /></div>
          <div>
            <p className={styles.statLabel}>Data Volume</p>
            <p className={styles.statValue}>4.2 TB</p>
          </div>
        </div>
      </div>

      <div className={adminStyles.tableShell}>
        <table className={styles.dataTable}>
          <thead className={styles.tableHead}>
            <tr>
              <th className={styles.tableHeadCell}>Workspace Name</th>
              <th className={styles.tableHeadCell}>Created Date</th>
              <th className={styles.tableHeadCell}>Active User Counts</th>
              <th className={styles.tableHeadCell}>Status</th>
              <th className={`${styles.tableHeadCell} ${styles.tableHeadCellRight}`}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {workspaces.map(row => (
              <tr key={row.id} className={adminStyles.dataTableRow}>
                <td className={styles.tableCell}>
                  <div className={styles.nameRow}>
                    <span className={styles.workspaceName}>{row.name}</span>
                    {row.isDefault && <span className={styles.defaultBadge}>Default/Global</span>}
                  </div>
                </td>
                <td className={`${styles.tableCell} ${styles.tableCellMuted}`}>{row.createdDate}</td>
                <td className={`${styles.tableCell} ${styles.tableCellMuted}`}>{row.userCount}</td>
                <td className={styles.tableCell}>{getStatusBadge(row.status)}</td>
                <td className={`${styles.tableCell} ${styles.tableHeadCellRight}`}>
                  <div className={styles.actionRow}>
                    <button type="button" className={styles.iconBtn}><EditOutlined className={styles.iconBtnGlyph} /></button>
                    <button
                      type="button"
                      disabled={row.isDefault}
                      onClick={() => handleDeleteWorkspace(row.id)}
                      className={`${styles.iconBtn} ${styles.iconBtnDanger}`}
                    >
                      <DeleteOutlined className={styles.iconBtnGlyph} />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        <div className={styles.tableFooter}>
          <span className={styles.footerMeta}>Showing 1-5 of 12 Workspaces</span>
          <div className={styles.pagination}>
            <button type="button" disabled className={styles.pageNavBtn}><LeftOutlined /></button>
            <button type="button" className={styles.pageActive}>1</button>
            <button type="button" className={styles.pageNavBtn}><RightOutlined /></button>
          </div>
        </div>
      </div>

      <div className={styles.tipBanner}>
        <div className={styles.tipIconWrap}><BulbOutlined className={styles.tipIcon} /></div>
        <div>
          <h3 className={styles.tipTitle}>Administrative Pro-Tip</h3>
          <p className={styles.tipBody}>Workspaces allow you to isolate validation rules and data source connections between different business units. Remember that the &quot;Global Workspace&quot; rules are inherited by all child workspaces unless explicitly overridden in the workspace configuration settings.</p>
        </div>
      </div>
    </div>
  );
};

export default WorkspaceMgmtSubView;
