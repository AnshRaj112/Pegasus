import React from 'react';
import { Lock, FolderHeart, MoreVertical } from 'lucide-react';

import styles from '../Dashboard.module.scss';

export const WorkspacesPanel: React.FC = () => {
  return (
    <div className={styles.panelCard}>
      <div className={styles.panelHeader}>
        <h3 style={{ fontSize: 'var(--label-md)', fontWeight: 500, margin: 0 }}>Workspaces</h3>
        <button type="button" className={styles.secondaryBtn}>Manage</button>
      </div>

      <div className={`${styles.workspaceScrollContainer} custom-scrollbar`}>
        <div className={styles.defaultWorkspaceCard} style={{ border: '1px solid var(--surface-variant)', borderRadius: '8px', padding: 'var(--md)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--xs)' }}>
              <Lock size={16} style={{ color: 'var(--on-surface-variant)' }} />
              <span style={{ fontWeight: 500, marginLeft: '4px' }}>Global Workspace</span>
            </div>
            <span className={styles['badge-system-highlight']}>System Default</span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--xs)', fontSize: 'var(--body-sm)', marginTop: 'var(--sm)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}><span style={{ color: 'var(--on-surface-variant)' }}>Total Entities:</span><strong>24</strong></div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}><span style={{ color: 'var(--on-surface-variant)' }}>Uptime:</span><strong style={{ color: '#16a34a' }}>99.9%</strong></div>
          </div>
        </div>

        <div className={styles.defaultWorkspaceCard} style={{ border: '1px solid var(--surface-variant)', borderRadius: '8px', padding: 'var(--md)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--xs)' }}>
              <FolderHeart size={16} style={{ color: 'var(--on-surface-variant)' }} />
              <span style={{ fontWeight: 500, marginLeft: '4px' }}>Project Alpha</span>
            </div>
            <button type="button" className={styles['action-icon-btn']}><MoreVertical size={16} /></button>
          </div>
          <div className={styles['avatar-stack']} style={{ marginTop: 'var(--sm)' }}>
            <img className={styles['avatar-item']} src="https://lh3.googleusercontent.com/aida-public/AB6AXuCX0kRU-zDo2PYNv5vPNBrpX0TsPsy_MDESXA9dXfYKQU6LONr7aBuPdNe_XZ-f_TDUwH0vFVHVyqiR9glWBCFUzEJ73GWQ1MMZALmMwZECjlb6z01OR0L_nqCnELDV3E0LDQIHi10LmEaVQ-6haZ5zHzwYGPFiL7qf19OgWiZNv3irOT0DB6pF9HtqDObychtDMjWlX9TiKnUKq9z6wK0rqLLGvrmbp_3XmGF9KgeR6JeQg3cdA03JJZZQVTiHlGl-ZpLTghpdpnE" alt="Scientist" />
            <img style={{ marginLeft: '-6px' }} className={styles['avatar-item']} src="https://lh3.googleusercontent.com/aida-public/AB6AXuDqACb3sNgN8yJV-KZaG3HS66w1TbtXsw483I0VqQ4m_WFw0yrnyCxwpLmjs-qKoF1Y4rJ5DTf0w1myZ6rhjdiF6dkPc53PzIUWoICNygVuLKdjAydlr59lG1Lozcjztc3RdV4vU5p8PsLiO_e5i24ld48QoO4bi7OtCgIurJmUJ1rhHhGM-gESvhPa82e0q-2FS8w1j5ajlxMjK1W99CJz-OfCzf3MtgkU0ep_-hdMReMHWmkc4KFGseF-itMF5obuf7qhhiXL-DU" alt="Scientist 2" />
            <div style={{ marginLeft: '-6px', width: '24px', height: '24px', borderRadius: '50%', border: '2px solid var(--surface)', backgroundColor: 'var(--surface-container-highest)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '8px', fontWeight: 'bold' }}>+3</div>
          </div>
        </div>
      </div>
    </div>
  );
};