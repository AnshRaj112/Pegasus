import React, { useState } from 'react'
import { Card, Button, Space, message } from 'antd'
import { ArrowRight } from 'lucide-react'

export default function ConfigureMappingPage() {
  const [loading, setLoading] = useState(false)

  const handleProceed = async () => {
    try {
      setLoading(true)
      // TODO: Implement mapping configuration logic
      message.success('Mapping configured successfully')
    } catch (error) {
      message.error('Failed to configure mapping')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ padding: '24px' }}>
      <Card title="Configure Mapping" style={{ maxWidth: '1200px', margin: '0 auto' }}>
        <div style={{ textAlign: 'center', padding: '60px 20px' }}>
          <h3>Mapping Configuration</h3>
          <p style={{ color: '#666', marginTop: '16px' }}>
            Configure column mappings from source to target files
          </p>
          <Space style={{ marginTop: '24px' }}>
            <Button type="primary" size="large" onClick={handleProceed} loading={loading}>
              <ArrowRight size={16} /> Proceed
            </Button>
          </Space>
        </div>
      </Card>
    </div>
  )
}
