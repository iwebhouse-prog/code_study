import type { AxiosInstance } from 'axios'
import type { Language } from '@/lib/languages'
import type { UploadEntry } from '@/lib/upload-rules'
import { apiClient } from './api-client'

/** Task object as the backend sends it (contracts/tasks-api.md). */
interface TaskResponse {
  id: string
  project_id: string
  task_number: number
  title: string
  description: string | null
  upload_method: string
  created_at: string
  updated_at: string
  code: {
    detected_language: string | null
    complexity_level: string | null
    total_lines: number
    total_files: number
    upload_size_bytes: number
  } | null
}

interface UploadedFileResponse {
  id: string
  file_name: string
  file_path: string
  file_extension: string
  file_size_bytes: number
  language: string
}

interface UploadResultResponse extends TaskResponse {
  files: UploadedFileResponse[]
  excluded_paths: string[]
}

interface TaskCodeResponse {
  task_id: string
  detected_language: string | null
  files: (UploadedFileResponse & { content: string })[]
}

export type UploadMethod = 'file' | 'folder' | 'paste'

export interface Task {
  id: string
  projectId: string
  taskNumber: number
  title: string
  description: string | null
  uploadMethod: string
  createdAt: string
  updatedAt: string
  code: {
    detectedLanguage: string | null
    complexityLevel: string | null
    totalLines: number
    totalFiles: number
    uploadSizeBytes: number
  } | null
}

export interface UploadedFile {
  id: string
  fileName: string
  filePath: string
  fileExtension: string
  fileSizeBytes: number
  language: string
}

export interface UploadResult extends Task {
  files: UploadedFile[]
  excludedPaths: string[]
}

export interface TaskCode {
  taskId: string
  detectedLanguage: string | null
  files: (UploadedFile & { content: string })[]
}

interface NewTaskBase {
  title: string
  description?: string
}

/** What to create: files/folders carry entries, pasted code carries text and language. */
export type NewTask =
  | (NewTaskBase & { uploadMethod: 'file' | 'folder'; files: UploadEntry[] })
  | (NewTaskBase & { uploadMethod: 'paste'; code: string; language: Language })

/** Only the fields that changed; `description: null` clears the description. */
export interface TaskChanges {
  title?: string
  description?: string | null
}

export function toTask(body: TaskResponse): Task {
  return {
    id: body.id,
    projectId: body.project_id,
    taskNumber: body.task_number,
    title: body.title,
    description: body.description,
    uploadMethod: body.upload_method,
    createdAt: body.created_at,
    updatedAt: body.updated_at,
    code: body.code && {
      detectedLanguage: body.code.detected_language,
      complexityLevel: body.code.complexity_level,
      totalLines: body.code.total_lines,
      totalFiles: body.code.total_files,
      uploadSizeBytes: body.code.upload_size_bytes,
    },
  }
}

function toUploadedFile(file: UploadedFileResponse): UploadedFile {
  return {
    id: file.id,
    fileName: file.file_name,
    filePath: file.file_path,
    fileExtension: file.file_extension,
    fileSizeBytes: file.file_size_bytes,
    language: file.language,
  }
}

function toFormData(task: NewTask): FormData {
  const form = new FormData()
  form.append('title', task.title)
  if (task.description) form.append('description', task.description)
  form.append('upload_method', task.uploadMethod)
  if (task.uploadMethod === 'paste') {
    form.append('code', task.code)
    form.append('language', task.language)
  } else {
    // The part's filename is the path, so folders keep their structure.
    for (const { file, path } of task.files) form.append('files', file, path)
  }
  return form
}

const projectTasksUrl = (projectId: string) => `/projects/${encodeURIComponent(projectId)}/tasks`
const taskUrl = (taskId: string) => `/tasks/${encodeURIComponent(taskId)}`

export function createTaskService(client: AxiosInstance) {
  return {
    list: async (projectId: string) =>
      (await client.get<TaskResponse[]>(projectTasksUrl(projectId))).data.map(toTask),
    create: async (projectId: string, task: NewTask): Promise<UploadResult> => {
      const { data } = await client.post<UploadResultResponse>(
        projectTasksUrl(projectId),
        toFormData(task),
      )
      return {
        ...toTask(data),
        files: data.files.map(toUploadedFile),
        excludedPaths: data.excluded_paths,
      }
    },
    get: async (taskId: string) => toTask((await client.get<TaskResponse>(taskUrl(taskId))).data),
    update: async (taskId: string, changes: TaskChanges) =>
      toTask((await client.patch<TaskResponse>(taskUrl(taskId), changes)).data),
    remove: async (taskId: string): Promise<void> => {
      await client.delete(taskUrl(taskId))
    },
    getCode: async (taskId: string): Promise<TaskCode> => {
      const { data } = await client.get<TaskCodeResponse>(`${taskUrl(taskId)}/code`)
      return {
        taskId: data.task_id,
        detectedLanguage: data.detected_language,
        files: data.files.map((file) => ({ ...toUploadedFile(file), content: file.content })),
      }
    },
  }
}

export const taskService = createTaskService(apiClient)
