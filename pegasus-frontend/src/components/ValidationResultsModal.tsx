import React from 'react'
import { Modal, Button } from 'antd'

interface ValidationResultsModalProps {
  open?: boolean
  results?: any
  onClose?: () => void
}

export const ValidationResultsModal: React.FC<ValidationResultsModalProps> = ({
  open = false,
  results,
  onClose,
}) => {
  return (
    <Modal
      open={open}
      title="Validation Results"
      onCancel={onClose}
      footer={[
        <Button key="close" type="primary" onClick={onClose}>
          Close
        </Button>,
      ]}
    >
      <div>
        <p>Validation completed successfully</p>
        {results && (
          <div style={{ marginTop: '16px', padding: '12px', background: '#f0f9ff', borderRadius: '8px' }}>
            <code>{JSON.stringify(results, null, 2)}</code>
          </div>
        )}
      </div>
    </Modal>
  )
}

export default ValidationResultsModal
