import { afterEach, beforeEach, vi } from 'vitest'

import { Api } from '../../../shared/api/Api'
import { buildActiveReportItem } from '../reportActiveItem'
import { ReportService } from '../Report.service'
import * as sessionStorage from '../../validation/validationSessionStorage'

vi.mock('../../../shared/api/Api', () => ({
  Api: {
    getValidationQueue: vi.fn(),
    getValidationJob: vi.fn(),
  },
}))

describe('ReportService.fetchActive', () => {
  beforeEach(() => {
    vi.clearAllMocks()
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

  it('keeps sessions when the queue is empty but the job is still running', async () => {
    vi.mocked(Api.getValidationQueue).mockResolvedValue({
      data: { running: 0, pending: 0, jobs: [] },
    } as never)
    vi.mocked(Api.getValidationJob).mockResolvedValue({
      data: { status: 'running' },
    } as never)

    const items = await ReportService.fetchActive()

    expect(items).toHaveLength(1)
    expect(items[0].sourceTitle).toBe('source.csv')
    expect(items[0].jobTitle).toBe('target.csv')
    expect(sessionStorage.setActiveSessions).not.toHaveBeenCalled()
  })

  it('drops completed sessions reported by the queue', async () => {
    vi.mocked(Api.getValidationQueue).mockResolvedValue({
      data: {
        running: 0,
        pending: 0,
        jobs: [{ job_id: 'job-1', state: 'completed', enqueued_at: 1, started_at: 1, finished_at: 2 }],
      },
    } as never)

    const items = await ReportService.fetchActive()

    expect(items).toEqual([])
    expect(sessionStorage.setActiveSessions).toHaveBeenCalledWith([])
    expect(Api.getValidationJob).not.toHaveBeenCalled()
  })

  it('drops completed sessions verified by the job API when absent from queue', async () => {
    vi.mocked(Api.getValidationQueue).mockResolvedValue({
      data: { running: 0, pending: 0, jobs: [] },
    } as never)
    vi.mocked(Api.getValidationJob).mockResolvedValue({
      data: { status: 'completed' },
    } as never)

    const items = await ReportService.fetchActive()

    expect(items).toEqual([])
    expect(sessionStorage.setActiveSessions).toHaveBeenCalledWith([])
  })

  it('keeps pending browser sessions while submit is still in flight', async () => {
    vi.spyOn(sessionStorage, 'getActiveSessions').mockReturnValue([
      {
        jobId: 'pending-123',
        sourcePath: 'gs://bucket/data/source.csv',
        targetPath: 'gs://bucket/data/target.csv',
        sourceFileName: 'source.csv',
        targetFileName: 'target.csv',
        startedAt: Date.now(),
      },
    ])
    vi.mocked(Api.getValidationQueue).mockResolvedValue({
      data: { running: 0, pending: 0, jobs: [] },
    } as never)

    const items = await ReportService.fetchActive()

    expect(items).toHaveLength(1)
    expect(items[0].jobId).toBe('pending-123')
    expect(Api.getValidationJob).not.toHaveBeenCalled()
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
    expect(Api.getValidationJob).not.toHaveBeenCalled()
  })

  it('falls back to browser sessions when the queue API is unavailable', async () => {
    vi.mocked(Api.getValidationQueue).mockRejectedValue(new Error('offline'))

    const items = await ReportService.fetchActive()

    expect(items).toHaveLength(1)
    expect(items[0].sourceTitle).toBe('source.csv')
    expect(items[0].jobTitle).toBe('target.csv')
    expect(sessionStorage.setActiveSessions).not.toHaveBeenCalled()
    expect(Api.getValidationJob).not.toHaveBeenCalled()
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
