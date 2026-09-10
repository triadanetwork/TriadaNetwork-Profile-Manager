'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import { Activity, ArrowUpRight, CircleDot, Play, RefreshCw, Square, X } from 'lucide-react'
import { browsersAPI, profilesAPI, type BrowserSession, type Profile } from '@/lib/api'
import { useToast } from '@/components/toast'

type Task = { profile: Profile; state: 'running' | 'offline' }

export default function TasksPage() {
  const [profiles, setProfiles] = useState<Profile[]>([])
  const [sessions, setSessions] = useState<BrowserSession[]>([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState<Set<string>>(new Set())
  const toast = useToast()

  const load = useCallback(async () => {
    try {
      const [p, active] = await Promise.all([profilesAPI.getProfiles({ page: 1, per_page: 100 }), browsersAPI.sessions()])
      setProfiles(p.profiles); setSessions(active.sessions)
    } catch (error) { toast('error', 'Task Center unavailable', String(error instanceof Error ? error.message : error)) }
    finally { setLoading(false) }
  }, [toast])

  useEffect(() => { load(); const timer = window.setInterval(load, 3000); return () => window.clearInterval(timer) }, [load])

  const sessionByProfile = useMemo(() => new Map(sessions.map(s => [s.profile_id, s])), [sessions])
  const tasks = useMemo<Task[]>(() => sessions.map(s => profiles.find(p => p.id === s.profile_id)).filter(Boolean).map(profile => ({ profile: profile as Profile, state: 'running' })), [sessions, profiles])
  const idle = profiles.filter(p => !sessionByProfile.has(p.id)).slice(0, 12)

  const launch = async (id: string) => { setBusy(s => new Set(s).add(id)); try { await profilesAPI.startProfile(id); await load(); toast('ok', 'Browser launched') } catch (e) { toast('error', 'Launch failed', String(e)) } finally { setBusy(s => { const n=new Set(s); n.delete(id); return n }) } }
  const restart = async (id: string) => { setBusy(s => new Set(s).add(id)); try { await browsersAPI.restart(id); await load(); toast('ok', 'Browser restarted') } catch (e) { toast('error', 'Restart failed', String(e)) } finally { setBusy(s => { const n=new Set(s); n.delete(id); return n }) } }
  const forceClose = async (id: string) => { setBusy(s => new Set(s).add(id)); try { await browsersAPI.forceClose(id); await load(); toast('ok', 'Browser force-closed') } catch (e) { toast('error', 'Force close failed', String(e)) } finally { setBusy(s => { const n=new Set(s); n.delete(id); return n }) } }
  const close = async (id: string) => { setBusy(s => new Set(s).add(id)); try { await profilesAPI.closeProfile(id); await load(); toast('ok', 'Browser closed') } catch (e) { toast('error', 'Close failed', String(e)) } finally { setBusy(s => { const n=new Set(s); n.delete(id); return n }) } }

  return <div className="page-shell">
    <header className="page-header"><div><div className="eyebrow">TRIADA NETWORK / DESKTOP</div><h1>Task Center</h1><p className="page-subtitle">Live browser sessions and launch queue.</p></div><button className="btn btn-default" onClick={load}><RefreshCw size={14}/> Refresh</button></header>
    <section className="grid gap-3 sm:grid-cols-3">
      <div className="panel p-4"><div className="eyebrow">RUNNING</div><div className="mt-2 text-2xl font-semibold">{tasks.length}</div><div className="mt-1 text-xs text-ink-faint">Live browser sessions</div></div>
      <div className="panel p-4"><div className="eyebrow">AVAILABLE</div><div className="mt-2 text-2xl font-semibold">{profiles.length - tasks.length}</div><div className="mt-1 text-xs text-ink-faint">Profiles not running</div></div>
      <div className="panel p-4"><div className="eyebrow">POLLING</div><div className="mt-2 text-2xl font-semibold">3s</div><div className="mt-1 text-xs text-ink-faint">Desktop status refresh</div></div>
    </section>
    <section className="mt-3 panel p-4"><div className="mb-5 flex items-center justify-between"><div><div className="eyebrow">LIVE</div><h2>Running sessions</h2></div><span className="status-chip"><CircleDot size={11}/> {tasks.length} active</span></div>
      {tasks.length ? <div className="space-y-2">{tasks.map(({profile}) => <div key={profile.id} className="flex items-center justify-between rounded-md border border-line bg-canvas px-3 py-3"><div className="flex min-w-0 items-center gap-3"><span className="live-dot"/><div className="min-w-0"><div className="truncate text-sm font-medium">{profile.name}</div><div className="truncate font-mono text-[10px] text-ink-faint">{profile.id}</div><div className="mt-1 flex gap-3 text-[10px] text-ink-faint"><span>PID {sessionByProfile.get(profile.id)?.process_id ?? '—'}</span><span>{Math.floor((sessionByProfile.get(profile.id)?.uptime_seconds ?? 0) / 60)}m</span><span>{sessionByProfile.get(profile.id)?.memory_mb != null ? `${sessionByProfile.get(profile.id)?.memory_mb} MB` : '—'}</span></div></div></div><div className="flex items-center gap-2"><Link className="icon-link" href="/">Open <ArrowUpRight size={13}/></Link><button className="btn btn-default" disabled={busy.has(profile.id)} onClick={() => restart(profile.id)}>Restart</button><button className="btn btn-default" disabled={busy.has(profile.id)} onClick={() => forceClose(profile.id)}>Force close</button><button className="btn btn-default" disabled={busy.has(profile.id)} onClick={() => close(profile.id)}><Square size={13}/> Stop</button></div></div>)}</div> : <div className="rounded-md border border-dashed border-line bg-canvas p-12 text-center text-sm text-ink-faint">No browser sessions are running.</div>}
    </section>
    <section className="mt-3 panel p-4"><div className="mb-5"><div className="eyebrow">QUEUE</div><h2>Launch profiles</h2></div><div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">{idle.map(profile => <div key={profile.id} className="rounded-md border border-line bg-canvas p-3"><div className="flex items-center justify-between gap-2"><div className="min-w-0"><div className="truncate text-sm font-medium">{profile.name}</div><div className="font-mono text-[10px] text-ink-faint">{profile.id}</div></div><span className="text-[10px] text-ink-faint">IDLE</span></div><button className="btn btn-primary mt-3 w-full" disabled={busy.has(profile.id)} onClick={() => launch(profile.id)}><Play size={13}/> Launch</button></div>)}</div>{!idle.length && !loading && <div className="text-sm text-ink-faint">No idle profiles available.</div>}</section>
  </div>
}
