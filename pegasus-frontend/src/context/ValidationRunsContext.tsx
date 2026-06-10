import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import { pollValidationJobDetail } from '../api/validationPoll.js'
import { fetchValidationQueue } from '../api/validationQueue.js'
import { notifyValidationComplete, requestNotificationPermission } from '../utils/notifications.js'

const pollTimeoutRaw = Number(import.meta.env.VITE_VALIDATION_POLL_TIMEOUT_MS ?? 0)
const pollTimeoutMs = Number.isFinite(pollTimeoutRaw) ? pollTimeoutRaw : 0
const POLL_INTERVAL_MS = 400

export type ValidationRunStatus = 'queued' | 'running' | 'completed' | 'failed'
export type ValidationRunOutcome = 'passed' | 'mismatches' | 'failed' | null

export type ValidationRunRecord = {
  id: string
  jobId: string
  pollUrl: string
  sourceLabel: string
  targetLabel: string
  status: ValidationRunStatus
  outcome: ValidationRunOutcome
  phase?: string
  message?: string
  progress?: Record<string, unknown>
  resourceProfile?: Record<string, unknown>
  result?: unknown
  batchResult?: unknown
  error?: string
  submittedAt: number
  completedAt?: number
  isMatch?: boolean
}

type StartRunInput = {
  jobId: string
  pollUrl: string
  sourceLabel: string
  targetLabel: string
  initialStatus?: ValidationRunStatus
}

type ValidationRunsContextValue = {
  runs: ValidationRunRecord[]
  activeCount: number
  startRun: (input: StartRunInput) => string
  dismissRun: (id: string) => void
  focusRun: (id: string) => void
  focusedRunId: string | null
  focusedRun: ValidationRunRecord | null
  refreshQueue: () => Promise<void>
  queueSnapshot: Record<string, unknown> | null
}

const ValidationRunsContext = createContext<ValidationRunsContextValue | null>(null)

function basename(path: string) {
  const normalized = String(path || '').replace(/\\/g, '/')
  const parts = normalized.split('/')
  return parts[parts.length - 1] || normalized || 'file'
}

function deriveMatch(payload: Record<string, unknown>) {
  if (payload.batch_result && typeof payload.batch_result === 'object') {
    const summary = (payload.batch_result as { summary?: { is_match?: boolean } }).summary
    return summary?.is_match === true
  }
  if (payload.result && typeof payload.result === 'object') {
    const summary = (payload.result as { summary?: { is_match?: boolean } }).summary
    return summary?.is_match === true
  }
  return false
}

function normalizeRunStatus(raw: unknown): ValidationRunStatus {
  const status = String(raw || '').toLowerCase()
  if (status === 'queued') return 'queued'
  if (status === 'running' || status === 'updating') return 'running'
  if (status === 'completed') return 'completed'
  if (status === 'failed') return 'failed'
  return 'running'
}

function deriveOutcome(
  status: ValidationRunStatus,
  isMatch: boolean,
): ValidationRunOutcome {
  if (status === 'failed') return 'failed'
  if (status === 'completed') return isMatch ? 'passed' : 'mismatches'
  return null
}

