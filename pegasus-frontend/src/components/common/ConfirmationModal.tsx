import React from 'react'
import { Modal, Button, Space } from 'antd'

interface ConfirmationModalProps {
  open?: boolean
  title?: string
  message?: string
  confirmText?: string
  cancelText?: string
  loading?: boolean
  onConfirm?: () => void
  onCancel?: () => void
  isDangerous?: boolean
}

export const ConfirmationModal: React.FC<ConfirmationModalProps> = ({
  open = false,
  title = 'Confirm',
  message = 'Are you sure?',
  confirmText = 'Confirm',
  cancelText = 'Cancel',
  loading = false,
  onConfirm,
  onCancel,
  isDangerous = false,
}) => {
  return (
    <Modal
      open={open}
      title={title}
      onCancel={onCancel}
      footer={[
        <Button key="cancel" onClick={onCancel}>
          {cancelText}
        </Button>,
        <Button
          key="confirm"
          type={isDangerous ? 'primary' : 'default'}
          danger={isDangerous}
          onClick={onConfirm}
          loading={loading}
        >
          {confirmText}
        </Button>,
      ]}
    >
      <p>{message}</p>
    </Modal>
  )
}
