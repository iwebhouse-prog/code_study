import type { AxiosInstance } from 'axios'
import { apiClient } from './api-client'

/** Project object as the backend sends it (contracts/projects-api.md). */
interface ProjectResponse {
  id: string
  title: string
  description: string | null
  created_at: string
  updated_at: string
  last_activity_at: string
  task_count: number
  completed_task_count: number
}

export interface Project {
  id: string
  title: string
  description: string | null
  createdAt: string
  updatedAt: string
  lastActivityAt: string
  taskCount: number
  completedTaskCount: number
}

export interface NewProject {
  title: string
  description?: string
}

/** Only the fields that changed; `description: null` clears the description. */
export interface ProjectChanges {
  title?: string
  description?: string | null
}

export function toProject(body: ProjectResponse): Project {
  return {
    id: body.id,
    title: body.title,
    description: body.description,
    createdAt: body.created_at,
    updatedAt: body.updated_at,
    lastActivityAt: body.last_activity_at,
    taskCount: body.task_count,
    completedTaskCount: body.completed_task_count,
  }
}

const projectUrl = (projectId: string) => `/projects/${encodeURIComponent(projectId)}`

export function createProjectService(client: AxiosInstance) {
  return {
    list: async () => (await client.get<ProjectResponse[]>('/projects')).data.map(toProject),
    get: async (projectId: string) =>
      toProject((await client.get<ProjectResponse>(projectUrl(projectId))).data),
    create: async (project: NewProject) =>
      toProject((await client.post<ProjectResponse>('/projects', project)).data),
    update: async (projectId: string, changes: ProjectChanges) =>
      toProject((await client.patch<ProjectResponse>(projectUrl(projectId), changes)).data),
    remove: async (projectId: string): Promise<void> => {
      await client.delete(projectUrl(projectId))
    },
  }
}

export const projectService = createProjectService(apiClient)
