// TanStack Query keys for projects; the list key is the prefix of every detail
// key (and of the project's task list), so invalidating it refreshes all of them.
export const PROJECTS_KEY = ['projects'] as const
export const projectKey = (projectId: string) => ['projects', projectId] as const
export const projectTasksKey = (projectId: string) => ['projects', projectId, 'tasks'] as const
export const taskKey = (taskId: string) => ['tasks', taskId] as const
// Under the task key, so invalidating the task refreshes its document too.
export const taskDocumentStatusKey = (taskId: string) =>
  ['tasks', taskId, 'document', 'status'] as const
export const taskDocumentKey = (taskId: string) => ['tasks', taskId, 'document'] as const
export const taskCodeKey = (taskId: string) => ['tasks', taskId, 'code'] as const
