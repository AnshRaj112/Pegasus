import { fileDisplayName } from '../reportActiveItem'
import { mockSourceCloud } from '../../validation/Validation.mockData'

describe('fileDisplayName', () => {
  it('prefers the selected file name from the form', () => {
    expect(fileDisplayName('source.csv', mockSourceCloud, 'gs://test-bucket/data/source.csv')).toBe('source.csv')
  })

  it('falls back to the cloud object name', () => {
    expect(fileDisplayName(null, mockSourceCloud, 'gs://test-bucket/data/source.csv')).toBe('source.csv')
  })

  it('falls back to the path basename', () => {
    expect(fileDisplayName(null, null, 'gs://test-bucket/data/source.csv')).toBe('source.csv')
  })
})
