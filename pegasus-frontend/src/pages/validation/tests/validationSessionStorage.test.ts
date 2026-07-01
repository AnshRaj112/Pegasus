import { afterEach, vi } from 'vitest'

import {
  getActiveSessions,
  replaceActiveSessionJobId,
  upsertActiveSession,
  clearAllActiveSessions,
} from '../validationSessionStorage'

describe('validationSessionStorage', () => {
  afterEach(() => {
    clearAllActiveSessions()
    vi.restoreAllMocks()
  })

  it('replaces a pending session job id without dropping file metadata', () => {
    upsertActiveSession({
      jobId: 'pending-1',
      sourcePath: 'gs://bucket/source.csv',
      targetPath: 'gs://bucket/target.csv',
      sourceFileName: 'source.csv',
      targetFileName: 'target.csv',
      startedAt: Date.now(),
    })

    replaceActiveSessionJobId('pending-1', 'real-job-1')

    const sessions = getActiveSessions()
    expect(sessions).toHaveLength(1)
    expect(sessions[0].jobId).toBe('real-job-1')
    expect(sessions[0].sourceFileName).toBe('source.csv')
    expect(sessions[0].targetFileName).toBe('target.csv')
  })
})
