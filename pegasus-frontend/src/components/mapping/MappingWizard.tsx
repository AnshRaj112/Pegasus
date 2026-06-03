import React, { useState } from 'react'
import { Card, Steps, Button, Space, message } from 'antd'
import { ArrowRight, ArrowLeft } from 'lucide-react'

interface MappingWizardProps {
  onComplete?: (config: any) => void
  onCancel?: () => void
}

export const MappingWizard: React.FC<MappingWizardProps> = ({ onComplete, onCancel }) => {
  const [current, setCurrent] = useState(0)

  const steps = [
    { title: 'Data Source', description: 'Select source' },
    { title: 'File Picker', description: 'Choose files' },
    { title: 'Configure', description: 'Map columns' },
  ]

  const next = () => {
    if (current < steps.length - 1) {
      setCurrent(current + 1)
    } else {
      message.success('Mapping configuration complete')
      onComplete?.({})
    }
  }

  const prev = () => {
    setCurrent(Math.max(0, current - 1))
  }

  return (
    <Card>
      <Steps current={current} items={steps} style={{ marginBottom: '24px' }} />
      <div style={{ minHeight: '400px', padding: '24px', background: '#f9fafb', borderRadius: '8px' }}>
        {current === 0 && <div>Step 1: Select data source</div>}
        {current === 1 && <div>Step 2: Choose files to map</div>}
        {current === 2 && <div>Step 3: Configure column mappings</div>}
      </div>
      <Space style={{ marginTop: '24px', justifyContent: 'flex-end', width: '100%' }}>
        <Button onClick={prev} icon={<ArrowLeft size={14} />} disabled={current === 0}>
          Back
        </Button>
        <Button type="primary" onClick={next} icon={<ArrowRight size={14} />}>
          {current === steps.length - 1 ? 'Complete' : 'Next'}
        </Button>
      </Space>
    </Card>
  )
}

export default MappingWizard
