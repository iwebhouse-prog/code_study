// Route structure for the whole app (URL -> page).
import type { RouteObject } from 'react-router-dom'
import ProtectedRoute from './components/auth/ProtectedRoute'
import AppLayout from './components/layout/AppLayout'
import Dashboard from './pages/Dashboard'
import Login from './pages/Login'
import NotFound from './pages/NotFound'
import ProjectDetail from './pages/ProjectDetail'
import Register from './pages/Register'
import TaskDetail from './pages/TaskDetail'
import Trash from './pages/Trash'

export const routes: RouteObject[] = [
  // Public pages: no navigation bar (requirements-addendum navigation rules).
  { path: '/login', element: <Login /> },
  { path: '/register', element: <Register /> },
  {
    // Signed-in pages: checked by ProtectedRoute, shown under the top bar.
    element: <ProtectedRoute />,
    children: [
      {
        element: <AppLayout />,
        children: [
          { path: '/', element: <Dashboard /> },
          { path: '/projects/:projectId', element: <ProjectDetail /> },
          // Task URLs match the API (/api/v1/tasks/{task_id}); tabs live inside the page.
          { path: '/tasks/:taskId', element: <TaskDetail /> },
          { path: '/trash', element: <Trash /> },
        ],
      },
    ],
  },
  // Development-only tools; lazy so production builds leave them out entirely.
  ...(import.meta.env.DEV
    ? [
        {
          path: '/dev-test',
          lazy: async () => ({ Component: (await import('./pages/dev/DevTest')).default }),
        },
        {
          path: '/dev/query-test',
          lazy: async () => ({ Component: (await import('./pages/dev/QueryTest')).default }),
        },
      ]
    : []),
  { path: '*', element: <NotFound /> },
]
