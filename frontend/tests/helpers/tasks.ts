// Task objects as the backend sends them (contracts/tasks-api.md).
export const RAW_TASK = {
  id: '22222222-2222-4222-8222-222222222222',
  project_id: '11111111-1111-4111-8111-111111111111',
  task_number: 1,
  title: '할 일 추가 기능',
  description: '버튼을 누르면 목록에 추가' as string | null,
  upload_method: 'file',
  created_at: '2026-11-16T01:00:00+00:00',
  updated_at: '2026-11-16T02:00:00+00:00',
  code: {
    detected_language: 'javascript' as string | null,
    complexity_level: 'beginner' as string | null,
    total_lines: 42,
    total_files: 2,
    upload_size_bytes: 1830,
  },
}

export const APP_TASK = {
  id: RAW_TASK.id,
  projectId: RAW_TASK.project_id,
  taskNumber: 1,
  title: '할 일 추가 기능',
  description: '버튼을 누르면 목록에 추가' as string | null,
  uploadMethod: 'file',
  createdAt: '2026-11-16T01:00:00+00:00',
  updatedAt: '2026-11-16T02:00:00+00:00',
  code: {
    detectedLanguage: 'javascript' as string | null,
    complexityLevel: 'beginner' as string | null,
    totalLines: 42,
    totalFiles: 2,
    uploadSizeBytes: 1830,
  },
}

export const RAW_UPLOAD_RESULT = {
  ...RAW_TASK,
  files: [
    {
      id: '33333333-3333-4333-8333-333333333333',
      file_name: 'App.jsx',
      file_path: 'src/App.jsx',
      file_extension: '.jsx',
      file_size_bytes: 1240,
      language: 'javascript',
    },
  ],
  excluded_paths: ['node_modules/react/index.js'],
}
