import { beforeEach, afterEach, vi } from 'vitest'

import {
  adminLogout,
  extendAdminSession,
  fetchAdminMe,
  fetchAdminSessionStatus,
} from '~/shared/api/adminAuth'
import { render, screen, waitFor } from '~/utils/renderWithProviders'

import { AuthSessionManager } from '../AuthSessionManager'
import { authenticatedState } from '../Auth.mockData'

vi.mock('~/shared/api/adminAuth', () => ({
  fetchAdminMe: vi.fn(),
  fetchAdminSessionStatus: vi.fn(),
  adminLogout: vi.fn(),
  extendAdminSession: vi.fn(),
}))

vi.mock('~/pages/validation/resetValidationOnLogout', () => ({
  resetValidationOnLogout: vi.fn(),
}))

const mockFetchAdminMe = vi.mocked(fetchAdminMe)
const mockFetchAdminSessionStatus = vi.mocked(fetchAdminSessionStatus)
const mockAdminLogout = vi.mocked(adminLogout)
const mockExtendAdminSession = vi.mocked(extendAdminSession)

const SESSION_NOW = new Date('2026-06-28T12:00:00.000Z').getTime()
const SESSION_EXPIRING_SOON = '2026-06-28T12:04:00.000Z'
const SESSION_EXTENDED = '2026-06-28T12:34:00.000Z'

describe('AuthSessionManager', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.spyOn(Date, 'now').mockReturnValue(SESSION_NOW)
    mockAdminLogout.mockResolvedValue(undefined)
    mockFetchAdminSessionStatus.mockResolvedValue({
      email: 'admin@pegasus.io',
      expires_at: SESSION_EXTENDED,
    })
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
  })

  it('clears session when bootstrap fetchAdminMe fails', async () => {
    mockFetchAdminMe.mockRejectedValue(new Error('Unauthorized'))

    const { store } = render(<AuthSessionManager />)

    await waitFor(() => {
      expect(store.getState().auth.isAuthenticated).toBe(false)
      expect(store.getState().auth.user).toBeNull()
    })
  })

  it('shows session expiry modal when remaining time is within warning window', async () => {
    mockFetchAdminMe.mockResolvedValue({ email: 'admin@pegasus.io' })
    mockFetchAdminSessionStatus.mockResolvedValue({
      email: 'admin@pegasus.io',
      expires_at: SESSION_EXPIRING_SOON,
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

    expect(screen.getByRole('button', { name: /extend 30 minutes/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /^logout$/i })).toBeInTheDocument()
  })

  it('extends session when extend button is clicked', async () => {
    mockFetchAdminMe.mockResolvedValue({ email: 'admin@pegasus.io' })
    mockFetchAdminSessionStatus.mockResolvedValue({
      email: 'admin@pegasus.io',
      expires_at: SESSION_EXPIRING_SOON,
    })
    mockExtendAdminSession.mockResolvedValue({
      email: 'admin@pegasus.io',
      expires_at: SESSION_EXTENDED,
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

    screen.getByRole('button', { name: /extend 30 minutes/i }).click()

    await waitFor(() => {
      expect(mockExtendAdminSession).toHaveBeenCalled()
    })
  })

  it('logs out when logout is clicked on the expiry modal', async () => {
    mockFetchAdminMe.mockResolvedValue({ email: 'admin@pegasus.io' })
    mockFetchAdminSessionStatus.mockResolvedValue({
      email: 'admin@pegasus.io',
      expires_at: SESSION_EXPIRING_SOON,
    })

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
