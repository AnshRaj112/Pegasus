import React from 'react'
import { ReportSection } from './ReportSection'

export function Extra({ samples = [] }) {
  return (
    <ReportSection type="extra_in_target" samples={samples} />
  )
}

export default Extra