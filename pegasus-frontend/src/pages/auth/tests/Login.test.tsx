import userEvent from '@testing-library/user-event'
import { beforeEach, vi } from 'vitest'

import { adminLogin } from '~/shared/api/adminAuth'
import { PATHS } from '~/router/router.constants'
import { render, screen, waitFor } from '~/utils/renderWithProviders'

import Login from '../Login'

const mockNavigate = vi.fn()

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  }
})

vi.mock('~/shared/api/adminAuth', () => ({
  adminLogin: vi.fn(),
}))

const mockAdminLogin = vi.mocked(adminLogin)

describe('Login', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the login form with required fields', () => {
    render(<Login />)

    expect(screen.getByText('Pegasus')).toBeInTheDocument()
    expect(screen.getByTestId('login-form')).toBeInTheDocument()
    expect(screen.getByTestId('input-email')).toBeInTheDocument()
    expect(screen.getByTestId('input-password')).toBeInTheDocument()
    expect(screen.getByTestId('btn-submit-login')).toBeInTheDocument()
    expect(screen.getByTestId('btn-toggle-password')).toBeInTheDocument()
  })

  it('shows placeholder text on email and password inputs', () => {
    render(<Login />)

    expect(screen.getByPlaceholderText('User')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('Password')).toBeInTheDocument()
  })

  it('toggles password visibility when the eye button is clicked', async () => {
    const user = userEvent.setup()
    render(<Login />)

    const passwordInput = screen.getByTestId('input-password')
    expect(passwordInput).toHaveAttribute('type', 'password')

    await user.click(screen.getByTestId('btn-toggle-password'))
    expect(passwordInput).toHaveAttribute('type', 'text')

    await user.click(screen.getByTestId('btn-toggle-password'))
    expect(passwordInput).toHaveAttribute('type', 'password')
  })

  it('dispatches setSession and navigates to dashboard on successful login', async () => {
    const user = userEvent.setup()
    mockAdminLogin.mockResolvedValue({ email: 'admin@pegasus.io' })

    const { store } = render(<Login />)

    await user.type(screen.getByTestId('input-email'), 'admin@pegasus.io')
    await user.type(screen.getByTestId('input-password'), 'secret-password')
    await user.click(screen.getByTestId('btn-submit-login'))

    await waitFor(() => {
      expect(mockAdminLogin).toHaveBeenCalledWith('admin@pegasus.io', 'secret-password')
    })

    expect(store.getState().auth.isAuthenticated).toBe(true)
    expect(store.getState().auth.user?.email).toBe('admin@pegasus.io')
    expect(mockNavigate).toHaveBeenCalledWith(PATHS.DASHBOARD)
  })

  it('shows an error message when login fails', async () => {
    const user = userEvent.setup()
    mockAdminLogin.mockRejectedValue(new Error('Invalid credentials'))

    render(<Login />)

    await user.type(screen.getByTestId('input-email'), 'admin@pegasus.io')
    await user.type(screen.getByTestId('input-password'), 'wrong-password')
    await user.click(screen.getByTestId('btn-submit-login'))

    await waitFor(() => {
      expect(screen.getByTestId('login-error-message')).toHaveTextContent('Invalid credentials')
    })

    expect(mockNavigate).not.toHaveBeenCalled()
  })

  it('disables submit button while login is in progress', async () => {
    const user = userEvent.setup()
    mockAdminLogin.mockReturnValue(new Promise(() => {}))

    render(<Login />)

    await user.type(screen.getByTestId('input-email'), 'admin@pegasus.io')
    await user.type(screen.getByTestId('input-password'), 'secret-password')
    await user.click(screen.getByTestId('btn-submit-login'))

    await waitFor(() => {
      expect(screen.getByTestId('btn-submit-login')).toBeDisabled()
      expect(screen.getByTestId('btn-submit-login')).toHaveTextContent('Signing in...')
    })
  })
})
