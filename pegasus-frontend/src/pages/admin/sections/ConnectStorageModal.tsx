import React, { useEffect, useState } from 'react';
import { Modal, Input, Upload, Button } from 'antd';
import { GoogleOutlined, UploadOutlined, InboxOutlined } from '@ant-design/icons';
import { StorageProviderItem, StorageProviderPayload } from '../Admin.interface';
import styles from '../Admin.module.scss';

const { TextArea } = Input;
const { Dragger } = Upload;

interface ConnectStorageModalProps {
  open: boolean;
  isSubmitting: boolean;
  error: string | null;
  editingConnection: StorageProviderItem | null;
  onClose: () => void;
  onSubmit: (payload: StorageProviderPayload) => void;
  onClearError: () => void;
}

const parseCredentialsJson = (
  raw: string,
  { required }: { required: boolean },
): { valid: boolean; projectId?: string; error?: string } => {
  const trimmed = raw.trim();
  if (!trimmed) {
    return required
      ? { valid: false, error: 'Service account JSON is required.' }
      : { valid: true };
  }
  try {
    const parsed = JSON.parse(trimmed) as Record<string, unknown>;
    if (parsed.type !== 'service_account') {
      return { valid: false, error: 'JSON must be a Google service account key (type: service_account).' };
    }
    const projectId = typeof parsed.project_id === 'string' ? parsed.project_id : undefined;
    return { valid: true, projectId };
  } catch {
    return { valid: false, error: 'Invalid JSON. Paste or upload a valid service account key file.' };
  }
};

