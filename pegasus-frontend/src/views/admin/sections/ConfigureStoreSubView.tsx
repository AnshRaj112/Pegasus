import React, { useState } from 'react';

interface StorageProviderItem {
  id: string;
  name: string;
  providerType: 'Google Cloud Storage' | 'Amazon S3' | 'Local File System' | 'Azure Blob Storage';
  status: 'Success' | 'Syncing';
  pathLabel: string;
  pathValue: string;
  syncTime: string;
  regionLabel: string;
  regionValue: string;
  logoBg: string;
  logoSrc?: string;
  logoIcon?: string;
}

export const ConfigureStoreSubView: React.FC = () => {
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [testingId, setTestingId] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<{ [key: string]: 'success' | null }>({});

  const storageProviders: StorageProviderItem[] = [
    { id: 'p1', name: 'production-datalake-v1', providerType: 'Google Cloud Storage', status: 'Success', pathLabel: 'Bucket Path:', pathValue: 'gs://finance-prod-audit', syncTime: '2023-10-24 14:22:05', regionLabel: 'Region:', regionValue: 'us-east1', logoBg: '#4285F4/10', logoSrc: 'https://googleusercontent.com' },
    { id: 'p2', name: 'staging-validation-store', providerType: 'Amazon S3', status: 'Syncing', pathLabel: 'Bucket Path:', pathValue: 's3://audit-staging-results', syncTime: '2023-10-24 15:10:44', regionLabel: 'Region:', regionValue: 'us-west-2', logoBg: '#FF9900/10', logoSrc: 'https://googleusercontent.com' },
    { id: 'p3', name: 'local-dev-cache', providerType: 'Local File System', status: 'Success', pathLabel: 'System Path:', pathValue: '/mnt/data/audit_cache', syncTime: '2023-10-24 09:00:00', regionLabel: 'Mount Point:', regionValue: 'Ext4 Network Drive', logoBg: 'rgba(65,71,85,0.1)', logoIcon: 'folder_zip' },
    { id: 'p4', name: 'legacy-reports-archive', providerType: 'Azure Blob Storage', status: 'Success', pathLabel: 'Container:', pathValue: 'az://archive/2023-q3', syncTime: '2023-10-23 23:59:59', regionLabel: 'Region:', regionValue: 'UK South', logoBg: '#0078D4/10', logoSrc: 'https://googleusercontent.com' }
  ];

  const handleTestConnection = (id: string) => {
    setTestingId(id);
    setTimeout(() => {
      setTestingId(null);
      setTestResult(prev => ({ ...prev, [id]: 'success' }));
      setTimeout(() => {
        setTestResult(prev => ({ ...prev, [id]: null }));
      }, 2000);
    }, 1500);
  };

  const filteredProviders = storageProviders.filter(prov => 
    prov.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    prov.providerType.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', width: '100%' }}>
      {/* Subview Header Block */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: 'var(--xl)' }}>
        <div>
          <h2 style={{ fontSize: 'var(--h2)', fontWeight: 600, margin: '0 0 var(--xs) 0' }}>Configure Store</h2>
          <p style={{ fontSize: 'var(--body-md)', color: 'var(--on-surface-variant)', margin: 0 }}>
            Manage your storage providers and bucket configurations for data validation workflows.
          </p>
        </div>
        <button style={{ background: '#1677ff', color: '#fff', border: 'none', padding: 'var(--sm) var(--lg)', borderRadius: '8px', fontFamily: 'var(--font-label-md)', fontSize: 'var(--label-md)', fontWeight: 500, display: 'flex', alignItems: 'center', gap: 'var(--xs)', cursor: 'pointer', boxShadow: '0 2px 0 rgba(22,119,255,0.05)' }}>
          <span className="material-symbols-outlined" style={{ fontSize: '18px' }}>add</span> Add New Storage Bucket
        </button>
      </div>

      {/* Local Filter Bar Input Component */}
      <div className="matrixControlBar" style={{ background: 'transparent', border: 'none', padding: 0, boxShadow: 'none', marginBottom: 'var(--lg)' }}>
        <div className="matrixSearchWrapper" style={{ width: '448px' }}>
          <span className="material-symbols-outlined searchIcon">search</span>
          <input 
            type="text" 
            placeholder="Filter buckets by name or provider..." 
            className="matrixSearchInput" 
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{ background: 'var(--surface-container-lowest)' }}
          />
        </div>
        <button className="submitActionBtn" style={{ width: 'auto', background: 'var(--surface-container-lowest)', padding: '0 var(--md)' }}>
          <span className="material-symbols-outlined" style={{ fontSize: '20px' }}>filter_list</span> Filter
        </button>
      </div>

      {/* Grid Layout Cards Matrix Container */}
      <div className="storeCardsGrid">
        {filteredProviders.map(prov => (
          <div key={prov.id} className="antCard">
            <div className="providerCardHeader">
              <div className="providerLogoGroup">
                <div className="providerIconContainer" style={{ backgroundColor: prov.logoBg.includes('/') ? 'rgba(65,71,85,0.1)' : prov.logoBg }}>
                  {prov.logoSrc ? (
                    <img src={prov.logoSrc} alt={prov.name} style={{ width: '24px', height: '24px', objectFit: 'contain' }} />
                  ) : (
                    <span className="material-symbols-outlined" style={{ color: 'var(--on-surface-variant)' }}>{prov.logoIcon}</span>
                  )}
                </div>
                <div>
                  <h3 style={{ margin: 0, fontSize: 'var(--label-md)', fontWeight: 600, color: 'var(--on-surface)' }}>{prov.name}</h3>
                  <span style={{ fontSize: 'var(--body-sm)', color: 'var(--on-surface-variant)' }}>{prov.providerType}</span>
                </div>
              </div>
              
              {prov.status === 'Success' ? (
                <span className="badgeStatusSuccess">
                  <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#52c41a' }}></span> Success
                </span>
              ) : (
                <span className="badgeStatusSyncing">
                  <span className="w-1.5 h-1.5 rounded-full bg-[#faad14] animate-pulse" style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#faad14' }}></span> Syncing
                </span>
              )}
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sm)', fontSize: 'var(--body-sm)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--on-surface-variant)' }}>{prov.pathLabel}</span>
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: 'var(--code-sm)', color: 'var(--on-surface)' }}>{prov.pathValue}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--on-surface-variant)' }}>Last Synchronized:</span>
                <span style={{ color: 'var(--on-surface)' }}>{prov.syncTime}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--on-surface-variant)' }}>{prov.regionLabel}</span>
                <span style={{ color: 'var(--on-surface)' }}>{prov.regionValue}</span>
              </div>
            </div>

            <div className="cardActionDivider">
              <button 
                type="button"
                disabled={testingId !== null}
                onClick={() => handleTestConnection(prov.id)}
                className="submitActionBtn" 
                style={{ 
                  flexGrow: 1, 
                  background: 'none', 
                  fontSize: 'var(--label-md)',
                  borderColor: testResult[prov.id] ? '#52c41a' : 'var(--outline-variant)',
                  color: testResult[prov.id] ? '#52c41a' : 'var(--on-surface)'
                }}
              >
                {testingId === prov.id ? (
                  <><span className="material-symbols-outlined animate-spin" style={{ fontSize: '18px' }}>sync</span> Testing...</>
                ) : testResult[prov.id] === 'success' ? (
                  <><span className="material-symbols-outlined" style={{ fontSize: '18px', color: '#52c41a' }}>check_circle</span> Success</>
                ) : (
                  <><span className="material-symbols-outlined" style={{ fontSize: '18px' }}>network_check</span> Test Connection</>
                )}
              </button>
              <button type="button" className="submitActionBtn" style={{ width: '40px', background: 'none', padding: 0 }}>
                <span className="material-symbols-outlined" style={{ fontSize: '18px' }}>settings</span>
              </button>
            </div>
          </div>
        ))}

                <button type="button" className="providerDashedAddCard">
          <div style={{ width: '48px', height: '48px', borderRadius: '50%', background: 'var(--surface-container)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <span className="material-symbols-outlined" style={{ fontSize: '32px', color: 'var(--on-surface-variant)' }}>add</span>
          </div>
          <span style={{ fontFamily: 'var(--font-label-md)', fontSize: 'var(--label-md)', color: 'var(--on-surface-variant)', fontWeight: 500 }}>
            Configure New Provider
          </span>
        </button>
      </div>

      {/* Usage Analytics Bento Row Section */}
      <div className="bentoMetricsLayout">
        <div className="bentoHealthOverviewCard">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h2 style={{ fontFamily: 'var(--font-h3)', fontSize: '18px', margin: 0 }}>Storage Health Overview</h2>
            <span style={{ fontSize: 'var(--body-sm)', color: 'var(--on-surface-variant)' }}>Last 24 Hours</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--xl)', flexWrap: 'wrap' }}>
            <div style={{ flexGrow: 1 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 'var(--xs)' }}>
                <span style={{ fontSize: 'var(--body-sm)', fontWeight: 500 }}>Global Sync Progress</span>
                <span style={{ fontSize: 'var(--body-sm)', color: 'var(--primary)', fontWeight: 700 }}>89%</span>
              </div>
              <div style={{ width: '100%', background: 'var(--tertiary-fixed)', borderRadius: '9999px', height: '8px', overflow: 'hidden' }}>
                <div style={{ background: 'var(--primary)', height: '8px', borderRadius: '9999px', width: '89%' }}></div>
              </div>
            </div>
            
            <div style={{ display: 'flex', gap: 'var(--md)' }}>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: 'var(--h3)', fontWeight: 'bold', color: '#52c41a', lineHeight: 1 }}>12</div>
                <div style={{ fontSize: '10px', color: 'var(--on-surface-variant)', marginTop: '4px' }}>ACTIVE</div>
              </div>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: 'var(--h3)', fontWeight: 'bold', color: '#faad14', lineHeight: 1 }}>1</div>
                <div style={{ fontSize: '10px', color: 'var(--on-surface-variant)', marginTop: '4px' }}>SYNCING</div>
              </div>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: 'var(--h3)', fontWeight: 'bold', color: 'var(--error)', lineHeight: 1 }}>0</div>
                <div style={{ fontSize: '10px', color: 'var(--on-surface-variant)', marginTop: '4px' }}>FAILING</div>
              </div>
            </div>
          </div>
        </div>

        <div className="bentoScannedDataCard">
          <div style={{ zIndex: 10 }}>
            <h3 style={{ fontFamily: 'var(--font-label-md)', fontSize: 'var(--label-md)', margin: '0 0 var(--xs) 0', opacity: 0.9, fontWeight: 500 }}>
              Total Data Scanned
            </h3>
            <div style={{ fontSize: 'var(--h2)', fontWeight: 'bold', lineHeight: 1 }}>1.42 PB</div>
          </div>
          <div style={{ zIndex: 10, fontSize: 'var(--body-sm)', opacity: 0.8 }}>
            +12.4% from last month
          </div>
          <div style={{ position: 'absolute', right: '-32px', bottom: '-32px', width: '128px', height: '128px', background: 'rgba(255,255,255,0.1)', borderRadius: '50%', filter: 'blur(32px)' }}></div>
          <span className="material-symbols-outlined" style={{ position: 'absolute', right: '16px', top: '16px', fontSize: '48px', opacity: 0.2 }}>
            database
          </span>
        </div>
      </div>
    </div>
  );
};
