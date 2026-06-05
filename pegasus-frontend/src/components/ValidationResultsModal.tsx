import { Button, Col, Modal, Result, Row, Statistic, Space } from 'antd'
import { useNavigate } from 'react-router-dom'
import { CloseOutlined } from '@ant-design/icons'

export default function ValidationResultsModal({ visible, result, onClose, elapsedMs }: any) {
  const navigate = useNavigate()

  const handleViewReport = () => {
    onClose()
    navigate('/report', { state: { result } })
  }

  return (
    <Modal
      title="Validation complete"
      open={visible}
      onCancel={onClose}
      footer={null}
      width={800}
      centered
      closeIcon={<CloseOutlined className="text-xl text-slate-600 hover:text-slate-800" />}
      styles={{ body: { padding: 24 } }}
    >
      <Space direction="vertical" size={24} style={{ width: '100%' }}>
        <Result status="success" title="Finished" subTitle={`${(elapsedMs / 1000).toFixed(1)}s elapsed`} />

        {result ? (
          <Space direction="vertical" size={16} style={{ width: '100%' }}>
            <Row gutter={[16, 16]}>
              <Col xs={24} sm={12} lg={6}><Statistic title="Fully Match" value={result.summary?.is_match ? 'Yes' : 'No'} /></Col>
              <Col xs={24} sm={12} lg={6}><Statistic title="Source Rows" value={result.summary?.source_row_count ?? '-'} /></Col>
              <Col xs={24} sm={12} lg={6}><Statistic title="Target Rows" value={result.summary?.target_row_count ?? '-'} /></Col>
              <Col xs={24} sm={12} lg={6}><Statistic title="Mismatches" value={result.summary?.total_mismatch_records ?? '-'} /></Col>
            </Row>

            <Row gutter={[16, 16]}>
              <Col xs={24} md={8}><Statistic title="Missing in Target" value={result.mismatch_counts?.missing_in_target ?? 0} /></Col>
              <Col xs={24} md={8}><Statistic title="Extra in Target" value={result.mismatch_counts?.extra_in_target ?? 0} /></Col>
              <Col xs={24} md={8}><Statistic title="Value Mismatch" value={result.mismatch_counts?.value_mismatch ?? 0} /></Col>
            </Row>

            {result.run_id ? <div>Run ID: <code>{result.run_id}</code></div> : null}

            {((result.mismatch_samples?.length ?? 0) > 0 || (result.summary?.total_mismatch_records ?? 0) > 0) ? (
              <Button type="primary" size="large" block onClick={handleViewReport}>
                View Detailed Report
              </Button>
            ) : null}
          </Space>
        ) : null}
      </Space>
    </Modal>
  )
}