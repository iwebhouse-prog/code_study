import { Outlet } from 'react-router-dom'
import Toaster from '@/components/ui/toast'
import TopNav from './TopNav'

// Layout of the signed-in pages: the top bar above whichever page is open,
// plus the toasts that pages (and the page they navigate to) can raise.
export default function AppLayout() {
  return (
    <>
      <TopNav />
      <Toaster />
      <Outlet />
    </>
  )
}
