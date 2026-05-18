import React from 'react'
import { ReportSection } from './ReportSection'

export function Missing({ samples = [] }) {
  return (
    <ReportSection type="missing_in_target" samples={samples} />
  )
}

export default Missing
