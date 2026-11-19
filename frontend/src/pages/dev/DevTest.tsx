import type { AxiosInstance } from 'axios'
import { useState } from 'react'
import { ApiError, apiClient } from '../../services/api-client'
import AuthStorePanel from './AuthStorePanel'
import UiTestPanel from './UiTestPanel'

type Result =
  | { kind: 'idle' }
  | { kind: 'success'; status: number; body: unknown; ms: number }
  | { kind: 'error'; status?: number; code: string; message: string; ms: number }

interface Props {
  client?: AxiosInstance
}

// Development-only page (/dev-test): calls GET /api/v1/health through the
// shared API client to check that frontend, backend and database connect.
export default function DevTest({ client = apiClient }: Props) {
  const [result, setResult] = useState<Result>({ kind: 'idle' })
  const [loading, setLoading] = useState(false)
  const url = client.getUri({ url: '/health' })

  async function callApi() {
    setLoading(true)
    const started = performance.now()
    const ms = () => Math.round(performance.now() - started)
    try {
      const response = await client.get('/health')
      setResult({ kind: 'success', status: response.status, body: response.data, ms: ms() })
    } catch (error) {
      const apiError =
        error instanceof ApiError
          ? error
          : new ApiError({ code: 'unknown', message: String(error) })
      setResult({
        kind: 'error',
        status: apiError.status,
        code: apiError.code,
        message: apiError.message,
        ms: ms(),
      })
    } finally {
      setLoading(false)
    }
  }

  return (
    <main>
      <h1>API 연결 테스트</h1>
      <p>GET {url} (개발 모드 전용)</p>

      <button type="button" onClick={() => void callApi()} disabled={loading}>
        {loading ? '호출 중...' : 'API 호출'}
      </button>

      <section aria-label="응답">
        {result.kind === 'idle' && <p role="status">아직 호출하지 않았습니다.</p>}

        {result.kind === 'success' && (
          <div role="status">
            <p>
              ✅ HTTP {result.status} · {result.ms}ms
            </p>
            <pre>{JSON.stringify(result.body, null, 2)}</pre>
          </div>
        )}

        {result.kind === 'error' && (
          <div role="alert">
            <p>
              ❌ HTTP {result.status ?? '응답 없음'} · {result.code} · {result.ms}ms
            </p>
            <p>{result.message}</p>
          </div>
        )}
      </section>

      <AuthStorePanel />
      <UiTestPanel />
    </main>
  )
}
