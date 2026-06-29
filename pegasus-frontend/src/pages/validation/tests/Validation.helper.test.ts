import {
  cloudFromPath,
  cloudHasAuth,
  enrichCloudWithConnection,
  formFromHistory,
  parseGsUri,
  validateRequestFromForm,
} from '../validationRerun'
import {
  isValidationsPath,
  parseValidationRoute,
  validationMappingPath,
  validationOverviewPath,
} from '../validationRoutes'
import { mockCloudConnection, mockHistoryDetail, mockSourceCloud, mockTargetCloud, validationFormWithFiles } from '../Validation.mockData'

describe('validationRoutes helpers', () => {
  it('builds overview and mapping paths', () => {
    expect(validationOverviewPath('run-123')).toBe('/validations/overview/run-123')
    expect(validationMappingPath('run-123')).toBe('/validations/mapping/run-123')
  })

  it('parses step 1 route for base validations path', () => {
    expect(parseValidationRoute('/validations')).toEqual({ step: 1, runId: null })
    expect(parseValidationRoute('/validations/')).toEqual({ step: 1, runId: null })
  })

  it('parses overview and mapping routes', () => {
    expect(parseValidationRoute('/validations/overview/run-abc')).toEqual({ step: 2, runId: 'run-abc' })
    expect(parseValidationRoute('/validations/mapping/run-xyz')).toEqual({ step: 3, runId: 'run-xyz' })
  })

  it('detects validations paths', () => {
    expect(isValidationsPath('/validations')).toBe(true)
    expect(isValidationsPath('/validations/overview/run-1')).toBe(true)
    expect(isValidationsPath('/dashboard')).toBe(false)
  })
})

describe('validationRerun helpers', () => {
  it('parses gs:// URIs into cloud config', () => {
    expect(parseGsUri('gs://test-bucket/data/source.csv')).toEqual({
      provider: 'google-cloud-storage',
      bucket: 'test-bucket',
      object_name: 'data/source.csv',
    })
  })

  it('returns null for invalid gs URIs', () => {
    expect(parseGsUri('not-a-uri')).toBeNull()
  })

  it('detects cloud auth from connection id or credentials', () => {
    expect(cloudHasAuth(mockSourceCloud)).toBe(true)
    expect(cloudHasAuth({ provider: 'google-cloud-storage', bucket: 'b', object_name: 'f' })).toBe(false)
  })

  it('enriches cloud config with matching active connection', () => {
    const cloud = { provider: 'google-cloud-storage' as const, bucket: 'test-bucket', object_name: 'data/source.csv' }
    expect(enrichCloudWithConnection(cloud, [mockCloudConnection])).toEqual({
      ...cloud,
      connection_id: 'conn-1',
    })
  })

  it('maps history detail into wizard form fields', () => {
    expect(formFromHistory(mockHistoryDetail)).toMatchObject({
      uidColumn: 'id',
      delimiter: 'auto',
      hasHeader: true,
      sourceFileName: 'source.csv',
      targetFileName: 'target.csv',
    })
  })

  it('builds validate request from form with authenticated cloud refs', () => {
    const request = validateRequestFromForm({
      ...validationFormWithFiles,
      sourceCloud: mockSourceCloud,
      targetCloud: mockTargetCloud,
    })
    expect(request.source_cloud).toEqual(mockSourceCloud)
    expect(request.target_cloud).toEqual(mockTargetCloud)
    expect(request.uid_column).toBe('id')
  })

  it('builds validate request from gs paths when cloud lacks auth', () => {
    const unauthenticatedCloud = {
      provider: 'google-cloud-storage' as const,
      bucket: 'test-bucket',
      object_name: 'data/source.csv',
    }
    const request = validateRequestFromForm({
      ...validationFormWithFiles,
      sourceCloud: unauthenticatedCloud,
      targetCloud: { ...unauthenticatedCloud, object_name: 'data/target.csv' },
    })
    expect(request.source_path).toBe('gs://test-bucket/data/source.csv')
    expect(request.target_path).toBe('gs://test-bucket/data/target.csv')
  })

  it('parses cloud from gs path via cloudFromPath', () => {
    expect(cloudFromPath('gs://test-bucket/data/source.csv')).toEqual({
      provider: 'google-cloud-storage',
      bucket: 'test-bucket',
      object_name: 'data/source.csv',
    })
  })
})