export const ConnectStorageModal: React.FC<ConnectStorageModalProps> = ({
  open,
  isSubmitting,
  error,
  editingConnection,
  onClose,
  onSubmit,
  onClearError,
}) => {
  const isEditing = editingConnection != null;
  const [name, setName] = useState('');
  const [bucket, setBucket] = useState('');
  const [projectId, setProjectId] = useState('');
  const [credentialsJson, setCredentialsJson] = useState('');
  const [localError, setLocalError] = useState<string | null>(null);
  const [fileName, setFileName] = useState<string | null>(null);

  useEffect(() => {
    if (!open) {
      setName('');
      setBucket('');
      setProjectId('');
      setCredentialsJson('');
      setLocalError(null);
      setFileName(null);
      onClearError();
      return;
    }

    if (editingConnection) {
      setName(editingConnection.name);
      setBucket(editingConnection.bucket);
      setProjectId(editingConnection.projectId ?? '');
      setCredentialsJson('');
      setFileName(null);
      setLocalError(null);
    }
  }, [open, editingConnection, onClearError]);

  const applyCredentialsFile = (file: File) => {
    const reader = new FileReader();
    reader.onload = (event) => {
      const text = String(event.target?.result ?? '');
      setCredentialsJson(text);
      setFileName(file.name);
      const parsed = parseCredentialsJson(text, { required: !isEditing });
      if (parsed.valid && parsed.projectId && !projectId.trim()) {
        setProjectId(parsed.projectId);
      }
      setLocalError(parsed.valid ? null : parsed.error ?? null);
    };
    reader.onerror = () => {
      setLocalError('Could not read the selected file.');
    };
    reader.readAsText(file);
  };

  const handleJsonUpload = (options: { file: File | Blob | string; onSuccess?: (body: unknown) => void }) => {
    const file = options.file as File;
    applyCredentialsFile(file);
    options.onSuccess?.('ok');
  };

  const handleSubmit = () => {
    if (!name.trim()) {
      setLocalError('Connection name is required.');
      return;
    }
    const jsonCheck = parseCredentialsJson(credentialsJson, { required: !isEditing });
    if (!jsonCheck.valid) {
      setLocalError(jsonCheck.error ?? 'Invalid credentials JSON.');
      return;
    }

    setLocalError(null);
    const payload: StorageProviderPayload = {
      name: name.trim(),
      bucket: bucket.trim().replace(/^gs:\/\//, ''),
      projectId: projectId.trim() || jsonCheck.projectId,
      provider: 'google-cloud-storage',
    };
    if (isEditing) {
      payload.id = editingConnection.id;
      if (credentialsJson.trim()) {
        payload.credentialsJson = credentialsJson.trim();
      }
    } else {
      payload.credentialsJson = credentialsJson.trim();
    }
    onSubmit(payload);
  };

  const displayError = localError ?? error;

  return (
    <Modal
      title={isEditing ? 'Edit Storage Connection' : 'Connect Storage Bucket'}
      open={open}
      onCancel={onClose}
      footer={null}
      width={560}
      destroyOnHidden
    >
      <div className={styles.connectModalBody}>
        <div className={styles.providerPicker}>
          <div className={`${styles.providerCard} ${styles.providerCardSelected}`}>
            <div className={styles.gcsIconWrap}>
              <GoogleOutlined className={styles.gcsIcon} />
            </div>
            <div>
              <div className={styles.providerCardTitle}>Google Cloud Storage</div>
              <div className={styles.providerCardSubtitle}>Connect with a service account JSON key</div>
            </div>
          </div>
        </div>

        <div className={styles.connectForm}>
          <label className={styles.connectLabel}>
            Connection name
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. production-audit-lake"
              disabled={isSubmitting}
            />
          </label>

          <label className={styles.connectLabel}>
            GCS bucket name <span className={styles.optionalTag}>(optional)</span>
            <Input
              value={bucket}
              onChange={(e) => setBucket(e.target.value)}
              placeholder="Leave empty to browse any accessible bucket"
              disabled={isSubmitting}
            />
          </label>

          <label className={styles.connectLabel}>
            Project ID <span className={styles.optionalTag}>(optional)</span>
            <Input
              value={projectId}
              onChange={(e) => setProjectId(e.target.value)}
              placeholder="Auto-filled from JSON when available"
              disabled={isSubmitting}
            />
          </label>

          <div className={styles.connectLabel}>
            <span>
              Service account JSON
              {isEditing && <span className={styles.optionalTag}> (optional — leave blank to keep current key)</span>}
            </span>
            <Dragger
              accept=".json,application/json"
              showUploadList={false}
              customRequest={handleJsonUpload}
              disabled={isSubmitting}
              className={styles.jsonDragger}
              openFileDialogOnClick
            >
              <p className="ant-upload-drag-icon">
                <InboxOutlined />
              </p>
              <p className="ant-upload-text">Drop your service account key here, or click to browse</p>
              <p className="ant-upload-hint">
                {fileName
                  ? `Loaded: ${fileName}`
                  : isEditing
                    ? 'Upload a new key only if you want to replace the saved credentials'
                    : 'Download from Google Cloud Console → IAM → Service Accounts → Keys'}
              </p>
            </Dragger>
          </div>

          <label className={styles.connectLabel}>
            Or paste JSON
            <TextArea
              value={credentialsJson}
              onChange={(e) => {
                setCredentialsJson(e.target.value);
                setFileName(null);
                if (localError) setLocalError(null);
              }}
              rows={5}
              placeholder={
                isEditing
                  ? 'Paste new JSON only to replace the saved key'
                  : '{"type": "service_account", "project_id": "...", ...}'
              }
              disabled={isSubmitting}
              className={styles.jsonTextarea}
            />
          </label>

          {displayError && <div className={styles.connectError}>{displayError}</div>}

          <div className={styles.connectActions}>
            <Button onClick={onClose} disabled={isSubmitting}>
              Cancel
            </Button>
            <Button
              type="primary"
              icon={<UploadOutlined />}
              loading={isSubmitting}
              onClick={handleSubmit}
            >
              {isEditing ? 'Save Changes' : 'Connect Bucket'}
            </Button>
          </div>
        </div>
      </div>
    </Modal>
  );
};
