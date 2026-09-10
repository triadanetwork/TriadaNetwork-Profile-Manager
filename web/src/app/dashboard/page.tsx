'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import { Activity, ArrowUpRight, Boxes, CircleDot, Database, Layers3, Play, Users } from 'lucide-react'

import { browsersAPI, groupsAPI, profilesAPI, systemAPI, operationsAPI, type Group, type Profile, type SystemStatus, type TeamDashboard } from '@/lib/api'
import { useToast } from '@/components/toast'

const EMPTY_STATUS: SystemStatus = { total_profiles: 0, active_profiles: 0, running_browsers: 0, total_groups: 0, system_load: 0, memory_usage: 0, disk_usage: 0, uptime_seconds: 0 }

function formatUptime(seconds: number) {
  const days = Math.floor(seconds / 86400)
  const hours = Math.floor((seconds % 86400) / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  if (days) return `${days}d ${hours}h ${minutes}m`
  if (hours) return `${hours}h ${minutes}m`
  return `${minutes}m`
}

function Metric({ label, value, detail, icon: Icon }: { label: string; value: string | number; detail: string; icon: typeof Activity }) {
  return (
    <div className="panel relative overflow-hidden p-4">
      <div className="mb-6 flex items-start justify-between">
        <span className="eyebrow">{label}</span>
        <span className="flex h-8 w-8 items-center justify-center rounded-md border border-line bg-raised text-ink-dim"><Icon size={15} strokeWidth={1.7} /></span>
      </div>
      <div className="text-2xl font-semibold tracking-[-0.03em] text-ink">{value}</div>
      <div className="mt-1 text-xs text-ink-faint">{detail}</div>
    </div>
  )
}

function Meter({ label, value }: { label: string; value: number }) {
  const safeValue = Math.min(100, Math.max(0, value))
  return (
    <div>
      <div className="mb-2 flex items-center justify-between text-xs"><span className="text-ink-dim">{label}</span><span className="font-mono text-ink">{safeValue.toFixed(0)}%</span></div>
      <div className="h-1.5 overflow-hidden rounded-full bg-raised"><div className="h-full rounded-full bg-signal transition-[width] duration-500" style={{ width: `${safeValue}%` }} /></div>
    </div>
  )
}

export default function DashboardPage() {
  const [status, setStatus] = useState<SystemStatus>(EMPTY_STATUS)
  const [groups, setGroups] = useState<Group[]>([])
  const [profiles, setProfiles] = useState<Profile[]>([])
  const [activeIds, setActiveIds] = useState<string[]>([])
  const [team, setTeam] = useState<TeamDashboard | null>(null)
  const [loading, setLoading] = useState(true)
  const toast = useToast()

  const load = useCallback(async () => {
    try {
      const [statusResponse, groupsResponse, profilesResponse, browsersResponse, teamResponse] = await Promise.all([
        systemAPI.status(), groupsAPI.list(), profilesAPI.getProfiles({ page: 1, per_page: 8 }), browsersAPI.active(), operationsAPI.teamDashboard().catch(() => null),
      ])
      setStatus(statusResponse)
      setGroups(groupsResponse.groups)
      setProfiles(profilesResponse.profiles)
      setActiveIds(browsersResponse.active_browsers.map((item) => item.profile_id))
      setTeam(teamResponse)
    } catch (error) {
      toast('error', 'Dashboard unavailable', String(error instanceof Error ? error.message : error))
    } finally {
      setLoading(false)
    }
  }, [toast])

  useEffect(() => {
    load()
    const timer = window.setInterval(load, 10000)
    return () => window.clearInterval(timer)
  }, [load])

  const profileMap = useMemo(() => new Map(profiles.map((profile) => [profile.id, profile])), [profiles])
  const activeProfiles = activeIds.map((id) => profileMap.get(id)).filter(Boolean) as Profile[]

  if (loading && !profiles.length) {
    return <div className="page-shell"><div className="page-header"><div><div className="eyebrow">TRIADA NETWORK</div><h1>Dashboard</h1></div></div><div className="panel p-6 text-ink-dim">Loading control center…</div></div>
  }

  return (
    <div className="page-shell">
      <header className="page-header">
        <div><div className="eyebrow">TRIADA NETWORK / CONTROL CENTER</div><h1>Dashboard</h1><p className="page-subtitle">Operational view of your browser infrastructure.</p></div>
        <div className="flex items-center gap-2"><span className="status-chip"><CircleDot size={11} className="signal-pulse rounded-full" /> System online</span><Link href="/" className="btn btn-primary"><Users size={14} /> Profiles</Link></div>
      </header>

      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Metric label="Profiles" value={status.total_profiles} detail={`${status.active_profiles} active`} icon={Boxes} />
        <Metric label="Running" value={status.running_browsers} detail="Browser sessions" icon={Play} />
        <Metric label="Groups" value={status.total_groups} detail="Profile segments" icon={Layers3} />
        <Metric label="Uptime" value={formatUptime(status.uptime_seconds)} detail="Current instance" icon={Activity} />
      </section>

      {team?.workspace.workspace_type === 'team' && (
        <section className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <Metric label="Team" value={team.summary.members} detail={`${team.workspace.current_role ?? 'member'} role`} icon={Users} />
          <Metric label="Assigned" value={team.summary.assigned_profiles} detail="Profiles assigned to buyers" icon={Users} />
          <Metric label="Unassigned" value={team.summary.unassigned_profiles} detail="Profiles needing ownership" icon={Boxes} />
          <Metric label="Invites" value={team.pending_invites} detail="Pending workspace invites" icon={Users} />
        </section>
      )}

      <section className="mt-3 grid gap-3 lg:grid-cols-[1.35fr_1fr]">
        <div className="panel p-4">
          <div className="mb-5 flex items-center justify-between"><div><div className="eyebrow">LIVE SESSIONS</div><h2>Running browsers</h2></div><Link href="/" className="icon-link">Open profiles <ArrowUpRight size={13} /></Link></div>
          {activeProfiles.length ? <div className="space-y-1.5">{activeProfiles.map((profile) => <div key={profile.id} className="flex items-center justify-between rounded-md border border-line bg-canvas px-3 py-2.5"><div className="min-w-0"><div className="truncate text-sm font-medium">{profile.name}</div><div className="mt-0.5 font-mono text-[11px] text-ink-faint">{profile.id}</div></div><span className="status-chip status-chip-live"><span className="live-dot" /> RUNNING</span></div>)}</div> : <div className="flex min-h-36 items-center justify-center rounded-md border border-dashed border-line bg-canvas text-sm text-ink-faint">No active browser sessions.</div>}
        </div>

        <div className="panel p-4">
          <div className="mb-6"><div className="eyebrow">INSTANCE HEALTH</div><h2>System resources</h2></div>
          <div className="space-y-5"><Meter label="Memory usage" value={status.memory_usage} /><Meter label="Disk usage" value={status.disk_usage} /><Meter label="CPU load" value={Math.min(100, status.system_load * 20)} /></div>
          <div className="mt-6 grid grid-cols-2 gap-2 border-t border-line pt-4"><div className="rounded-md bg-canvas p-3"><div className="eyebrow">CPU LOAD</div><div className="mt-1 font-mono text-sm">{status.system_load.toFixed(2)}</div></div><div className="rounded-md bg-canvas p-3"><div className="eyebrow">STORAGE</div><div className="mt-1 font-mono text-sm">{status.disk_usage.toFixed(0)}%</div></div></div>
        </div>
      </section>

      <section className="mt-3 grid gap-3 lg:grid-cols-[1fr_1.35fr]">
        <div className="panel p-4">
          <div className="mb-5 flex items-center justify-between"><div><div className="eyebrow">GROUPS</div><h2>Profile segments</h2></div><Link href="/groups/" className="icon-link">Manage <ArrowUpRight size={13} /></Link></div>
          <div className="space-y-1.5">{groups.slice(0, 6).map((group) => <div key={group.id} className="flex items-center justify-between rounded-md bg-canvas px-3 py-2.5"><div className="flex min-w-0 items-center gap-2"><span className="h-1.5 w-1.5 rounded-full bg-signal" /><span className="truncate text-sm">{group.name}</span></div><span className="font-mono text-[11px] text-ink-faint">{group.profile_count}</span></div>)}{!groups.length && <div className="py-8 text-center text-sm text-ink-faint">No groups configured.</div>}</div>
        </div>

        <div className="panel p-4">
          <div className="mb-5 flex items-center justify-between"><div><div className="eyebrow">RECENT PROFILES</div><h2>Latest workspace activity</h2></div><Link href="/" className="icon-link">View all <ArrowUpRight size={13} /></Link></div>
          <div className="overflow-hidden rounded-md border border-line"><div className="grid grid-cols-[1.4fr_.7fr_.7fr] border-b border-line bg-raised px-3 py-2 text-[10px] font-medium uppercase tracking-[0.1em] text-ink-faint"><span>Profile</span><span>OS</span><span>Status</span></div>{profiles.slice(0, 6).map((profile) => <div key={profile.id} className="grid grid-cols-[1.4fr_.7fr_.7fr] items-center border-b border-line/70 px-3 py-2.5 last:border-0"><div className="min-w-0"><div className="truncate text-sm">{profile.name}</div><div className="truncate font-mono text-[10px] text-ink-faint">{profile.id}</div></div><span className="text-xs text-ink-dim">{profile.browser_settings?.os ?? '—'}</span><span className="text-[11px] text-ink-dim">{profile.status}</span></div>)}{!profiles.length && <div className="py-10 text-center text-sm text-ink-faint">No profiles yet.</div>}</div>
        </div>
      </section>

      <section className="mt-3 grid gap-3 sm:grid-cols-3">
        <Link href="/groups/" className="panel action-card"><Layers3 size={16} /><div><strong>Organize groups</strong><span>Segment profiles by workspace or traffic source.</span></div><ArrowUpRight size={14} /></Link>
        <Link href="/schedules/" className="panel action-card"><Activity size={16} /><div><strong>Automation</strong><span>Review scheduled browser operations.</span></div><ArrowUpRight size={14} /></Link>
        <Link href="/settings/" className="panel action-card"><Database size={16} /><div><strong>Infrastructure</strong><span>Inspect instance, auth and storage settings.</span></div><ArrowUpRight size={14} /></Link>
      </section>
    </div>
  )
}
