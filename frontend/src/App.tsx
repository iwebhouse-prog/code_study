import { QueryClientProvider } from '@tanstack/react-query'
import { useState } from 'react'
import { RouterProvider, createBrowserRouter } from 'react-router-dom'
import SessionBootstrap from './components/auth/SessionBootstrap'
import { createQueryClient } from './lib/queryClient'
import { routes } from './routes'

export default function App() {
  // One router and one query cache per mount: re-renders (and StrictMode's
  // double render in development) must not reset navigation or cached data.
  const [router] = useState(() => createBrowserRouter(routes))
  const [queryClient] = useState(createQueryClient)
  return (
    <QueryClientProvider client={queryClient}>
      <SessionBootstrap />
      <RouterProvider router={router} />
    </QueryClientProvider>
  )
}
