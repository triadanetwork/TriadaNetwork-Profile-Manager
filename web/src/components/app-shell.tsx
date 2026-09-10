'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { Activity, CalendarClock, Cloud, Download, FileClock, Layers, LogOut, Settings, Trash2, Users, ListTodo, Wrench, Archive, ShieldCheck } from 'lucide-react'

import { useAuth } from '@/components/login-gate'
import { operationsAPI, systemAPI, type Workspace } from '@/lib/api'
import { DesktopOnboarding } from '@/components/desktop-onboarding'

const NAV = [
  { href: '/dashboard/', label: 'Dashboard', icon: Activity },
  { href: '/', label: 'Profiles', icon: Users },
  { href: '/proxy-pools/', label: 'Proxy Manager', icon: Layers },
  { href: '/tasks/', label: 'Tasks', icon: ListTodo },
  { href: '/runtime/', label: 'Browser Runtime', icon: Wrench },
  { href: '/trash/', label: 'Trash', icon: Trash2 },
  { href: '/team/', label: 'Team', icon: Users },
  { href: '/activity/', label: 'Activity', icon: FileClock, audit: true },
  { href: '/cloud/', label: 'Cloud', icon: Cloud },
  { href: '/updates/', label: 'Updates', icon: Download },
  { href: '/groups/', label: 'Groups', icon: Layers },
  { href: '/schedules/', label: 'Schedules', icon: CalendarClock },
  { href: '/diagnostics/', label: 'Diagnostics', icon: Wrench },
  { href: '/security/', label: 'Security & Data', icon: ShieldCheck },
  { href: '/backups/', label: 'Backups', icon: Archive },
  { href: '/settings/', label: 'Settings', icon: Settings },
]

/** Fixed rail + scrollable work area. The rail never scrolls. */
export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  // trailingSlash is on for the static export, so normalise before comparing.
  const current = pathname.replace(/\/+$/, '') || '/'
  const [address, setAddress] = useState<string | null>(null)
  const [workspace, setWorkspace] = useState<Workspace | null>(null)
  const { username, logout } = useAuth()

  useEffect(() => {
    // Report where the server actually is rather than assuming loopback.
    systemAPI
      .config()
      .then((config) => setAddress(`${config.host}:${config.port}`))
      .catch(() => setAddress(null))
    operationsAPI.getWorkspace().then(setWorkspace).catch(() => setWorkspace(null))
  }, [])

  return (
    <div className="flex h-screen">
      <aside className="flex w-[236px] shrink-0 flex-col border-r border-line bg-surface">
        <div className="flex h-[68px] items-center border-b border-line px-4">
          <Wordmark />
        </div>

        <nav className="flex flex-col gap-px p-2">
          {NAV.filter(({ href, audit }) => (href !== '/team/' || workspace?.workspace_type === 'team') && (!audit || workspace?.current_role !== 'viewer')).map(({ href, label, icon: Icon }) => {
            const target = href.replace(/\/+$/, '') || '/'
            const active = current === target
            return (
              <Link
                key={href}
                href={href}
                aria-current={active ? 'page' : undefined}
                className={`flex items-center gap-2.5 rounded-md px-2.5 py-1.5 transition-colors ${
                  active
                    ? 'bg-raised text-ink'
                    : 'text-ink-dim hover:bg-raised/60 hover:text-ink'
                }`}
              >
                <Icon size={15} strokeWidth={1.75} className={active ? 'text-signal' : ''} />
                {label}
              </Link>
            )
          })}
        </nav>

        <div className="mt-auto">
          {username && (
            <div className="flex items-center justify-between gap-2 border-t border-line px-4 py-2">
              <span className="truncate text-ink-dim" title={username}>
                {username}
              </span>
              <button
                type="button"
                onClick={logout}
                aria-label="Log out"
                title="Log out"
                className="rounded p-1 text-ink-faint transition-colors hover:bg-raised hover:text-ink"
              >
                <LogOut size={14} strokeWidth={1.75} />
              </button>
            </div>
          )}
          <div className="px-4 py-3 font-mono text-[11px] text-ink-faint">{address ?? '—'}</div>
        </div>
      </aside>

      <main className="flex-1 overflow-y-auto">{children}</main>
      <DesktopOnboarding />
    </div>
  )
}

/**
 * Triada mark: three aligned bars represent profiles, teams and infrastructure.
 */
function Wordmark() {
  return (
    <>
      <svg width="17" height="17" viewBox="0 0 16 16" fill="none" aria-hidden="true">
        <rect x="1" y="2.5" width="14" height="2.4" rx="1.2" fill="var(--color-ink)" />
        <rect x="3" y="6.8" width="10" height="2.4" rx="1.2" fill="var(--color-ink-dim)" opacity="0.72" />
        <rect x="5.5" y="11.1" width="5" height="2.4" rx="1.2" fill="var(--color-ink-faint)" opacity="0.75" />
      </svg>
      <span className="text-[12px] font-semibold tracking-[0.12em]">TRIADA NETWORK</span>
    </>
  )
}
