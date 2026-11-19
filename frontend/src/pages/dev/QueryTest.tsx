import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { getHttpStatus } from '../../lib/queryClient'
import { type DummyMode, fetchDummyProjects } from './dummyApi'

const MODES: { mode: DummyMode; label: string }[] = [
  { mode: 'success', label: '성공' },
  { mode: 'notfound', label: '404 오류' },
  { mode: 'server-error', label: '503 오류' },
]

interface Props {
  delayMs?: number
  retryDelayMs?: number
}

// Development-only page (/dev/query-test) showing loading, success and error
// states with the shared query client rules from T019.
export default function QueryTest({ delayMs = 1000, retryDelayMs = 500 }: Props) {
  const [mode, setMode] = useState<DummyMode>('success')
  const query = useQuery({
    queryKey: ['dev', 'dummy-projects', mode],
    queryFn: () => fetchDummyProjects(mode, delayMs),
    retryDelay: retryDelayMs,
  })

  return (
    <main>
      <h1>TanStack Query 테스트</h1>
      <p>더미 API 응답을 고르면 로딩·성공·에러 상태가 바뀝니다. (개발 모드 전용)</p>

      <div>
        {MODES.map(({ mode: value, label }) => (
          <button
            key={value}
            type="button"
            onClick={() => setMode(value)}
            aria-pressed={mode === value}
          >
            {label}
          </button>
        ))}
        <button type="button" onClick={() => void query.refetch()}>
          다시 불러오기
        </button>
      </div>

      <p role="status">
        상태: {query.isPending ? '불러오는 중...' : query.isError ? '에러' : '성공'}
        {query.isFetching && !query.isPending ? ' (새로 받는 중...)' : ''}
      </p>

      {query.isError && (
        <div role="alert">
          <p>HTTP {getHttpStatus(query.error)} 오류가 발생했습니다.</p>
          <p>시도 횟수: {query.failureCount}</p>
        </div>
      )}

      {query.isSuccess && (
        <ul>
          {query.data.map((project) => (
            <li key={project.id}>
              <strong>{project.title}</strong> — 태스크 {project.taskCount}개
            </li>
          ))}
        </ul>
      )}
    </main>
  )
}