export function ValidationRunsProvider({ children }: { children: ReactNode }) {
  const [runs, setRuns] = useState<ValidationRunRecord[]>([])
  const [focusedRunId, setFocusedRunId] = useState<string | null>(null)
  const [queueSnapshot, setQueueSnapshot] = useState<Record<string, unknown> | null>(null)
  const pollingRef = useRef(new Set<string>())
  const notifiedRef = useRef(new Set<string>())

  const updateRun = useCallback((id: string, patch: Partial<ValidationRunRecord>) => {
    setRuns((prev) => prev.map((run) => (run.id === id ? { ...run, ...patch } : run)))
  }, [])

  const pollRun = useCallback(async (run: ValidationRunRecord) => {
    if (pollingRef.current.has(run.id)) return
    pollingRef.current.add(run.id)
    try {
      const payload = await pollValidationJobDetail(run.pollUrl, {
        timeoutMs: pollTimeoutMs,
        intervalMs: POLL_INTERVAL_MS,
        onPoll: (detail) => {
          const status = normalizeRunStatus(detail?.status)
          updateRun(run.id, {
            status,
            outcome: null,
            phase: typeof detail?.phase === 'string' ? detail.phase : undefined,
            message: typeof detail?.message === 'string' ? detail.message : undefined,
            progress: detail?.progress && typeof detail.progress === 'object'
              ? detail.progress as Record<string, unknown>
              : undefined,
            resourceProfile: detail?.resource_profile && typeof detail.resource_profile === 'object'
              ? detail.resource_profile as Record<string, unknown>
              : undefined,
          })
        },
      })

      const status = normalizeRunStatus(payload?.status || 'completed')
      const isMatch = deriveMatch(payload as Record<string, unknown>)
      const outcome = deriveOutcome(status, isMatch)
      const completedAt = Date.now()
      updateRun(run.id, {
        status,
        outcome,
        phase: typeof payload?.phase === 'string' ? payload.phase : 'completed',
        message: typeof payload?.message === 'string' ? payload.message : undefined,
        progress: payload?.progress && typeof payload.progress === 'object'
          ? payload.progress as Record<string, unknown>
          : undefined,
        resourceProfile: payload?.resource_profile && typeof payload.resource_profile === 'object'
          ? payload.resource_profile as Record<string, unknown>
          : undefined,
        result: payload?.result,
        batchResult: payload?.batch_result,
        completedAt,
        isMatch,
        error: status === 'failed'
          ? String(payload?.error || payload?.message || 'Validation job failed')
          : undefined,
      })

      if (!notifiedRef.current.has(run.id)) {
        notifiedRef.current.add(run.id)
        const label = `${basename(run.sourceLabel)} → ${basename(run.targetLabel)}`
        const title = status === 'failed'
          ? 'Validation job failed'
          : isMatch
            ? 'Validation passed'
            : 'Validation complete — mismatches found'
        notifyValidationComplete({
          title,
          body: status === 'failed'
            ? `${label}: ${String(payload?.error || payload?.message || 'worker error')}`
            : `${label} ${isMatch ? 'passed with no mismatches' : 'finished with mismatch records'}`,
          isMatch,
        })
      }
    } catch (error) {
      updateRun(run.id, {
        status: 'failed',
        outcome: 'failed',
        phase: 'failed',
        error: error instanceof Error ? error.message : String(error),
        completedAt: Date.now(),
      })
      if (!notifiedRef.current.has(run.id)) {
        notifiedRef.current.add(run.id)
        notifyValidationComplete({
          title: 'Validation job failed',
          body: `${basename(run.sourceLabel)} → ${basename(run.targetLabel)}`,
          isMatch: false,
        })
      }
    } finally {
      pollingRef.current.delete(run.id)
    }
  }, [updateRun])

  const startRun = useCallback((input: StartRunInput) => {
    const id = `${input.jobId}-${Date.now()}`
    const initialStatus = input.initialStatus === 'running' ? 'running' : 'queued'
    const run: ValidationRunRecord = {
      id,
      jobId: input.jobId,
      pollUrl: input.pollUrl,
      sourceLabel: input.sourceLabel,
      targetLabel: input.targetLabel,
      status: initialStatus,
      outcome: null,
      phase: initialStatus,
      submittedAt: Date.now(),
    }
    setRuns((prev) => [run, ...prev])
    setFocusedRunId(id)
    void requestNotificationPermission()
    void pollRun(run)
    return id
  }, [pollRun])

  const dismissRun = useCallback((id: string) => {
    setRuns((prev) => prev.filter((run) => run.id !== id))
    setFocusedRunId((current) => (current === id ? null : current))
  }, [])

  const focusRun = useCallback((id: string) => {
    setFocusedRunId(id)
  }, [])

  const refreshQueue = useCallback(async () => {
    try {
      const data = await fetchValidationQueue()
      setQueueSnapshot(data && typeof data === 'object' ? data as Record<string, unknown> : null)
    } catch {
      setQueueSnapshot(null)
    }
  }, [])

  useEffect(() => {
    void refreshQueue()
    const timer = window.setInterval(() => { void refreshQueue() }, 5000)
    return () => window.clearInterval(timer)
  }, [refreshQueue])

  const activeCount = useMemo(
    () => runs.filter((run) => run.status === 'queued' || run.status === 'running').length,
    [runs],
  )

  const focusedRun = useMemo(
    () => runs.find((run) => run.id === focusedRunId) ?? null,
    [runs, focusedRunId],
  )

  const value = useMemo(
    () => ({
      runs,
      activeCount,
      startRun,
      dismissRun,
      focusRun,
      focusedRunId,
      focusedRun,
      refreshQueue,
      queueSnapshot,
    }),
    [runs, activeCount, startRun, dismissRun, focusRun, focusedRunId, focusedRun, refreshQueue, queueSnapshot],
  )

  return (
    <ValidationRunsContext.Provider value={value}>
      {children}
    </ValidationRunsContext.Provider>
  )
}

export function useValidationRuns() {
  const ctx = useContext(ValidationRunsContext)
  if (!ctx) {
    throw new Error('useValidationRuns must be used within ValidationRunsProvider')
  }
  return ctx
}
