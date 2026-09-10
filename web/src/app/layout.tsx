import type { Metadata } from 'next'

import { AppShell } from '@/components/app-shell'
import { LoginGate } from '@/components/login-gate'
import { ToastProvider } from '@/components/toast'
import './globals.css'

export const metadata: Metadata = {
  title: 'Triada Network',
  description: 'Browser infrastructure and profile management for teams',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <ToastProvider>
          <LoginGate>
            <AppShell>{children}</AppShell>
          </LoginGate>
        </ToastProvider>
      </body>
    </html>
  )
}
