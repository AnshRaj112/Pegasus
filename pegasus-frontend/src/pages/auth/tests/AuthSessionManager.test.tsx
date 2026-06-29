import { beforeEach, afterEach, vi } from 'vitest'

import {
  adminLogout,
  extendAdminSession,
  fetchAdminMe,
} from '~/shared/api/adminAuth'
import {
  getLastSessionActivityMs,
  resetSessionActivity,
} from '~/shared/api/sessionActivity'
import { render, screen, waitFor } from '~/utils/renderWithProviders'

import { AuthSessionManager } from '../AuthSessionManager'
import { authenticatedState } from '../Auth.mockData'

vi.mock('~/shared/api/adminAuth', () => ({
  fetchAdminMe: vi.fn(),
  adminLogout: vi.fn(),
  extendAdminSession: vi.fn(),
}))

vi.mock('~/shared/api/sessionActivity', () => ({
  getLastSessionActivityMs: vi.fn(),
  resetSessionActivity: vi.fn(),
  registerSessionExtender: vi.fn(),
}))

vi.mock('~/pages/validation/resetValidationOnLogout', () => ({
  resetValidationOnLogout: vi.fn(),
}))

const mockFetchAdminMe = vi.mocked(fetchAdminMe)
const mockAdminLogout = vi.mocked(adminLogout)
const mockExtendAdminSession = vi.mocked(extendAdminSession)
const mockGetLastSessionActivityMs = vi.mocked(getLastSessionActivityMs)
const mockResetSessionActivity = vi.mocked(resetSessionActivity)

const SESSION_NOW = new Date('2026-06-28T12:00:00.000Z').getTime()
const INACTIVITY_MS = 15 * 60 * 1000

describe('AuthSessionManager', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.spyOn(Date, 'now').mockReturnValue(SESSION_NOW)
    mockAdminLogout.mockResolvedValue(undefined)
    mockGetLastSessionActivityMs.mockReturnValue(SESSION_NOW)
    mockResetSessionActivity.mockImplementation(() => {})
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('sets session when bootstrap fetchAdminMe succeeds', async () => {
    mockFetchAdminMe.mockResolvedValue({ email: 'admin@pegasus.io' })

    const { store } = render(<AuthSessionManager />)

    await waitFor(() => {
      expect(store.getState().auth.isAuthenticated).toBe(true)
      expect(store.getState().auth.user?.email).toBe('admin@pegasus.io')
    })
    expect(mockResetSessionActivity).toHaveBeenCalled()
  })

  it('clears session when bootstrap fetchAdminMe fails', async () => {
    mockFetchAdminMe.mockRejectedValue(new Error('Unauthorized'))

    const { store } = render(<AuthSessionManager />)

    await waitFor(() => {
      expect(store.getState().auth.isAuthenticated).toBe(false)
      expect(store.getState().auth.user).toBeNull()
    })
  })

  it('shows session expiry modal after 15 minutes of inactivity', async () => {
    mockFetchAdminMe.mockResolvedValue({ email: 'admin@pegasus.io' })
    mockGetLastSessionActivityMs.mockReturnValue(SESSION_NOW - INACTIVITY_MS)

    render(<AuthSessionManager />, {
      preloadedState: {
        auth: {
          ...authenticatedState,
          isFetching: false,
        },
      },
    })

    await waitFor(() => {
      expect(screen.getByText('Session expiring soon')).toBeInTheDocument()
    })

    expect(screen.getByRole('button', { name: /extend session/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /^logout$/i })).toBeInTheDocument()
  })

  it('extends session when extend button is clicked', async () => {
    mockFetchAdminMe.mockResolvedValue({ email: 'admin@pegasus.io' })
    mockGetLastSessionActivityMs.mockReturnValue(SESSION_NOW - INACTIVITY_MS)
    mockExtendAdminSession.mockResolvedValue({
      email: 'admin@pegasus.io',
      expires_at: '2026-06-28T12:34:00.000Z',
    })

    render(<AuthSessionManager />, {
      preloadedState: {
        auth: {
          ...authenticatedState,
          isFetching: false,
        },
      },
    })

    await waitFor(() => {
      expect(screen.getByText('Session expiring soon')).toBeInTheDocument()
    })

    screen.getByRole('button', { name: /extend session/i }).click()

    await waitFor(() => {
      expect(mockExtendAdminSession).toHaveBeenCalled()
    })
  })

  it('logs out when logout is clicked on the expiry modal', async () => {
    mockFetchAdminMe.mockResolvedValue({ email: 'admin@pegasus.io' })
    mockGetLastSessionActivityMs.mockReturnValue(SESSION_NOW - INACTIVITY_MS)

    const { store } = render(<AuthSessionManager />, {
      preloadedState: {
        auth: {
          ...authenticatedState,
          isFetching: false,
        },
      },
    })

    await waitFor(() => {
      expect(screen.getByText('Session expiring soon')).toBeInTheDocument()
    })

    screen.getByRole('button', { name: /^logout$/i }).click()

    await waitFor(() => {
      expect(mockAdminLogout).toHaveBeenCalled()
      expect(store.getState().auth.isAuthenticated).toBe(false)
    })
  })
})
