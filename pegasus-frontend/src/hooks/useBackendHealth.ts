import { useCallback, useEffect, useRef, useState } from 'react'
import { checkBackendHealth } from '../api/http'

const DEFAULT_INTERVAL_MS = 5000

export function useBackendHealth({ intervalMs = DEFAULT_INTERVAL_MS, enabled = true }: { intervalMs?: number; enabled?: boolean } = {}) {
  const [status, setStatus] = useState<'checking' | 'up' | 'down'>('checking')
  const [lastOkAt, setLastOkAt] = useState<number | null>(null)
  const [lastError, setLastError] = useState('')
  const wasUpRef = useRef(false)

  const probe = useCallback(async () => {
    const result = await checkBackendHealth()
    if (result.ok) {
      setStatus('up')
      setLastOkAt(Date.now())
      setLastError('')
      wasUpRef.current = true
      return
    }
    setStatus('down')
    setLastError(result.error || 'Health check failed')
    if (wasUpRef.current) {
      wasUpRef.current = false
    }
  }, [])

  useEffect(() => {
    if (!enabled) return undefined
    probe()
    const id = setInterval(probe, intervalMs)
    return () => clearInterval(id)
  }, [enabled, intervalMs, probe])

  return {
    status,
    isUp: status === 'up',
    isDown: status === 'down',
    lastOkAt,
    lastError,
    refresh: probe,
  }
}
