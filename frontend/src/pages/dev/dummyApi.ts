// Development-only fake API for trying TanStack Query states without a backend.

export type DummyMode = 'success' | 'notfound' | 'server-error'

export interface DummyProject {
  id: string
  title: string
  taskCount: number
}

const PROJECTS: DummyProject[] = [
  { id: 'p-1', title: 'Python 기초 다지기', taskCount: 4 },
  { id: 'p-2', title: 'React 할 일 앱', taskCount: 7 },
  { id: 'p-3', title: 'FastAPI 로그인 만들기', taskCount: 2 },
]

// Shaped like the shared backend error (T016) inside an axios-style error.
const ERRORS = {
  notfound: { status: 404, error: 'not_found', message: '요청한 페이지를 찾을 수 없습니다.' },
  'server-error': {
    status: 503,
    error: 'service_unavailable',
    message: '일시적으로 서비스를 이용할 수 없습니다. 잠시 후 다시 시도하세요.',
  },
} as const

export function fetchDummyProjects(mode: DummyMode, delayMs: number): Promise<DummyProject[]> {
  return new Promise((resolve, reject) => {
    setTimeout(() => {
      if (mode === 'success') {
        resolve(PROJECTS)
        return
      }
      const { status, ...data } = ERRORS[mode]
      reject({ response: { status, data } })
    }, delayMs)
  })
}
