import { render, screen } from '~/utils/renderWithProviders'

import { mockEntityInsight, mockEntityInsightBeta } from '../../Dashboard.mockData'
import { WorkspacesPanel } from '../../components/WorkspacesPanel'

describe('WorkspacesPanel', () => {
  it('renders the panel header with entity count', () => {
    render(<WorkspacesPanel entities={[mockEntityInsight, mockEntityInsightBeta]} />)

    expect(screen.getByRole('heading', { name: 'Workspaces' })).toBeInTheDocument()
    expect(screen.getByText('2 entities')).toBeInTheDocument()
  })

  it('renders the global workspace and entity cards', () => {
    render(<WorkspacesPanel entities={[mockEntityInsight, mockEntityInsightBeta]} />)

    expect(screen.getByText('Global Workspace')).toBeInTheDocument()
    expect(screen.getByText('System Default')).toBeInTheDocument()
    expect(screen.getByText('Acme Corp')).toBeInTheDocument()
    expect(screen.getByText('Beta Inc')).toBeInTheDocument()
  })

  it('shows pass rate for entities', () => {
    render(<WorkspacesPanel entities={[mockEntityInsight, mockEntityInsightBeta]} />)

    expect(screen.getByText('80%')).toBeInTheDocument()
    expect(screen.getByText('50%')).toBeInTheDocument()
  })

  it('shows loading meta while fetching', () => {
    render(<WorkspacesPanel entities={[]} isLoading />)

    expect(screen.getByText('Loading…')).toBeInTheDocument()
  })

  it('shows empty hint when no entities exist', () => {
    render(<WorkspacesPanel entities={[]} />)

    expect(
      screen.getByText('No entity insights yet. Run validations to infer entities from filenames.'),
    ).toBeInTheDocument()
  })
})
