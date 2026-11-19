import { useSessionBootstrap } from '../../hooks/useAuth'

// Renders nothing; lives inside QueryClientProvider so the hook can reach the cache.
export default function SessionBootstrap() {
  useSessionBootstrap()
  return null
}
