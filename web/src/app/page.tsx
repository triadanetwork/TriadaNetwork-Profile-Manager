'use client'

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Cookie, Download, Filter, Pencil, Play, Plus, RefreshCw, Search, Square, Trash2, Upload, Users } from 'lucide-react'
import { EmptyState } from '@/components/empty-state'
import { ConfirmDialog, Modal } from '@/components/modal'
import { ProfileForm } from '@/components/profile-form'
import { useToast } from '@/components/toast'
import { browsersAPI, exportCookies, importCookies, exportCookiesBulk, importCookiesBulk, formatLastUsed, formatProxyString, groupsAPI, OS_LABELS, profilesAPI, operationsAPI, type Group, type Profile, type ProfileOperations, type ProxyPool, type TriadaTag, type Workspace, type WorkspaceMember, type ProfileOperationsPatch } from '@/lib/api'

type OpMap = Record<string, ProfileOperations>

function Pill({ children, tone = 'default' }: { children: React.ReactNode; tone?: 'default'|'ok'|'warn'|'danger' }) {
  return <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] ${tone === 'ok' ? 'border-ok/30 bg-ok/10 text-ok' : tone === 'warn' ? 'border-warn/30 bg-warn/10 text-warn' : tone === 'danger' ? 'border-danger/30 bg-danger/10 text-danger' : 'border-line text-ink-dim'}`}>{children}</span>
}

function proxyTone(profile: Profile) {
  const c = profile.proxy_check
  if (!profile.proxy_config) return ['No proxy', 'default'] as const
  if (!c) return ['Unchecked', 'warn'] as const
  if (!c.reachable) return ['Offline', 'danger'] as const
  if (c.findings.some((f) => f.level === 'error')) return ['Mismatch', 'danger'] as const
  if (c.findings.some((f) => f.level === 'warning')) return ['Warning', 'warn'] as const
  return [`Healthy${c.latency_ms ? ` · ${c.latency_ms} ms` : ''}`, 'ok'] as const
}

export default function ProfilesPage() {
  const [profiles, setProfiles] = useState<Profile[]>([])
  const [groups, setGroups] = useState<Group[]>([])
  const [ops, setOps] = useState<OpMap>({})
  const [workspace, setWorkspace] = useState<Workspace | null>(null)
  const [members, setMembers] = useState<WorkspaceMember[]>([])
  const [tags, setTags] = useState<TriadaTag[]>([])
  const [pools, setPools] = useState<ProxyPool[]>([])
  const [running, setRunning] = useState<Set<string>>(new Set())
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [groupFilter, setGroupFilter] = useState('all')
  const [ownerFilter, setOwnerFilter] = useState('all')
  const [tagFilter, setTagFilter] = useState('all')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [formOpen, setFormOpen] = useState(false)
  const [editing, setEditing] = useState<Profile | null>(null)
  const [operationsFor, setOperationsFor] = useState<Profile | null>(null)
  const [busy, setBusy] = useState<Set<string>>(new Set())
  const [confirm, setConfirm] = useState<null | { title: string; body: string; label: string; run: () => Promise<void> }>(null)
  const [bulkOpen, setBulkOpen] = useState(false)
  const importRef = useRef<HTMLInputElement>(null)
  const cookieImportRef = useRef<HTMLInputElement>(null)
  const cookieBulkImportRef = useRef<HTMLInputElement>(null)
  const [cookieTarget, setCookieTarget] = useState<string | null>(null)
  const [cookieBulkBusy, setCookieBulkBusy] = useState(false)
  const toast = useToast()

  const load = useCallback(async () => {
    try {
      setError(null)
      const [p, g, w, m, t, pp, active] = await Promise.all([
        profilesAPI.getProfiles({ page: 1, per_page: 100 }), groupsAPI.list(), operationsAPI.getWorkspace(), operationsAPI.getMembers(), operationsAPI.getTags(), operationsAPI.getProxyPools(), browsersAPI.active(),
      ])
      setProfiles(p.profiles); setGroups(g.groups); setWorkspace(w); setMembers(m); setTags(t); setPools(pp); setRunning(new Set(active.active_browsers.map((x) => x.profile_id)))
      const rows = await Promise.all(p.profiles.map(async (profile) => [profile.id, await operationsAPI.getProfileOperations(profile.id)] as const))
      setOps(Object.fromEntries(rows))
    } catch (e) { setError(String(e instanceof Error ? e.message : e)) }
    finally { setLoading(false) }
  }, [])

  useEffect(() => { load() }, [load])

  const groupNames = useMemo(() => new Map(groups.map((g) => [g.id, g.name])), [groups])
  const memberNames = useMemo(() => new Map(members.map((m) => [m.id, m.username])), [members])
  const poolNames = useMemo(() => new Map(pools.map((p) => [p.id, p.name])), [pools])
  const tagNames = useMemo(() => new Map(tags.map((t) => [t.id, t.name])), [tags])

  const visible = useMemo(() => {
    const needle = search.trim().toLowerCase()
    return profiles.filter((p) => {
      const o = ops[p.id]
      if (statusFilter !== 'all' && p.status !== statusFilter) return false
      if (groupFilter !== 'all' && p.group !== groupFilter) return false
      if (ownerFilter !== 'all' && (o?.owner_id ?? '') !== ownerFilter) return false
      if (tagFilter !== 'all' && !(o?.tag_ids ?? []).includes(tagFilter)) return false
      if (!needle) return true
      return [p.name, p.id, groupNames.get(p.group ?? '') ?? '', ...(o?.tags.map((t) => t.name) ?? [])].join(' ').toLowerCase().includes(needle)
    })
  }, [profiles, ops, search, statusFilter, groupFilter, ownerFilter, tagFilter, groupNames])

  const allSelected = visible.length > 0 && visible.every((p) => selected.has(p.id))
  const teamMode = workspace?.workspace_type === 'team'

  async function action(id: string, fn: () => Promise<void>) { setBusy((s) => new Set(s).add(id)); try { await fn() } finally { setBusy((s) => { const n = new Set(s); n.delete(id); return n }) } }
  async function toggleRun(p: Profile) {
    await action(p.id, async () => { try { if (running.has(p.id)) await profilesAPI.closeProfile(p.id); else await profilesAPI.startProfile(p.id); const active = await browsersAPI.active(); setRunning(new Set(active.active_browsers.map((x) => x.profile_id))) } catch (e) { toast('error', 'Browser action failed', String(e)) } })
  }

  function toggle(id: string) { setSelected((s) => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); return n }) }
  function toggleAll() { setSelected(allSelected ? new Set() : new Set(visible.map((p) => p.id))) }
  async function bulkApply(data: ProfileOperationsPatch) { const ids = [...selected]; if (!ids.length) return; try { await operationsAPI.bulkUpdate(ids, data); await load(); setBulkOpen(false); toast('ok', `Updated ${ids.length} profiles`) } catch (e) { toast('error', 'Bulk update failed', String(e)) } }

  async function downloadCookies(p: Profile) {
    await action(`cookies-export:${p.id}`, async () => {
      try {
        const blob = await exportCookies(p.id)
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a'); a.href = url; a.download = `${p.name.replace(/[^A-Za-z0-9_.-]+/g, '-') || p.id}.cookies.json`; a.click(); URL.revokeObjectURL(url)
      } catch (e) { toast('error', 'Cookie export failed', String(e)) }
    })
  }

  async function handleCookieImport(file: File) {
    if (!cookieTarget) return
    await action(`cookies-import:${cookieTarget}`, async () => {
      try { const result = await importCookies(cookieTarget, file); toast('ok', 'Cookies imported', `${result.imported} cookies`); await load() }
      catch (e) { toast('error', 'Cookie import failed', String(e)) }
    })
    setCookieTarget(null); if (cookieImportRef.current) cookieImportRef.current.value = ''
  }

  async function exportSelectedCookies() {
    const ids = [...selected]; if (!ids.length) return
    try {
      const blob = await exportCookiesBulk(ids); const url = URL.createObjectURL(blob); const a = document.createElement('a'); a.href = url; a.download = 'triada-cookie-export.zip'; a.click(); URL.revokeObjectURL(url)
      toast('ok', 'Cookies exported', `${ids.length} profiles`)
    } catch (e) { toast('error', 'Bulk cookie export failed', String(e)) }
  }

  async function handleBulkCookieImport(file: File) {
    setCookieBulkBusy(true)
    try {
      const result = await importCookiesBulk(file)
      toast(result.error_count ? 'info' : 'ok', 'Bulk account import complete', `${result.created_count} created · ${result.error_count} errors`)
      await load()
    } catch (e) { toast('error', 'Bulk account import failed', String(e)) }
    finally { setCookieBulkBusy(false); if (cookieBulkImportRef.current) cookieBulkImportRef.current.value = '' }
  }

  function askDelete(p: Profile) { setConfirm({ title: 'Delete profile', body: `"${p.name}" and its browser data will be removed.`, label: 'Delete', run: async () => { await profilesAPI.deleteProfile(p.id); await load(); toast('ok', 'Profile deleted', p.name) } }) }

  if (loading) return <p className="px-5 py-8 text-ink-faint">Loading profiles…</p>
  if (error) return <EmptyState icon={<RefreshCw size={18} />} title="Cannot load profiles" body={error} />

  return <>
    <header className="sticky top-0 z-20 flex min-h-[58px] items-center justify-between gap-3 border-b border-line bg-canvas/90 px-5 backdrop-blur">
      <div><h1 className="text-[15px] font-semibold">Profiles</h1><p className="text-[11px] text-ink-faint">{profiles.length} total · {selected.size} selected {teamMode ? '· Team workspace' : '· Personal workspace'}</p></div>
      <div className="flex flex-wrap items-center justify-end gap-2"><button className="btn btn-default" disabled={cookieBulkBusy} onClick={() => cookieBulkImportRef.current?.click()}><Cookie size={14}/>Import accounts</button><button className="btn btn-default" disabled={!selected.size} onClick={exportSelectedCookies}><Download size={14}/>Export cookies</button><button className="btn btn-default" onClick={() => load()}><RefreshCw size={14}/>Refresh</button><button className="btn btn-primary" onClick={() => { setEditing(null); setFormOpen(true) }}><Plus size={14}/>New profile</button></div>
    </header>

    <div className="space-y-3 p-5">
      <div className="flex flex-wrap items-center gap-2">
        <div className="relative min-w-[260px] flex-1"><Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-faint"/><input className="field pl-9" placeholder="Search name, ID, group, tag…" value={search} onChange={(e) => setSearch(e.target.value)} /></div>
        <select className="select" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}><option value="all">All status</option><option value="active">Active</option><option value="inactive">Inactive</option><option value="archived">Archived</option></select>
        <select className="select" value={groupFilter} onChange={(e) => setGroupFilter(e.target.value)}><option value="all">All groups</option>{groups.map((g) => <option key={g.id} value={g.id}>{g.name}</option>)}</select>
        {teamMode && <select className="select" value={ownerFilter} onChange={(e) => setOwnerFilter(e.target.value)}><option value="all">All owners</option>{members.map((m) => <option key={m.id} value={m.id}>{m.username}</option>)}</select>}
        <select className="select" value={tagFilter} onChange={(e) => setTagFilter(e.target.value)}><option value="all">All tags</option>{tags.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}</select>
      </div>

      <input ref={cookieBulkImportRef} type="file" accept=".zip,application/zip" className="hidden" onChange={(e) => { const f = e.target.files?.[0]; if (f) void handleBulkCookieImport(f) }} />
      <input ref={cookieImportRef} type="file" accept=".json,.cookies.json,application/json" className="hidden" onChange={(e) => { const f = e.target.files?.[0]; if (f) void handleCookieImport(f) }} />

      {selected.size > 0 && <div className="flex flex-wrap items-center gap-2 rounded-lg border border-line bg-surface px-3 py-2"><span className="text-[11px] text-ink-dim">{selected.size} selected</span><button className="btn btn-default" onClick={() => setBulkOpen(true)}><Filter size={13}/>Bulk manage</button><button className="btn btn-ghost" onClick={() => setSelected(new Set())}>Clear</button></div>}

      <div className="panel overflow-hidden">
        <div className="overflow-x-auto"><table className="w-full text-left text-[12px]"><thead className="border-b border-line text-ink-faint"><tr><th className="w-10 px-3 py-2"><input type="checkbox" checked={allSelected} onChange={toggleAll}/></th><th className="px-3 py-2">Profile</th><th className="px-3 py-2">Status</th><th className="px-3 py-2">Proxy</th><th className="px-3 py-2">Tags</th>{teamMode && <th className="px-3 py-2">Ownership</th>}<th className="px-3 py-2">Last active</th><th className="w-[150px] px-3 py-2">Actions</th></tr></thead>
        <tbody className="divide-y divide-line">
          {visible.map((p) => { const o = ops[p.id]; const [proxyLabel, proxyToneName] = proxyTone(p); const isRunning = running.has(p.id); return <tr key={p.id} className="hover:bg-raised/40">
            <td className="px-3 py-3"><input type="checkbox" checked={selected.has(p.id)} onChange={() => toggle(p.id)}/></td>
            <td className="px-3 py-3"><div className="font-medium">{p.name}</div><div className="font-mono text-[10px] text-ink-faint">{p.id} · {OS_LABELS[p.browser_settings?.os] ?? p.browser_settings?.os}</div><div className="text-[10px] text-ink-faint">{groupNames.get(p.group ?? '') ?? 'No group'}</div></td>
            <td className="px-3 py-3">{isRunning ? <Pill tone="ok">Running</Pill> : <Pill>{p.status}</Pill>}</td>
            <td className="px-3 py-3"><div>{formatProxyString(p.proxy_config)}</div><Pill tone={proxyToneName as any}>{proxyLabel}</Pill>{o?.proxy_pool_id && <div className="mt-1 text-[10px] text-ink-faint">Pool: {poolNames.get(o.proxy_pool_id) ?? '—'}</div>}</td>
            <td className="max-w-[220px] px-3 py-3"><div className="flex flex-wrap gap-1">{o?.tags.map((t) => <Pill key={t.id}>{t.name}</Pill>)}{!o?.tags.length && <span className="text-ink-faint">—</span>}</div></td>
            {teamMode && <td className="px-3 py-3"><div>{memberNames.get(o?.assigned_user_id ?? '') ?? 'Unassigned'}</div><div className="text-[10px] text-ink-faint">Owner: {memberNames.get(o?.owner_id ?? '') ?? '—'}</div></td>}
            <td className="px-3 py-3 text-ink-dim">{formatLastUsed(p.last_used)}</td>
            <td className="px-3 py-3"><div className="flex items-center gap-1"><button className="icon-btn" title={isRunning ? 'Stop' : 'Launch'} disabled={busy.has(p.id)} onClick={() => toggleRun(p)}>{isRunning ? <Square size={13}/> : <Play size={13}/>}</button><button className="icon-btn" title="Edit" onClick={() => { setEditing(p); setFormOpen(true) }}><Pencil size={13}/></button><button className="icon-btn" title="Operations" onClick={() => setOperationsFor(p)}><Users size={13}/></button><button className="icon-btn" title="Export cookies" disabled={busy.has(`cookies-export:${p.id}`)} onClick={() => downloadCookies(p)}><Download size={13}/></button><button className="icon-btn" title="Import cookies" onClick={() => { setCookieTarget(p.id); setTimeout(() => cookieImportRef.current?.click(), 0) }}><Upload size={13}/></button><button className="icon-btn text-danger" title="Delete" onClick={() => askDelete(p)}><Trash2 size={13}/></button></div></td>
          </tr> })}
          {!visible.length && <tr><td colSpan={teamMode ? 8 : 7} className="px-4 py-12 text-center text-ink-faint">No profiles match these filters.</td></tr>}
        </tbody></table></div>
      </div>
    </div>

    <ProfileForm
      open={formOpen}
      profile={editing}
      groups={groups}
      onSaved={load}
      onClose={() => setFormOpen(false)}
    />
    {operationsFor && <OperationsModal profile={operationsFor} members={members} tags={tags} pools={pools} current={ops[operationsFor.id]} onClose={() => setOperationsFor(null)} onSaved={() => { setOperationsFor(null); load() }} />}
    {bulkOpen && <BulkModal members={members} tags={tags} pools={pools} teamMode={teamMode} onClose={() => setBulkOpen(false)} onApply={bulkApply} />}
    {confirm && <ConfirmDialog open title={confirm.title} body={confirm.body} confirmLabel={confirm.label} onCancel={() => setConfirm(null)} onConfirm={async () => { await confirm.run(); setConfirm(null) }} />}
  </>
}

function OperationsModal({ profile, members, tags, pools, current, onClose, onSaved }: { profile: Profile; members: WorkspaceMember[]; tags: TriadaTag[]; pools: ProxyPool[]; current?: ProfileOperations; onClose: () => void; onSaved: () => void }) {
  const [owner, setOwner] = useState(current?.owner_id ?? '')
  const [assigned, setAssigned] = useState(current?.assigned_user_id ?? '')
  const [pool, setPool] = useState(current?.proxy_pool_id ?? '')
  const [selectedTags, setSelectedTags] = useState<string[]>(current?.tag_ids ?? [])
  const [saving, setSaving] = useState(false)
  async function save() {
    setSaving(true)
    try {
      await operationsAPI.updateProfileOperations(profile.id, {
        owner: owner ? { action: 'set', value: owner } : { action: 'clear' },
        assigned_user: assigned ? { action: 'set', value: assigned } : { action: 'clear' },
        proxy_pool: pool ? { action: 'set', value: pool } : { action: 'clear' },
        tags: { action: 'set', value: selectedTags },
      })
      onSaved()
    } finally { setSaving(false) }
  }
  return <Modal open onClose={onClose} title={`Operations · ${profile.name}`}>
    <div className="space-y-4 p-1"><p className="text-[11px] text-ink-faint">Operational metadata is separate from browser identity and can change without touching the fingerprint.</p>
      <Field label="Owner"><select className="select w-full" value={owner} onChange={(e) => setOwner(e.target.value)}><option value="">No owner</option>{members.map((m) => <option key={m.id} value={m.id}>{m.username} · {m.role}</option>)}</select></Field>
      <Field label="Assigned buyer"><select className="select w-full" value={assigned} onChange={(e) => setAssigned(e.target.value)}><option value="">Unassigned</option>{members.map((m) => <option key={m.id} value={m.id}>{m.username}</option>)}</select></Field>
      <Field label="Proxy pool"><select className="select w-full" value={pool} onChange={(e) => setPool(e.target.value)}><option value="">No pool</option>{pools.map((p) => <option key={p.id} value={p.id}>{p.name} · {p.country ?? '—'} · {p.profile_count}</option>)}</select></Field>
      <Field label="Tags"><div className="flex flex-wrap gap-2">{tags.map((t) => <label key={t.id} className="inline-flex items-center gap-1.5 rounded border border-line px-2 py-1 text-[11px]"><input type="checkbox" checked={selectedTags.includes(t.id)} onChange={() => setSelectedTags((s) => s.includes(t.id) ? s.filter((x) => x !== t.id) : [...s, t.id])}/>{t.name}</label>)}</div></Field>
      <div className="flex justify-end gap-2"><button className="btn btn-default" onClick={onClose}>Cancel</button><button className="btn btn-primary" disabled={saving} onClick={save}>{saving ? 'Saving…' : 'Save operations'}</button></div>
    </div>
  </Modal>
}

function BulkModal({ members, tags, pools, teamMode, onClose, onApply }: { members: WorkspaceMember[]; tags: TriadaTag[]; pools: ProxyPool[]; teamMode: boolean; onClose: () => void; onApply: (data: ProfileOperationsPatch) => Promise<void> }) {
  const [owner, setOwner] = useState(''); const [assigned, setAssigned] = useState(''); const [pool, setPool] = useState(''); const [tag, setTag] = useState('')
  return <Modal open onClose={onClose} title="Bulk manage"><div className="space-y-4"><p className="text-[11px] text-ink-faint">Only populated fields are applied. Leave a field as No change to preserve current values.</p>
    {teamMode && <><Field label="Owner"><select className="select w-full" value={owner} onChange={(e) => setOwner(e.target.value)}><option value="">No change</option><option value="__clear">Clear owner</option>{members.map((m) => <option key={m.id} value={m.id}>{m.username}</option>)}</select></Field><Field label="Assigned buyer"><select className="select w-full" value={assigned} onChange={(e) => setAssigned(e.target.value)}><option value="">No change</option><option value="__clear">Clear assignment</option>{members.map((m) => <option key={m.id} value={m.id}>{m.username}</option>)}</select></Field></>}
    <Field label="Proxy pool"><select className="select w-full" value={pool} onChange={(e) => setPool(e.target.value)}><option value="">No change</option><option value="__clear">Clear pool</option>{pools.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}</select></Field>
    <Field label="Set one tag"><select className="select w-full" value={tag} onChange={(e) => setTag(e.target.value)}><option value="">No change</option>{tags.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}</select></Field>
    <div className="flex justify-end gap-2"><button className="btn btn-default" onClick={onClose}>Cancel</button><button className="btn btn-primary" onClick={() => {
      const field = (value: string) => value === '__clear' ? ({ action: 'clear' as const }) : value ? ({ action: 'set' as const, value }) : ({ action: 'unchanged' as const })
      onApply({ owner: field(owner), assigned_user: field(assigned), proxy_pool: field(pool), ...(tag ? { tags: { action: 'set', value: [tag] } as const } : {}) })
    }}>Apply</button></div>
  </div></Modal>
}
function Field({ label, children }: { label: string; children: React.ReactNode }) { return <label className="block"><span className="mb-1.5 block text-[11px] text-ink-dim">{label}</span>{children}</label> }
