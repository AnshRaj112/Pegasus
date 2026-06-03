import React from 'react'
import { Modal, Button } from 'antd'

interface ParallelValidationModalProps {
  open?: boolean
  onClose?: () => void
  onSubmit?: (config: any) => void
}

export const ParallelValidationModal: React.FC<ParallelValidationModalProps> = ({
  open = false,
  onClose,
  onSubmit,
}) => {
  return (
    <Modal
      open={open}
      title="Parallel Validation"
      onCancel={onClose}
      footer={[
        <Button key="cancel" onClick={onClose}>
          Cancel
        </Button>,
        <Button key="submit" type="primary" onClick={() => onSubmit?.({})} >
          Start Validation
        </Button>,
      ]}
    >
      <div>
        <p>Configure parallel validation settings</p>
      </div>
    </Modal>
  )
}

export default ParallelValidationModal
