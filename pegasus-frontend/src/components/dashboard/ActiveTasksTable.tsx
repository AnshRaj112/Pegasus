import React from 'react'
import { Table, Progress, Card, Tag } from 'antd'
import type { ActiveTask } from '../../types'

interface ActiveTasksTableProps {
  tasks: ActiveTask[]
}

export const ActiveTasksTable: React.FC<ActiveTasksTableProps> = ({ tasks }) => {
  const columns = [
    {
      title: 'Task Name',
      dataIndex: 'task_name',
      key: 'task_name',
    },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => {
        const colorMap: Record<string, string> = {
          completed: 'green',
          running: 'blue',
          scheduled: 'orange',
          failed: 'red',
        }
        return <Tag color={colorMap[status]}>{status}</Tag>
      },
    },
    {
      title: 'Progress',
      dataIndex: 'progress',
      key: 'progress',
      render: (progress: number) => <Progress percent={progress} size="small" />,
    },
  ]

  return (
    <Card title="Active Tasks">
      <Table columns={columns} dataSource={tasks} rowKey="task_name" pagination={false} />
    </Card>
  )
}
