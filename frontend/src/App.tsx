import { RouterProvider } from 'react-router-dom'
import { Toaster } from '@/components/ui/sonner'
import { router } from '@/routes'
import PwaUpdatePrompt from '@/features/pwa/PwaUpdatePrompt'

export default function App() {
  return (
    <>
      <RouterProvider router={router} />
      <Toaster richColors position="top-right" />
      <PwaUpdatePrompt />
    </>
  )
}
