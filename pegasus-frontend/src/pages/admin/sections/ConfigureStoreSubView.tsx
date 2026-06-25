import React, { useEffect, useRef, useState } from 'react';
import { Modal, Spin } from 'antd';
import {
  PlusOutlined,
  SearchOutlined,
  FilterOutlined,
  SettingOutlined,
  EditOutlined,
  ApiOutlined,
  SyncOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  GoogleOutlined,
  AmazonOutlined,
  WindowsOutlined,
  FolderOpenOutlined,
  BulbOutlined,
  DeleteOutlined,
} from '@ant-design/icons';
import styles from '../Admin.module.scss';
import { useAppSelector, useAppDispatch } from '../../../redux/store';
import { adminActions } from '../Admin.reducer';
import { ConnectStorageModal } from './ConnectStorageModal';
import { StorageProviderItem } from '../Admin.interface';

export const ConfigureStoreSubView: React.FC = () => {
  const dispatch = useAppDispatch();
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [connectModalOpen, setConnectModalOpen] = useState(false);
  const [editingConnection, setEditingConnection] = useState<StorageProviderItem | null>(null);
  const [settingsTargetId, setSettingsTargetId] = useState<string | null>(null);

  const {
    data: storageProviders,
    isFetching,
    isCreating,
    isUpdating,
    isDeletingId,
    testingConnectionId: testingId,
    testResult,
    error,
    createError,
    updateError,
  } = useAppSelector((state) => state.admin.storageProviders);

  const wasCreatingRef = useRef(false);
  const wasUpdatingRef = useRef(false);

  useEffect(() => {
    dispatch(adminActions.fetchProvidersRequest());
  }, [dispatch]);

  useEffect(() => {
    if (wasCreatingRef.current && !isCreating && connectModalOpen && !createError && !editingConnection) {
      setConnectModalOpen(false);
    }
    wasCreatingRef.current = isCreating;
  }, [isCreating, connectModalOpen, createError, editingConnection]);

  useEffect(() => {
    if (wasUpdatingRef.current && !isUpdating && connectModalOpen && !updateError && editingConnection) {
      setConnectModalOpen(false);
      setEditingConnection(null);
    }
    wasUpdatingRef.current = isUpdating;
  }, [isUpdating, connectModalOpen, updateError, editingConnection]);

  const handleOpenCreate = () => {
    setEditingConnection(null);
    setConnectModalOpen(true);
  };

  const handleOpenEdit = (provider: StorageProviderItem) => {
    setEditingConnection(provider);
    setConnectModalOpen(true);
    setSettingsTargetId(null);
  };

  const handleCloseModal = () => {
    setConnectModalOpen(false);
    setEditingConnection(null);
    dispatch(adminActions.clearCreateProviderError());
    dispatch(adminActions.clearUpdateProviderError());
  };

  const handleTestConnection = (id: string) => {
    dispatch(adminActions.testConnectionRequest(id));
  };

  const handleDelete = (id: string) => {
    Modal.confirm({
      title: 'Remove storage connection?',
      content: 'Validation jobs using this bucket will need another connection or inline credentials.',
      okText: 'Remove',
      okType: 'danger',
      onOk: () => dispatch(adminActions.deleteProviderRequest(id)),
    });
    setSettingsTargetId(null);
  };

  const filteredProviders = storageProviders.filter(
    (prov) =>
      prov.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      prov.providerType.toLowerCase().includes(searchQuery.toLowerCase()) ||
      prov.bucket.toLowerCase().includes(searchQuery.toLowerCase()),
  );

  const getProviderIcon = (type: string) => {
    switch (type) {
      case 'Google Cloud Storage':
        return (
          <div
            style={{
              width: '40px',
              height: '40px',
              borderRadius: '8px',
              backgroundColor: 'rgba(66, 133, 244, 0.1)',
              color: '#4285F4',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '20px',
            }}
          >
            <GoogleOutlined />
          </div>
        );
      case 'Amazon S3':
        return (
          <div
            style={{
              width: '40px',
              height: '40px',
              borderRadius: '8px',
              backgroundColor: 'rgba(255, 153, 0, 0.1)',
              color: '#FF9900',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '20px',
            }}
          >
            <AmazonOutlined />
          </div>
        );
      case 'Azure Blob Storage':
        return (
          <div
            style={{
              width: '40px',
              height: '40px',
              borderRadius: '8px',
              backgroundColor: 'rgba(0, 120, 212, 0.1)',
              color: '#0078D4',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '20px',
            }}
          >
            <WindowsOutlined />
          </div>
        );
      default:
        return (
          <div
            style={{
              width: '40px',
              height: '40px',
              borderRadius: '8px',
              backgroundColor: 'rgba(65, 71, 85, 0.1)',
              color: '#414755',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '20px',
            }}
          >
            <FolderOpenOutlined />
          </div>
        );
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '32px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end' }}>
        <div>
          <h1 style={{ fontSize: '38px', fontWeight: 600, color: '#1b1b1c', margin: '0 0 4px 0', letterSpacing: '-0.02em' }}>
            Configure Store
          </h1>
          <p style={{ fontSize: '14px', color: '#414755', margin: 0 }}>
            Manage your storage providers and bucket configurations for data validation workflows.
          </p>
        </div>
        <button
          type="button"
          onClick={handleOpenCreate}
          style={{
            backgroundColor: '#234B5F',
            color: '#ffffff',
            padding: '8px 24px',
            borderRadius: '8px',
            fontSize: '14px',
            fontWeight: 500,
            border: 'none',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            cursor: 'pointer',
            boxShadow: '0 1px 2px rgba(0,0,0,0.05)',
          }}
        >
          <PlusOutlined /> Add New Storage Bucket
        </button>
      </div>

      <div style={{ display: 'flex', gap: '16px' }}>
        <div style={{ position: 'relative', flexGrow: 1, maxWidth: '448px' }}>
          <SearchOutlined
            style={{
              position: 'absolute',
              left: '12px',
              top: '50%',
              transform: 'translateY(-50%)',
              color: '#727786',
              fontSize: '20px',
            }}
          />
          <input
            type="text"
            placeholder="Filter buckets by name or provider..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{
              width: '100%',
              height: '40px',
              boxSizing: 'border-box',
              padding: '8px 16px 8px 40px',
              borderRadius: '8px',
              border: '1px solid #d9d9d9',
              outline: 'none',
              fontSize: '14px',
              backgroundColor: '#ffffff',
            }}
          />
        </div>
        <button
          type="button"
          style={{
            padding: '8px 16px',
            height: '40px',
            borderRadius: '8px',
            border: '1px solid #d9d9d9',
            backgroundColor: '#ffffff',
            fontSize: '14px',
            fontWeight: 500,
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            cursor: 'pointer',
            color: '#1b1b1c',
          }}
        >
          <FilterOutlined style={{ fontSize: '20px' }} />
        </button>
      </div>

      {error && (
        <div
          style={{
            padding: '12px 16px',
            borderRadius: '8px',
            backgroundColor: '#fff2f0',
            border: '1px solid #ffccc7',
            color: '#cf1322',
            fontSize: '14px',
          }}
        >
          {error}
        </div>
      )}

      <div className={styles.storeGrid}>
        {isFetching && storageProviders.length === 0 ? (
          <div className={styles.emptyState}>
            <Spin size="large" />
            <p style={{ marginTop: 16 }}>Loading connected storage buckets…</p>
          </div>
        ) : filteredProviders.length === 0 ? (
          <div className={styles.emptyState}>
            <GoogleOutlined style={{ fontSize: 32, color: '#4285F4', marginBottom: 12 }} />
            <p style={{ margin: '0 0 8px', fontWeight: 600, color: '#1b1b1c' }}>No storage buckets connected</p>
            <p style={{ margin: 0, fontSize: 14 }}>
              Connect a Google Cloud Storage bucket with a service account JSON key to use it in validation.
            </p>
          </div>
        ) : (
          filteredProviders.map((prov) => (
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
                  <span
                    style={{
                      padding: '4px 8px',
                      borderRadius: '4px',
                      backgroundColor: '#f6ffed',
                      border: '1px solid #b7eb8f',
                      color: '#52c41a',
                      fontSize: '12px',
                      fontWeight: 500,
                      display: 'flex',
                      alignItems: 'center',
                      gap: '4px',
                    }}
                  >
                    <span style={{ width: '6px', height: '6px', borderRadius: '50%', backgroundColor: '#52c41a' }} /> Active
                  </span>
                ) : (
                  <span
                    style={{
                      padding: '4px 8px',
                      borderRadius: '4px',
                      backgroundColor: '#fffbe6',
                      border: '1px solid #ffe58f',
                      color: '#faad14',
                      fontSize: '12px',
                      fontWeight: 500,
                      display: 'flex',
                      alignItems: 'center',
                      gap: '4px',
                    }}
                  >
                    <span style={{ width: '6px', height: '6px', borderRadius: '50%', backgroundColor: '#faad14' }} /> Inactive
                  </span>
                )}
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px' }}>
                  <span style={{ color: '#414755' }}>{prov.pathLabel}</span>
                  <span style={{ color: '#1b1b1c', fontFamily: 'var(--font-mono)' }}>{prov.pathValue}</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px' }}>
                  <span style={{ color: '#414755' }}>Last Updated:</span>
                  <span style={{ color: '#1b1b1c' }}>{prov.syncTime}</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px' }}>
                  <span style={{ color: '#414755' }}>{prov.regionLabel}</span>
                  <span style={{ color: '#1b1b1c' }}>{prov.regionValue}</span>
                </div>
              </div>

              <div
                style={{
                  display: 'flex',
                  gap: '8px',
                  marginTop: '4px',
                  paddingTop: '16px',
                  borderTop: '1px solid #f0f0f0',
                }}
              >
                <button
                  type="button"
                  disabled={testingId !== null}
                  onClick={() => handleTestConnection(prov.id)}
                  style={{
                    flexGrow: 1,
                    padding: '8px',
                    border:
                      testResult[prov.id] === 'success'
                        ? '1px solid #52c41a'
                        : testResult[prov.id] === 'failed'
                          ? '1px solid #ff4d4f'
                          : '1px solid #d9d9d9',
                    borderRadius: '8px',
                    backgroundColor: 'transparent',
                    color:
                      testResult[prov.id] === 'success'
                        ? '#52c41a'
                        : testResult[prov.id] === 'failed'
                          ? '#ff4d4f'
                          : '#1b1b1c',
                    fontSize: '14px',
                    fontWeight: 500,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '8px',
                    cursor: testingId ? 'not-allowed' : 'pointer',
                    transition: 'all 0.2s',
                  }}
                >
                  {testingId === prov.id ? (
                    <>
                      <SyncOutlined spin /> Testing...
                    </>
                  ) : testResult[prov.id] === 'success' ? (
                    <>
                      <CheckCircleOutlined /> Success
                    </>
                  ) : testResult[prov.id] === 'failed' ? (
                    <>
                      <CloseCircleOutlined /> Failed
                    </>
                  ) : (
                    <>
                      <ApiOutlined /> Test Connection
                    </>
                  )}
                </button>
                <button
                  type="button"
                  onClick={() => setSettingsTargetId(settingsTargetId === prov.id ? null : prov.id)}
                  style={{
                    padding: '8px',
                    border: '1px solid #d9d9d9',
                    borderRadius: '8px',
                    backgroundColor: 'transparent',
                    cursor: 'pointer',
                    color: '#1b1b1c',
                  }}
                >
                  <SettingOutlined style={{ fontSize: '18px' }} />
                </button>
              </div>

              {settingsTargetId === prov.id && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  <button
                    type="button"
                    onClick={() => handleOpenEdit(prov)}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: 8,
                      padding: '8px',
                      border: '1px solid #d9d9d9',
                      borderRadius: '8px',
                      backgroundColor: '#ffffff',
                      color: '#1b1b1c',
                      fontSize: '13px',
                      fontWeight: 500,
                      cursor: 'pointer',
                    }}
                  >
                    <EditOutlined />
                    Edit connection
                  </button>
                  <button
                    type="button"
                    disabled={isDeletingId === prov.id}
                    onClick={() => handleDelete(prov.id)}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: 8,
                      padding: '8px',
                      border: '1px solid #ffccc7',
                      borderRadius: '8px',
                      backgroundColor: '#fff2f0',
                      color: '#cf1322',
                      fontSize: '13px',
                      fontWeight: 500,
                      cursor: isDeletingId === prov.id ? 'not-allowed' : 'pointer',
                    }}
                  >
                    <DeleteOutlined />
                    {isDeletingId === prov.id ? 'Removing…' : 'Remove connection'}
                  </button>
                </div>
              )}
            </div>
          ))
        )}
      </div>

      <div
        style={{
          marginTop: '32px',
          padding: '24px',
          backgroundColor: 'rgba(0, 87, 194, 0.05)',
          border: '1px solid rgba(0, 87, 194, 0.1)',
          borderRadius: '12px',
          display: 'flex',
          gap: '24px',
          alignItems: 'flex-start',
        }}
      >
        <div style={{ padding: '8px', backgroundColor: 'rgba(0, 87, 194, 0.1)', color: '#234B5F', borderRadius: '8px' }}>
          <BulbOutlined style={{ fontSize: '20px' }} />
        </div>
        <div>
          <h3 style={{ margin: '0 0 4px 0', fontSize: '14px', fontWeight: 700, color: '#1b1b1c' }}>Administrative Pro-Tip</h3>
          <p style={{ margin: 0, fontSize: '14px', color: '#414755', lineHeight: '22px' }}>
            Upload or paste a Google Cloud service account JSON key with Storage Object Viewer (or broader) access on
            your bucket. Saved connections are encrypted and reused automatically in the validation file picker.
          </p>
        </div>
      </div>

      <ConnectStorageModal
        open={connectModalOpen}
        isSubmitting={isCreating || isUpdating}
        error={editingConnection ? updateError : createError}
        editingConnection={editingConnection}
        onClose={handleCloseModal}
        onClearError={() => {
          dispatch(adminActions.clearCreateProviderError());
          dispatch(adminActions.clearUpdateProviderError());
        }}
        onSubmit={(payload) => {
          if (payload.id) {
            dispatch(adminActions.updateProviderRequest(payload));
          } else {
            dispatch(adminActions.createProviderRequest({
              name: payload.name,
              bucket: payload.bucket,
              projectId: payload.projectId,
              credentialsJson: payload.credentialsJson ?? '',
              provider: payload.provider,
            }));
          }
        }}
      />
    </div>
  );
};
