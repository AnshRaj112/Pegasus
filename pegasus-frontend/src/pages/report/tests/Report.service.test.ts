import { afterEach, beforeEach, vi } from 'vitest'

import { Api } from '../../../shared/api/Api'
import { buildActiveReportItem } from '../reportActiveItem'
import { ReportService } from '../Report.service'
import * as sessionStorage from '../../validation/validationSessionStorage'

vi.mock('../../../shared/api/Api', () => ({
  Api: {
    getValidationQueue: vi.fn(),
  },
}))

describe('ReportService.fetchActive', () => {
  beforeEach(() => {
    vi.spyOn(sessionStorage, 'getActiveSessions').mockReturnValue([
      {
        jobId: 'job-1',
        sourcePath: 'gs://bucket/data/source.csv',
        targetPath: 'gs://bucket/data/target.csv',
        sourceFileName: 'source.csv',
        targetFileName: 'target.csv',
        startedAt: Date.now(),
      },
    ])
    vi.spyOn(sessionStorage, 'setActiveSessions').mockImplementation(() => {})
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('drops stale sessions when the queue reports no active jobs', async () => {
    vi.mocked(Api.getValidationQueue).mockResolvedValue({
      data: { running: 0, pending: 0, jobs: [] },
    } as never)

    const items = await ReportService.fetchActive()

    expect(items).toEqual([])
    expect(sessionStorage.setActiveSessions).toHaveBeenCalledWith([])
  })

  it('drops browser sessions when only unrelated queue jobs remain', async () => {
    vi.mocked(Api.getValidationQueue).mockResolvedValue({
      data: {
        running: 1,
        pending: 0,
        jobs: [{ job_id: 'orphan-job', state: 'running', enqueued_at: 1, started_at: 1, finished_at: null }],
      },
    } as never)

    const items = await ReportService.fetchActive()

    expect(items).toEqual([])
    expect(sessionStorage.setActiveSessions).toHaveBeenCalledWith([])
  })

  it('uses queue state to mark a session as queued', async () => {
    vi.mocked(Api.getValidationQueue).mockResolvedValue({
      data: {
        running: 0,
        pending: 1,
        jobs: [{ job_id: 'job-1', state: 'queued', enqueued_at: 1, started_at: null, finished_at: null }],
      },
    } as never)

    const items = await ReportService.fetchActive()

    expect(items[0].jobSubtitle).toBe('Queued…')
    expect(items[0].badges.some((b) => b.type === 'text' && b.content === 'Queued')).toBe(true)
  })

  it('falls back to browser sessions when the queue API is unavailable', async () => {
    vi.mocked(Api.getValidationQueue).mockRejectedValue(new Error('offline'))

    const items = await ReportService.fetchActive()

    expect(items).toHaveLength(1)
    expect(items[0].sourceTitle).toBe('source.csv')
    expect(items[0].jobTitle).toBe('target.csv')
    expect(sessionStorage.setActiveSessions).not.toHaveBeenCalled()
  })
})

describe('buildActiveReportItem', () => {
  it('preserves explicit file titles', () => {
    const item = buildActiveReportItem({
      jobId: 'job-1',
      sourcePath: 'gs://bucket/source.csv',
      targetPath: 'gs://bucket/target.csv',
      sourceTitle: 'source.csv',
      targetTitle: 'target.csv',
    })

    expect(item.sourceTitle).toBe('source.csv')
    expect(item.jobTitle).toBe('target.csv')
  })
})
