import React, { useState } from 'react';
import { 
  PlusOutlined, SearchOutlined, FilterOutlined, SettingOutlined, 
  ApiOutlined, SyncOutlined, CheckCircleOutlined, GoogleOutlined, 
  AmazonOutlined, WindowsOutlined, FolderOpenOutlined, BulbOutlined 
} from '@ant-design/icons';
import styles from '../Admin.module.scss';
import { useAppSelector, useAppDispatch } from '../../../redux/store';
import { adminActions } from '../Admin.reducer';

export const ConfigureStoreSubView: React.FC = () => {
  const dispatch = useAppDispatch();
  const [searchQuery, setSearchQuery] = useState<string>('');
  
  const { data: storageProviders, testingConnectionId : testingId, testResult } = useAppSelector((state) => state.admin.storageProviders);

  const handleTestConnection = (id: string) => {
    dispatch(adminActions.testConnectionRequest(id));
  };

  const filteredProviders = storageProviders.filter(prov => 
    prov.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    prov.providerType.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const getProviderIcon = (type: string) => {
    switch (type) {
      case 'Google Cloud Storage': return <div style={{ width: '40px', height: '40px', borderRadius: '8px', backgroundColor: 'rgba(66, 133, 244, 0.1)', color: '#4285F4', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '20px' }}><GoogleOutlined /></div>;
      case 'Amazon S3': return <div style={{ width: '40px', height: '40px', borderRadius: '8px', backgroundColor: 'rgba(255, 153, 0, 0.1)', color: '#FF9900', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '20px' }}><AmazonOutlined /></div>;
      case 'Azure Blob Storage': return <div style={{ width: '40px', height: '40px', borderRadius: '8px', backgroundColor: 'rgba(0, 120, 212, 0.1)', color: '#0078D4', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '20px' }}><WindowsOutlined /></div>;
      default: return <div style={{ width: '40px', height: '40px', borderRadius: '8px', backgroundColor: 'rgba(65, 71, 85, 0.1)', color: '#414755', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '20px' }}><FolderOpenOutlined /></div>;
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '32px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end' }}>
        <div>
          <h1 style={{ fontSize: '38px', fontWeight: 600, color: '#1b1b1c', margin: '0 0 4px 0', letterSpacing: '-0.02em' }}>Configure Store</h1>
          <p style={{ fontSize: '14px', color: '#414755', margin: 0 }}>Manage your storage providers and bucket configurations for data validation workflows.</p>
        </div>
        <button style={{ backgroundColor: '#1677ff', color: '#ffffff', padding: '8px 24px', borderRadius: '8px', fontSize: '14px', fontWeight: 500, border: 'none', display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', boxShadow: '0 1px 2px rgba(0,0,0,0.05)' }}>
          <PlusOutlined /> Add New Storage Bucket
        </button>
      </div>

      <div style={{ display: 'flex', gap: '16px' }}>
        <div style={{ position: 'relative', flexGrow: 1, maxWidth: '448px' }}>
          <SearchOutlined style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: '#727786', fontSize: '20px' }} />
          <input 
            type="text" 
            placeholder="Filter buckets by name or provider..." 
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{ width: '100%',height: '40px', boxSizing: 'border-box', padding: '8px 16px 8px 40px', borderRadius: '8px', border: '1px solid #d9d9d9', outline: 'none', fontSize: '14px', backgroundColor: '#ffffff' }}
          />
        </div>
        <button style={{ padding: '8px 16px', height: '40px', borderRadius: '8px', border: '1px solid #d9d9d9', backgroundColor: '#ffffff', fontSize: '14px', fontWeight: 500, display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', color: '#1b1b1c' }}>
          <FilterOutlined style={{ fontSize: '20px' }} />
        </button>
      </div>

      <div className={styles.storeGrid}>
        {filteredProviders.map(prov => (
          <div key={prov.id} className={styles.storeCard}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                {getProviderIcon(prov.providerType)}
                <div>
                  <h3 style={{ margin: 0, fontSize: '14px', fontWeight: 500, color: '#1b1b1c' }}>{prov.name}</h3>
                  <span style={{ fontSize: '12px', color: '#414755' }}>{prov.providerType}</span>
                </div>
              </div>
              {prov.status === 'Success' ? (
                <span style={{ padding: '4px 8px', borderRadius: '4px', backgroundColor: '#f6ffed', border: '1px solid #b7eb8f', color: '#52c41a', fontSize: '12px', fontWeight: 500, display: 'flex', alignItems: 'center', gap: '4px' }}><span style={{ width: '6px', height: '6px', borderRadius: '50%', backgroundColor: '#52c41a' }} /> Success</span>
              ) : (
                <span style={{ padding: '4px 8px', borderRadius: '4px', backgroundColor: '#fffbe6', border: '1px solid #ffe58f', color: '#faad14', fontSize: '12px', fontWeight: 500, display: 'flex', alignItems: 'center', gap: '4px' }}><span style={{ width: '6px', height: '6px', borderRadius: '50%', backgroundColor: '#faad14' }} className="animate-pulse" /> Syncing</span>
              )}
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px' }}><span style={{ color: '#414755' }}>{prov.pathLabel}</span><span style={{ color: '#1b1b1c', fontFamily: 'var(--font-mono)' }}>{prov.pathValue}</span></div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px' }}><span style={{ color: '#414755' }}>Last Synchronized:</span><span style={{ color: '#1b1b1c' }}>{prov.syncTime}</span></div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px' }}><span style={{ color: '#414755' }}>{prov.regionLabel}</span><span style={{ color: '#1b1b1c' }}>{prov.regionValue}</span></div>
            </div>

            <div style={{ display: 'flex', gap: '8px', marginTop: '4px', paddingTop: '16px', borderTop: '1px solid #f0f0f0' }}>
              <button 
                disabled={testingId !== null}
                onClick={() => handleTestConnection(prov.id)}
                style={{ flexGrow: 1, padding: '8px', border: testResult[prov.id] ? '1px solid #52c41a' : '1px solid #d9d9d9', borderRadius: '8px', backgroundColor: 'transparent', color: testResult[prov.id] ? '#52c41a' : '#1b1b1c', fontSize: '14px', fontWeight: 500, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px', cursor: testingId ? 'not-allowed' : 'pointer', transition: 'all 0.2s' }}
              >
                {testingId === prov.id ? <><SyncOutlined spin /> Testing...</> : testResult[prov.id] === 'success' ? <><CheckCircleOutlined /> Success</> : <><ApiOutlined /> Test Connection</>}
              </button>
              <button style={{ padding: '8px', border: '1px solid #d9d9d9', borderRadius: '8px', backgroundColor: 'transparent', cursor: 'pointer', color: '#1b1b1c' }}>
                <SettingOutlined style={{ fontSize: '18px' }} />
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* <div style={{ marginTop: '32px', display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: '24px' }}>
        <div style={{ gridColumn: 'span 2 / span 2', backgroundColor: '#f6f3f2', padding: '24px', borderRadius: '12px', border: '1px solid rgba(193, 198, 215, 0.3)', display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h2 style={{ fontSize: '18px', fontWeight: 600, color: '#1b1b1c', margin: 0 }}>Storage Health Overview</h2>
            <span style={{ fontSize: '12px', color: '#414755' }}>Last 24 Hours</span>
          </div>
          <div style={{ display: 'flex', gap: '32px', alignItems: 'center' }}>
            <div style={{ flexGrow: 1 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}><span style={{ fontSize: '12px', fontWeight: 500 }}>Global Sync Progress</span><span style={{ fontSize: '12px', color: '#0057c2', fontWeight: 700 }}>89%</span></div>
              <div style={{ width: '100%', backgroundColor: '#e3e2e2', borderRadius: '999px', height: '8px' }}><div style={{ backgroundColor: '#0057c2', height: '8px', borderRadius: '999px', width: '89%' }} /></div>
            </div>
            <div style={{ display: 'flex', gap: '16px' }}>
              <div style={{ textAlign: 'center' }}><div style={{ fontSize: '24px', fontWeight: 700, color: '#52c41a' }}>12</div><div style={{ fontSize: '10px', textTransform: 'uppercase', color: '#414755' }}>Active</div></div>
              <div style={{ textAlign: 'center' }}><div style={{ fontSize: '24px', fontWeight: 700, color: '#faad14' }}>1</div><div style={{ fontSize: '10px', textTransform: 'uppercase', color: '#414755' }}>Syncing</div></div>
              <div style={{ textAlign: 'center' }}><div style={{ fontSize: '24px', fontWeight: 700, color: '#ba1a1a' }}>0</div><div style={{ fontSize: '10px', textTransform: 'uppercase', color: '#414755' }}>Failing</div></div>
            </div>
          </div>
        </div>

        <div style={{ backgroundColor: '#006ef2', color: '#fefcff', padding: '24px', borderRadius: '12px', display: 'flex', flexDirection: 'column', justifyContent: 'space-between', position: 'relative', overflow: 'hidden' }}>
          <div style={{ zIndex: 10 }}>
            <h3 style={{ fontSize: '14px', fontWeight: 500, margin: '0 0 4px 0', opacity: 0.9 }}>Total Data Scanned</h3>
            <div style={{ fontSize: '30px', fontWeight: 700 }}>1.42 PB</div>
          </div>
          <div style={{ zIndex: 10, fontSize: '12px', opacity: 0.8 }}>+12.4% from last month</div>
          <DatabaseOutlined style={{ position: 'absolute', right: '16px', top: '16px', fontSize: '48px', opacity: 0.2 }} />
          <div style={{ position: 'absolute', right: '-32px', bottom: '-32px', width: '128px', height: '128px', backgroundColor: 'rgba(255,255,255,0.1)', borderRadius: '50%', filter: 'blur(32px)' }} />
        </div>
      </div> */}
      {/* Storage Configuration Pro Tip */}
      <div style={{ marginTop: '32px', padding: '24px', backgroundColor: 'rgba(0, 87, 194, 0.05)', border: '1px solid rgba(0, 87, 194, 0.1)', borderRadius: '12px', display: 'flex', gap: '24px', alignItems: 'flex-start' }}>
        <div style={{ padding: '8px', backgroundColor: 'rgba(0, 87, 194, 0.1)', color: '#0057c2', borderRadius: '8px' }}>
          <BulbOutlined style={{ fontSize: '20px' }} />
        </div>
        <div>
          <h3 style={{ margin: '0 0 4px 0', fontSize: '14px', fontWeight: 700, color: '#1b1b1c' }}>Administrative Pro-Tip</h3>
          <p style={{ margin: 0, fontSize: '14px', color: '#414755', lineHeight: '22px' }}>
            Regularly testing your storage connections ensures scheduled validation jobs run without interruption. For production data lakes, we highly recommend utilizing cloud-native IAM roles rather than hardcoded access keys to maintain strict security compliance.
          </p>
        </div>
      </div>
    </div>
  );
};