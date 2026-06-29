import { render, screen } from '~/utils/renderWithProviders'

import Profile from '../Profile'

describe('Profile', () => {
  it('renders the profile page heading and sections', () => {
    render(<Profile />)

    expect(screen.getByRole('heading', { name: 'Profile', level: 1 })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'User Details', level: 2 })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Password', level: 2 })).toBeInTheDocument()
  })

  it('renders user detail field labels', () => {
    render(<Profile />)

    expect(screen.getByText('First Name')).toBeInTheDocument()
    expect(screen.getByText('Last Name')).toBeInTheDocument()
    expect(screen.getByText('User Name')).toBeInTheDocument()
    expect(screen.getByText('Email')).toBeInTheDocument()
    expect(screen.getByText('Role')).toBeInTheDocument()
    expect(screen.getByText('Assigned Workspaces')).toBeInTheDocument()
    expect(screen.getByText('Last Login Time')).toBeInTheDocument()
    expect(screen.getByText('Organization')).toBeInTheDocument()
    expect(screen.getByText('Team')).toBeInTheDocument()
    expect(screen.getByText('Location')).toBeInTheDocument()
  })

  it('displays profile values from the current user data', () => {
    render(<Profile />)

    expect(screen.getByText('Super User')).toBeInTheDocument()
    expect(screen.getAllByText('superuser@onixnet.com')).toHaveLength(2)
    expect(screen.getByText('ADMINISTRATOR')).toBeInTheDocument()
    expect(screen.getByText('PELICAN')).toBeInTheDocument()
    expect(screen.getByText('2026-06-12 11:47:03')).toBeInTheDocument()
  })

  it('shows the LOCAL badge for local users', () => {
    render(<Profile />)

    expect(screen.getByText('LOCAL')).toBeInTheDocument()
  })

  it('renders the reset password button', () => {
    render(<Profile />)

    expect(screen.getByRole('button', { name: /reset password/i })).toBeInTheDocument()
  })

  it('renders the profile footer', () => {
    render(<Profile />)

    expect(
      screen.getByText('© 2026 Pegasus Systems • Administrative Profile Management Interface'),
    ).toBeInTheDocument()
  })
})
