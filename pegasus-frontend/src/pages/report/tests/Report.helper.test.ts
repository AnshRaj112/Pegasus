import {
  decodeReportPairId,
  encodeReportPairId,
  gcsUri,
  pairIdFromPathSegment,
  pairIdToPathSegment,
} from '../reportPairId'

describe('reportPairId helpers', () => {
  it('builds a GCS URI from cloud config', () => {
    expect(
      gcsUri({
        bucket: 'my-bucket',
        object_name: '/folder/file.csv',
        connection_id: 'conn-1',
      }),
    ).toBe('gs://my-bucket/folder/file.csv')
  })

  it('encodes and decodes report pair ids', () => {
    const pairId = encodeReportPairId('/data/source.csv', '/data/target.csv')
    expect(decodeReportPairId(pairId)).toEqual({
      sourcePath: '/data/source.csv',
      targetPath: '/data/target.csv',
    })
  })

  it('round-trips pair ids through URL path segments', () => {
    const pairId = encodeReportPairId('/nested/source.csv', '/nested/target.csv')
    const segment = pairIdToPathSegment(pairId)
    expect(decodeReportPairId(pairIdFromPathSegment(segment))).toEqual({
      sourcePath: '/nested/source.csv',
      targetPath: '/nested/target.csv',
    })
  })

  it('throws when decoding an invalid report pair id', () => {
    expect(() => decodeReportPairId('invalid-pair-id')).toThrow('Invalid report pair id')
  })
})
