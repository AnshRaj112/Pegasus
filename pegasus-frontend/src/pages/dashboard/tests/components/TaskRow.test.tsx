import { render, screen } from '~/utils/renderWithProviders'

import { mockCompletedTask, mockTaskItem } from '../../Dashboard.mockData'
import { TaskRow } from '../../components/TaskRow'

const renderTaskRow = (task: typeof mockTaskItem) =>
  render(
    <table>
      <tbody>
        <TaskRow task={task} />
      </tbody>
    </table>,
  )

describe('TaskRow', () => {
  it('renders task name and time', () => {
    renderTaskRow(mockTaskItem)

    expect(screen.getByText('Validation job-abc1')).toBeInTheDocument()
    expect(screen.getByText('5 mins ago')).toBeInTheDocument()
  })

  it('renders running status with progress label', () => {
    renderTaskRow(mockTaskItem)

    expect(screen.getByText('Running')).toBeInTheDocument()
    expect(screen.getByText('50% Processing')).toBeInTheDocument()
  })

  it('renders completed status badge', () => {
    renderTaskRow(mockCompletedTask)

    expect(screen.getByText('Completed')).toBeInTheDocument()
  })
})
