// Project objects as the backend sends them (contracts/projects-api.md).
export const RAW_PROJECT = {
  id: '11111111-1111-4111-8111-111111111111',
  title: 'My Todo App',
  description: '할 일 앱 만들기' as string | null,
  created_at: '2026-11-09T03:00:00+00:00',
  updated_at: '2026-11-10T03:00:00+00:00',
  last_activity_at: '2026-11-10T03:00:00+00:00',
  task_count: 5,
  completed_task_count: 2,
}

export const APP_PROJECT = {
  id: RAW_PROJECT.id,
  title: 'My Todo App',
  description: '할 일 앱 만들기' as string | null,
  createdAt: '2026-11-09T03:00:00+00:00',
  updatedAt: '2026-11-10T03:00:00+00:00',
  lastActivityAt: '2026-11-10T03:00:00+00:00',
  taskCount: 5,
  completedTaskCount: 2,
}
