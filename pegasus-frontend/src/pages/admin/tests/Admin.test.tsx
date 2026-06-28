import { beforeEach, vi } from 'vitest'

import { fetchAdminMe } from '~/shared/api/adminAuth'
import { render, screen, waitFor } from '~/utils/renderWithProviders'

import AdminView from '../AdminView'

vi.mock('~/shared/api/adminAuth', () => ({
  fetchAdminMe: vi.fn(),
  adminLogout: vi.fn(),
}))

vi.mock('~/pages/validation/resetValidationOnLogout', () => ({
  resetValidationOnLogout: vi.fn(),
}))

const mockFetchAdminMe = vi.mocked(fetchAdminMe)

describe('AdminView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows a loading spinner while checking the admin session', () => {
    mockFetchAdminMe.mockReturnValue(new Promise(() => {}))
    const { container } = render(<AdminView />, { route: '/admin/workspace-management' })
    expect(container.querySelector('.ant-spin')).toBeInTheDocument()
  })

  it('renders the admin shell after session is verified', async () => {
    mockFetchAdminMe.mockResolvedValue({ email: 'admin@pegasus.io' })
    render(<AdminView />, { route: '/admin/workspace-management' })

    await waitFor(() => {
      expect(screen.getByText('Admin Center')).toBeInTheDocument()
    })

    expect(screen.getByText('admin@pegasus.io')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /workspace management/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /configure store/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /configure settings/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /admin sign out/i })).toBeInTheDocument()
  })

  it('renders navigation without email when session check fails', async () => {
    mockFetchAdminMe.mockRejectedValue(new Error('Unauthorized'))
    render(<AdminView />, { route: '/admin/workspace-management' })

    await waitFor(() => {
      expect(screen.getByText('Admin Center')).toBeInTheDocument()
    })

    expect(screen.queryByText('admin@pegasus.io')).not.toBeInTheDocument()
  })
})
