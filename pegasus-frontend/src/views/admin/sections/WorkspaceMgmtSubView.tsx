import React, { useState } from 'react';

interface WorkspaceItem {
    id: string;
    name: string;
    isDefault: boolean;
    createdDate: string;
    userCount: number;
    status: 'Active' | 'Restricted' | 'Archived';
}

export const WorkspaceMgmtSubView: React.FC = () => {
    const [workspaces, setWorkspaces] = useState<WorkspaceItem[]>([
        { id: 'w1', name: 'Global Workspace', isDefault: true, createdDate: 'Jan 12, 2023', userCount: 842, status: 'Active' },
        { id: 'w2', name: 'Production (US-East)', isDefault: false, createdDate: 'Mar 05, 2023', userCount: 215, status: 'Active' },
        { id: 'w3', name: 'Quality Assurance (Staging)', isDefault: false, createdDate: 'Jun 18, 2023', userCount: 42, status: 'Active' },
        { id: 'w4', name: 'External Client Sandbox', isDefault: false, createdDate: 'Aug 22, 2023', userCount: 12, status: 'Restricted' },
        { id: 'w5', name: 'Legacy Audit (ReadOnly)', isDefault: false, createdDate: 'Dec 01, 2022', userCount: 4, status: 'Archived' }
    ]);

    const handleDeleteWorkspace = (id: string) => {
        setWorkspaces(prev => prev.filter(w => w.id !== id));
    };

    const getStatusBadge = (status: WorkspaceItem['status']) => {
        switch (status) {
            case 'Active':
                return (
                    <span className="badgeActiveGreen">
                        <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#16a34a' }}></span> Active
                    </span>
                );
            case 'Restricted':
                return (
                    <span className="badgeRestrictedAmber">
                        <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#d97706' }}></span> Restricted
                    </span>
                );
            case 'Archived':
                return (
                    <span className="badgeArchivedGray">
                        <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: 'var(--outline)' }}></span> Archived
                    </span>
                );
        }
    };

    return (
        <div className="workspaceMgmtContainer">
            {/* Page Context Header Area Block */}
            <div className="workspaceHeaderRow">
                <div>
                    <h2 style={{ fontFamily: 'var(--font-h2)', fontSize: 'var(--h2)', color: 'var(--on-surface)', margin: '0 0 var(--xs) 0', fontWeight: 600 }}>
                        Workspace Management
                    </h2>
                    <p style={{ fontSize: 'var(--body-md)', color: 'var(--on-surface-variant)', margin: '4px 0 0' }}>
                        Organize environments and manage isolation boundaries for data validation workflows.
                    </p>
                </div>
                <button type="button" style={{ background: 'var(--primary)', color: 'var(--on-primary)', border: 'none', padding: '10px var(--lg)', borderRadius: '8px', fontFamily: 'var(--font-label-md)', fontSize: 'var(--label-md)', fontWeight: 500, display: 'inline-flex', alignItems: 'center', gap: 'var(--xs)', cursor: 'pointer', boxShadow: '0 1px 2px rgba(0,0,0,0.05)' }}>
                    <span className="material-symbols-outlined" style={{ fontSize: '20px' }}>add</span>
                    Create New Workspace
                </button>
            </div>

            {/* Bento Style Lite Analytics Rows Grid Summary */}
            <div className="bentoLiteMetricsGrid">
                <div className="bentoLiteMetricCard">
                    <div className="metricCardIconBox" style={{ background: 'rgba(0, 87, 194, 0.1)', color: 'var(--primary)' }}>
                        <span className="material-symbols-outlined">groups</span>
                    </div>
                    <div>
                        <p style={{ margin: 0, fontSize: 'var(--body-sm)', fontFamily: 'var(--font-label-md)', color: 'var(--on-surface-variant)' }}>Total Users</p>
                        <p style={{ margin: '4px 0 0 0', fontSize: 'var(--h3)', fontFamily: 'var(--font-h3)', fontWeight: 600, color: 'var(--on-surface)' }}>1,284</p>
                    </div>
                </div>

                <div className="bentoLiteMetricCard">
                    <div className="metricCardIconBox" style={{ background: 'rgba(39, 82, 202, 0.1)', color: 'var(--secondary)' }}>
                        <span className="material-symbols-outlined">database</span>
                    </div>
                    <div>
                        <p style={{ margin: 0, fontSize: 'var(--body-sm)', fontFamily: 'var(--font-label-md)', color: 'var(--on-surface-variant)' }}>Active Instances</p>
                        <p style={{ margin: '4px 0 0 0', fontSize: 'var(--h3)', fontFamily: 'var(--font-h3)', fontWeight: 600, color: 'var(--on-surface)' }}>12</p>
                    </div>
                </div>

                <div className="bentoLiteMetricCard">
                    <div className="metricCardIconBox" style={{ background: 'rgba(91, 92, 92, 0.1)', color: 'var(--tertiary)' }}>
                        <span className="material-symbols-outlined">storage</span>
                    </div>
                    <div>
                        <p style={{ margin: 0, fontSize: 'var(--body-sm)', fontFamily: 'var(--font-label-md)', color: 'var(--on-surface-variant)' }}>Data Volume</p>
                        <p style={{ margin: '4px 0 0 0', fontSize: 'var(--h3)', fontFamily: 'var(--font-h3)', fontWeight: 600, color: 'var(--on-surface)' }}>4.2 TB</p>
                    </div>
                </div>
            </div>

            {/* Main Alignment Matrix Frame Container Table Asset */}
            <div className="workspaceMainTableCard">
                <div className="workspaceTableFrame custom-scrollbar">
                    <table className="workspaceTableLayout">
                        <thead>
                            <tr style={{ borderBottom: '1px solid var(--outline-variant)' }}>
                                <th style={{ padding: 'var(--md) var(--lg)' }}>Workspace Name</th>
                                <th style={{ padding: 'var(--md) var(--lg)' }}>Created Date</th>
                                <th style={{ padding: 'var(--md) var(--lg)' }}>Active User Counts</th>
                                <th style={{ padding: 'var(--md) var(--lg)' }}>Status</th>
                                <th style={{ padding: 'var(--md) var(--lg)', textAlign: 'right' }}>Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            {workspaces.map(row => (
                                <tr key={row.id} className="workspaceDataTableRow" style={{ borderBottom: '1px solid var(--outline-variant)' }}>
                                    <td style={{ padding: 'var(--md) var(--lg)' }}>
                                        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}> {/* Applied clean 12px gap here */}
                                            <span style={{ fontSize: 'var(--label-md)', fontFamily: 'var(--font-label-md)', fontWeight: 600, color: 'var(--on-surface)' }}>
                                                {row.name}
                                            </span>
                                            {row.isDefault && <span className="systemGlobalBadge">Default/Global</span>}
                                        </div>
                                    </td>
                                    <td style={{ padding: 'var(--md) var(--lg)', fontSize: 'var(--body-md)', color: 'var(--on-surface-variant)' }}>
                                        {row.createdDate}
                                    </td>
                                    <td style={{ padding: 'var(--md) var(--lg)', fontSize: 'var(--body-md)', color: 'var(--on-surface-variant)' }}>
                                        {row.userCount}
                                    </td>
                                    <td style={{ padding: 'var(--md) var(--lg)' }}>
                                        {getStatusBadge(row.status)}
                                    </td>
                                    <td style={{ padding: 'var(--md) var(--lg)', textAlign: 'right' }}>
                                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: '4px' }}>
                                            <button type="button" style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '8px', color: 'var(--on-surface-variant)', borderRadius: '8px', display: 'flex', alignItems: 'center' }} title="Edit">
                                                <span className="material-symbols-outlined" style={{ fontSize: '20px' }}>edit</span>
                                            </button>
                                            <button
                                                type="button"
                                                disabled={row.isDefault}
                                                onClick={() => handleDeleteWorkspace(row.id)}
                                                style={{
                                                    background: 'none',
                                                    border: 'none',
                                                    cursor: row.isDefault ? 'not-allowed' : 'pointer',
                                                    padding: '8px',
                                                    color: row.isDefault ? 'var(--outline)' : 'var(--error)',
                                                    opacity: row.isDefault ? 0.4 : 1,
                                                    display: 'flex',
                                                    alignItems: 'center',
                                                    borderRadius: '8px'
                                                }}
                                                title={row.isDefault ? "Root workspace cannot be deleted" : "Delete workspace"}
                                            >
                                                <span className="material-symbols-outlined" style={{ fontSize: '20px' }}>delete</span>
                                            </button>
                                        </div>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>

                {/* Structural Virtualization Pagination Controls Footer block */}
                <div className="matrixTableFooter" style={{ background: '#fafafa', borderTop: '1px solid var(--outline-variant)' }}>
                    <div style={{ fontSize: 'var(--body-sm)', color: 'var(--on-surface-variant)' }}>
                        Showing <strong>1-5</strong> of 12 Workspaces
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--sm)' }}>
                        <button type="button" disabled style={{ background: 'none', border: 'none', opacity: 0.3, cursor: 'not-allowed' }}>
                            <span className="material-symbols-outlined">chevron_left</span>
                        </button>
                        <button type="button" className="paginationNumBtn paginationNumBtnActive" style={{ width: '32px', height: '32px' }}>1</button>
                        <button type="button" className="paginationNumBtn" style={{ width: '32px', height: '32px' }}>2</button>
                        <button type="button" className="paginationNumBtn" style={{ width: '32px', height: '32px' }}>3</button>
                        <button type="button" style={{ background: 'none', border: 'none', cursor: 'pointer' }}>
                            <span className="material-symbols-outlined">chevron_right</span>
                        </button>
                    </div>
                </div>
            </div>

            {/* Helper Pro-Tip Information Banner Section */}
            <div className="adminTipCardRow">
                <div style={{ padding: '8px', borderRadius: '8px', background: 'rgba(0, 87, 194, 0.08)', color: 'var(--primary)', display: 'flex' }}>
                    <span className="material-symbols-outlined">lightbulb</span>
                </div>
                <div>
                    <h3 style={{ fontFamily: 'var(--font-label-md)', fontSize: 'var(--label-md)', fontWeight: 700, color: 'var(--on-surface)', margin: '0 0 4px 0' }}>
                        Administrative Pro-Tip
                    </h3>
                    <p style={{ margin: 0, fontSize: 'var(--body-md)', color: 'var(--on-surface-variant)', lineHeight: '22px' }}>
                        Workspaces allow you to isolate validation rules and data source connections between different business units. Remember that the "Global Workspace" rules are inherited by all child workspaces unless explicitly overridden in the workspace configuration settings.
                    </p>
                </div>
            </div>
        </div>
    );
};