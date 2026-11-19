// Single source for app URLs; build links with these instead of string literals.
export const paths = {
  dashboard: '/',
  login: '/login',
  register: '/register',
  trash: '/trash',
  project: (projectId: string) => `/projects/${encodeURIComponent(projectId)}`,
  task: (taskId: string) => `/tasks/${encodeURIComponent(taskId)}`,
} as const
