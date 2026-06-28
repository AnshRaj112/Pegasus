import { render, screen } from '~/utils/renderWithProviders'

import { mockCompletedTask, mockTaskItem } from '../../Dashboard.mockData'
import { ActiveTasksPanel } from '../../components/ActiveTasksPanel'

describe('ActiveTasksPanel', () => {
  it('renders the panel header with job count', () => {
    render(<ActiveTasksPanel tasks={[mockTaskItem, mockCompletedTask]} />)

    expect(screen.getByRole('heading', { name: 'Active Tasks' })).toBeInTheDocument()
    expect(screen.getByText('2 jobs')).toBeInTheDocument()
  })

  it('renders task rows from provided tasks', () => {
    render(<ActiveTasksPanel tasks={[mockTaskItem, mockCompletedTask]} />)

    expect(screen.getByText('Validation job-abc1')).toBeInTheDocument()
    expect(screen.getByText('Validation job-def6')).toBeInTheDocument()
  })

  it('shows loading meta while fetching', () => {
    render(<ActiveTasksPanel tasks={[]} isLoading />)

    expect(screen.getByText('Loading…')).toBeInTheDocument()
  })

  it('shows empty state when there are no tasks', () => {
    render(<ActiveTasksPanel tasks={[]} />)

    expect(screen.getByText('No validation jobs in queue.')).toBeInTheDocument()
  })
})
