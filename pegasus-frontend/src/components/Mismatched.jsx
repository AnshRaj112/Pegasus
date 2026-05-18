import React from 'react'
import { ReportSection } from './ReportSection'

export function Mismatched({ samples = [] }) {
  return (
    <ReportSection type="mismatched" samples={samples} />
  )
}

export default Mismatched
