import React, { useEffect, useState } from 'react';
import { Modal, Input, Upload, Button } from 'antd';
import { GoogleOutlined, UploadOutlined, InboxOutlined } from '@ant-design/icons';
import { type CreateStorageProviderPayload } from '../Admin.interface';
import styles from '../Admin.module.scss';

const { TextArea } = Input;
const { Dragger } = Upload;

interface ConnectStorageModalProps {
  open: boolean;
  isSubmitting: boolean;
  error: string | null;
  onClose: () => void;
  onSubmit: (payload: CreateStorageProviderPayload) => void;
  onClearError: () => void;
}

const parseCredentialsJson = (raw: string): { valid: boolean; projectId?: string; error?: string } => {
  const trimmed = raw.trim();
  if (!trimmed) return { valid: false, error: 'Service account JSON is required.' };
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
  onClose,
  onSubmit,
  onClearError,
}) => {
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
    }
  }, [open, onClearError]);

  const handleJsonFile = (file: File) => {
    const reader = new FileReader();
    reader.onload = (event) => {
      const text = String(event.target?.result ?? '');
      setCredentialsJson(text);
      setFileName(file.name);
      const parsed = parseCredentialsJson(text);
      if (parsed.valid && parsed.projectId && !projectId.trim()) {
        setProjectId(parsed.projectId);
      }
      setLocalError(parsed.valid ? null : parsed.error ?? null);
    };
    reader.readAsText(file);
    return false;
  };

  const handleSubmit = () => {
    if (!name.trim()) {
      setLocalError('Connection name is required.');
      return;
    }
    if (!bucket.trim()) {
      setLocalError('Bucket name is required.');
      return;
    }
    const jsonCheck = parseCredentialsJson(credentialsJson);
    if (!jsonCheck.valid) {
      setLocalError(jsonCheck.error ?? 'Invalid credentials JSON.');
      return;
    }

    setLocalError(null);
    onSubmit({
      name: name.trim(),
      bucket: bucket.trim().replace(/^gs:\/\//, ''),
      projectId: projectId.trim() || jsonCheck.projectId,
      credentialsJson: credentialsJson.trim(),
      provider: 'google-cloud-storage',
    });
  };

  const displayError = localError ?? error;

  return (
    <Modal
      title="Connect Storage Bucket"
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
            GCS bucket name
            <Input
              value={bucket}
              onChange={(e) => setBucket(e.target.value)}
              placeholder="my-company-data-bucket"
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

          <label className={styles.connectLabel}>
            Service account JSON
            <Dragger
              accept=".json,application/json"
              showUploadList={false}
              beforeUpload={handleJsonFile}
              disabled={isSubmitting}
              className={styles.jsonDragger}
            >
              <p className="ant-upload-drag-icon">
                <InboxOutlined />
              </p>
              <p className="ant-upload-text">Drop your service account key here, or click to browse</p>
              <p className="ant-upload-hint">
                {fileName ? `Loaded: ${fileName}` : 'Download from Google Cloud Console → IAM → Service Accounts → Keys'}
              </p>
            </Dragger>
          </label>

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
              placeholder='{"type": "service_account", "project_id": "...", ...}'
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
              Connect Bucket
            </Button>
          </div>
        </div>
      </div>
    </Modal>
  );
};
