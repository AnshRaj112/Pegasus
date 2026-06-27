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
import styles from './ConfigureStoreSubView.module.scss';
import { useAppSelector, useAppDispatch } from '../../../redux/store';
import { adminActions } from '../Admin.reducer';
import { ConnectStorageModal } from './ConnectStorageModal';
import { StorageProviderItem } from '../Admin.interface';

const providerIconClass = (type: string): string => {
  switch (type) {
    case 'Google Cloud Storage':
      return styles.providerIconGcs;
    case 'Amazon S3':
      return styles.providerIconS3;
    case 'Azure Blob Storage':
      return styles.providerIconAzure;
    default:
      return styles.providerIconDefault;
  }
};

const providerIcon = (type: string) => {
  switch (type) {
    case 'Google Cloud Storage':
      return <GoogleOutlined />;
    case 'Amazon S3':
      return <AmazonOutlined />;
    case 'Azure Blob Storage':
      return <WindowsOutlined />;
    default:
      return <FolderOpenOutlined />;
  }
};

const testBtnClass = (result: 'success' | 'failed' | null | undefined, disabled: boolean): string => {
  const base = styles.testBtn;
  if (disabled) return `${base} ${styles.testBtnDisabled} ${styles.testBtnDefault}`;
  if (result === 'success') return `${base} ${styles.testBtnSuccess}`;
  if (result === 'failed') return `${base} ${styles.testBtnFailed}`;
  return `${base} ${styles.testBtnDefault}`;
};

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

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <div>
          <h1 className={styles.title}>Configure Store</h1>
          <p className={styles.subtitle}>
            Manage your storage providers and bucket configurations for data validation workflows.
          </p>
        </div>
        <button type="button" onClick={handleOpenCreate} className={styles.addBtn}>
          <PlusOutlined /> Add New Storage Bucket
        </button>
      </div>

      <div className={styles.toolbar}>
        <div className={styles.searchWrap}>
          <SearchOutlined className={styles.searchIcon} />
          <input
            type="text"
            placeholder="Filter buckets by name or provider..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className={styles.searchInput}
          />
        </div>
        <button type="button" className={styles.filterBtn}>
          <FilterOutlined className={styles.filterIcon} />
        </button>
      </div>

      {error && (
        <div className={styles.errorBanner}>
          {error}
        </div>
      )}

      <div className={styles.storeGrid}>
        {isFetching && storageProviders.length === 0 ? (
          <div className={styles.emptyState}>
            <Spin size="large" />
            <p className={styles.emptyLoadingText}>Loading connected storage buckets…</p>
          </div>
        ) : filteredProviders.length === 0 ? (
          <div className={styles.emptyState}>
            <GoogleOutlined className={styles.emptyIcon} />
            <p className={styles.emptyTitle}>No storage buckets connected</p>
            <p className={styles.emptyDesc}>
              Connect a Google Cloud Storage bucket with a service account JSON key to use it in validation.
            </p>
          </div>
        ) : (
          filteredProviders.map((prov) => (
            <div key={prov.id} className={styles.storeCard}>
              <div className={styles.cardHeader}>
                <div className={styles.cardHeaderLeft}>
                  <div className={`${styles.providerIcon} ${providerIconClass(prov.providerType)}`}>
                    {providerIcon(prov.providerType)}
                  </div>
                  <div>
                    <h3 className={styles.cardTitle}>{prov.name}</h3>
                    <span className={styles.cardProvider}>{prov.providerType}</span>
                  </div>
                </div>
                {prov.status === 'Success' ? (
                  <span className={`${styles.statusBadge} ${styles.statusActive}`}>
                    <span className={`${styles.statusDot} ${styles.statusDotActive}`} /> Active
                  </span>
                ) : (
                  <span className={`${styles.statusBadge} ${styles.statusInactive}`}>
                    <span className={`${styles.statusDot} ${styles.statusDotInactive}`} /> Inactive
                  </span>
                )}
              </div>

              <div className={styles.cardMeta}>
                <div className={styles.cardMetaRow}>
                  <span className={styles.cardMetaLabel}>{prov.pathLabel}</span>
                  <span className={`${styles.cardMetaValue} ${styles.cardMetaMono}`}>{prov.pathValue}</span>
                </div>
                <div className={styles.cardMetaRow}>
                  <span className={styles.cardMetaLabel}>Last Updated:</span>
                  <span className={styles.cardMetaValue}>{prov.syncTime}</span>
                </div>
                <div className={styles.cardMetaRow}>
                  <span className={styles.cardMetaLabel}>{prov.regionLabel}</span>
                  <span className={styles.cardMetaValue}>{prov.regionValue}</span>
                </div>
              </div>

              <div className={styles.cardActions}>
                <button
                  type="button"
                  disabled={testingId !== null}
                  onClick={() => handleTestConnection(prov.id)}
                  className={testBtnClass(testResult[prov.id], testingId !== null)}
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
                  className={styles.settingsBtn}
                >
                  <SettingOutlined className={styles.settingsIcon} />
                </button>
              </div>

              {settingsTargetId === prov.id && (
                <div className={styles.settingsMenu}>
                  <button type="button" onClick={() => handleOpenEdit(prov)} className={styles.editBtn}>
                    <EditOutlined />
                    Edit connection
                  </button>
                  <button
                    type="button"
                    disabled={isDeletingId === prov.id}
                    onClick={() => handleDelete(prov.id)}
                    className={styles.deleteBtn}
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

      <div className={styles.tipBanner}>
        <div className={styles.tipIconWrap}>
          <BulbOutlined className={styles.tipIcon} />
        </div>
        <div>
          <h3 className={styles.tipTitle}>Administrative Pro-Tip</h3>
          <p className={styles.tipText}>
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
