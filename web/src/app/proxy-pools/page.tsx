'use client'

import { useEffect, useMemo, useState } from 'react'
import { Activity, CheckCircle2, Plus, RefreshCw, Server, Trash2, Unplug, Upload } from 'lucide-react'
import { Modal } from '@/components/modal'
import {
  operationsAPI,
  profilesAPI,
  proxyAPI,
  type Profile,
  type ProxyInventory,
  type ProxyPool,
} from '@/lib/api'

const statusTone: Record<string, string> = {
  healthy: 'text-ok',
  active: 'text-ok',
  degraded: 'text-warn',
  unknown: 'text-ink-faint',
  unhealthy: 'text-danger',
  disabled: 'text-ink-faint',
  retired: 'text-danger',
}

export default function ProxyManagerPage() {
  const [proxies, setProxies] = useState<ProxyInventory[]>([])
  const [pools, setPools] = useState<ProxyPool[]>([])
  const [profiles, setProfiles] = useState<Profile[]>([])
  const [poolFilter, setPoolFilter] = useState('all')
  const [statusFilter, setStatusFilter] = useState('all')
  const [proxyOpen, setProxyOpen] = useState(false)
  const [bulkOpen, setBulkOpen] = useState(false)
  const [bulkFile, setBulkFile] = useState<File | null>(null)
  const [bulkPoolId, setBulkPoolId] = useState('')
  const [poolOpen, setPoolOpen] = useState(false)
  const [assignFor, setAssignFor] = useState<ProxyInventory | null>(null)
  const [assignProfile, setAssignProfile] = useState('')
  const [busy, setBusy] = useState<string | null>(null)
  const [proxyForm, setProxyForm] = useState({
    name: '', proxy_type: 'http', server: '', username: '', password: '', provider: '', country: '', pool_id: '',
  })
  const [poolForm, setPoolForm] = useState({ name: '', provider: '', country: 'US', proxy_type: 'residential' })

  async function load() {
    const [proxyResult, poolResult, profileResult] = await Promise.all([
      proxyAPI.list({
        pool_id: poolFilter === 'all' ? undefined : poolFilter,
        status: statusFilter === 'all' ? undefined : statusFilter,
      }),
      operationsAPI.getProxyPools(),
      profilesAPI.getProfiles({ page: 1, per_page: 100 }),
    ])
    setProxies(proxyResult.proxies)
    setPools(poolResult)
    setProfiles(profileResult.profiles)
  }

  useEffect(() => {
    load().catch(() => undefined)
  }, [poolFilter, statusFilter])

  const healthy = useMemo(() => proxies.filter((p) => p.status === 'healthy').length, [proxies])
  const assigned = useMemo(() => proxies.filter((p) => p.assigned_profile_id).length, [proxies])

  async function createProxy() {
    if (!proxyForm.name.trim() || !proxyForm.server.trim()) return
    setBusy('proxy-create')
    try {
      await proxyAPI.create({
        ...proxyForm,
        pool_id: proxyForm.pool_id || null,
        username: proxyForm.username || null,
        password: proxyForm.password || null,
      })
      setProxyOpen(false)
      setProxyForm({ name: '', proxy_type: 'http', server: '', username: '', password: '', provider: '', country: '', pool_id: '' })
      await load()
    } finally {
      setBusy(null)
    }
  }

  async function createPool() {
    if (!poolForm.name.trim()) return
    setBusy('pool-create')
    try {
      await operationsAPI.createProxyPool(poolForm)
      setPoolOpen(false)
      setPoolForm({ name: '', provider: '', country: 'US', proxy_type: 'residential' })
      await load()
    } finally {
      setBusy(null)
    }
  }

  async function check(id: string) {
    setBusy(id)
    try {
      await proxyAPI.check(id)
      await load()
    } finally {
      setBusy(null)
    }
  }

  async function unassign(id: string) {
    setBusy(id)
    try {
      await proxyAPI.unassign(id)
      await load()
    } finally {
      setBusy(null)
    }
  }

  async function assign() {
    if (!assignFor || !assignProfile) return
    setBusy(assignFor.id)
    try {
      await proxyAPI.assign(assignFor.id, assignProfile)
      setAssignFor(null)
      setAssignProfile('')
      await load()
    } finally {
      setBusy(null)
    }
  }

  async function removeProxy(id: string) {
    if (!window.confirm('Delete this proxy from inventory?')) return
    setBusy(id)
    try {
      await proxyAPI.remove(id)
      await load()
    } finally {
      setBusy(null)
    }
  }

  return (
    <div>
      <header className="sticky top-0 z-20 flex min-h-[58px] items-center justify-between border-b border-line bg-canvas/90 px-5 backdrop-blur">
        <div>
          <h1 className="text-[15px] font-semibold">Proxy Manager</h1>
          <p className="text-[11px] text-ink-faint">Inventory, pools, health and profile assignment.</p>
        </div>
        <div className="flex gap-2">
          <button className="btn btn-default" onClick={() => load()}><RefreshCw size={14} />Refresh</button>
          <button className="btn btn-default" onClick={() => setPoolOpen(true)}><Plus size={14} />New pool</button>
          <button className="btn btn-default" onClick={() => setBulkOpen(true)}><Upload size={14} />Import proxies</button><button className="btn btn-primary" onClick={() => setProxyOpen(true)}><Plus size={14} />Add proxy</button>
        </div>
      </header>

      <div className="space-y-4 p-5">
        <div className="grid grid-cols-3 gap-3">
          <Stat icon={Server} label="Inventory" value={String(proxies.length)} />
          <Stat icon={CheckCircle2} label="Healthy" value={String(healthy)} />
          <Stat icon={Activity} label="Assigned" value={String(assigned)} />
        </div>

        <div className="flex flex-wrap gap-2">
          <select className="select" value={poolFilter} onChange={(e) => setPoolFilter(e.target.value)}>
            <option value="all">All pools</option>
            {pools.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
          <select className="select" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
            <option value="all">All statuses</option>
            {['healthy', 'degraded', 'unhealthy', 'unknown', 'disabled', 'retired'].map((x) => <option key={x} value={x}>{x}</option>)}
          </select>
        </div>

        {pools.length > 0 && (
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {pools.map((p) => (
              <button key={p.id} type="button" className={`panel px-4 py-3 text-left transition-colors hover:bg-raised/40 ${poolFilter === p.id ? 'border-signal' : ''}`} onClick={() => setPoolFilter(poolFilter === p.id ? 'all' : p.id)}>
                <div className="flex items-center justify-between"><div className="font-medium text-[12px]">{p.name}</div><span className="text-[10px] text-ink-faint">{p.status}</span></div>
                <div className="mt-2 flex gap-4 text-[10px] text-ink-faint"><span>{p.proxy_count} proxies</span><span>{p.profile_count} profiles</span></div>
              </button>
            ))}
          </div>
        )}

        <div className="panel overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-[12px]">
              <thead className="border-b border-line text-ink-faint"><tr><th className="px-4 py-2">Proxy</th><th>Endpoint</th><th>Pool</th><th>Health</th><th>Exit</th><th>Assigned</th><th className="w-[180px]">Actions</th></tr></thead>
              <tbody className="divide-y divide-line">
                {proxies.map((p) => (
                  <tr key={p.id} className="hover:bg-raised/40">
                    <td className="px-4 py-3"><div className="font-medium">{p.name}</div><div className="font-mono text-[10px] text-ink-faint">{p.provider || 'No provider'}{p.country ? ` · ${p.country}` : ''}</div></td>
                    <td><div className="font-mono text-[11px]">{p.proxy_type}://{p.server}</div><div className="text-[10px] text-ink-faint">{p.username_set ? 'Authenticated' : 'No auth'}</div></td>
                    <td>{p.pool_name || '—'}</td>
                    <td><span className={statusTone[p.status] || 'text-ink-dim'}>● {p.status}</span>{p.latency_ms != null && <div className="text-[10px] text-ink-faint">{p.latency_ms} ms</div>}</td>
                    <td>{p.exit_ip || '—'}{p.exit_country && <div className="text-[10px] text-ink-faint">{p.exit_country} · {p.exit_timezone || '—'}</div>}</td>
                    <td>{p.assigned_profile_name ? <div>{p.assigned_profile_name}</div> : <span className="text-ink-faint">Unassigned</span>}</td>
                    <td><div className="flex items-center gap-1"><button className="icon-btn" disabled={busy === p.id} title="Health check" onClick={() => check(p.id)}><RefreshCw size={13} /></button>{p.assigned_profile_id ? <button className="icon-btn" disabled={busy === p.id} title="Unassign" onClick={() => unassign(p.id)}><Unplug size={13} /></button> : <button className="icon-btn" disabled={busy === p.id} title="Assign to profile" onClick={() => setAssignFor(p)}><Server size={13} /></button>}<button className="icon-btn text-danger" disabled={busy === p.id} title="Delete" onClick={() => removeProxy(p.id)}><Trash2 size={13} /></button></div></td>
                  </tr>
                ))}
                {!proxies.length && <tr><td colSpan={7} className="px-4 py-12 text-center text-ink-faint">No proxies in inventory. Add a proxy or create a pool first.</td></tr>}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {assignFor && (
        <Modal open onClose={() => { setAssignFor(null); setAssignProfile('') }} title={`Assign · ${assignFor.name}`}>
          <div className="space-y-3 p-1">
            <p className="text-[11px] text-ink-faint">The proxy becomes the profile's managed proxy and replaces its current proxy configuration.</p>
            <Field label="Profile"><select className="select w-full" value={assignProfile} onChange={(e) => setAssignProfile(e.target.value)}><option value="">Select profile</option>{profiles.map((p) => <option key={p.id} value={p.id}>{p.name} · {p.id}</option>)}</select></Field>
            <div className="flex justify-end gap-2 pt-2"><button className="btn btn-default" onClick={() => setAssignFor(null)}>Cancel</button><button className="btn btn-primary" disabled={!assignProfile || busy === assignFor.id} onClick={assign}>{busy === assignFor.id ? 'Assigning…' : 'Assign proxy'}</button></div>
          </div>
        </Modal>
      )}

      <Modal open={poolOpen} onClose={() => setPoolOpen(false)} title="New proxy pool">
        <div className="space-y-3 p-1">
          <Field label="Pool name"><input className="field w-full" placeholder="US Residential" value={poolForm.name} onChange={(e) => setPoolForm({ ...poolForm, name: e.target.value })} /></Field>
          <Field label="Provider"><input className="field w-full" placeholder="Provider name" value={poolForm.provider} onChange={(e) => setPoolForm({ ...poolForm, provider: e.target.value })} /></Field>
          <div className="grid grid-cols-2 gap-2"><Field label="Country"><input className="field w-full" value={poolForm.country} onChange={(e) => setPoolForm({ ...poolForm, country: e.target.value })} /></Field><Field label="Type"><select className="select w-full" value={poolForm.proxy_type} onChange={(e) => setPoolForm({ ...poolForm, proxy_type: e.target.value })}><option>residential</option><option>mobile</option><option>datacenter</option><option>isp</option></select></Field></div>
          <div className="flex justify-end gap-2 pt-2"><button className="btn btn-default" onClick={() => setPoolOpen(false)}>Cancel</button><button className="btn btn-primary" disabled={busy === 'pool-create'} onClick={createPool}>{busy === 'pool-create' ? 'Creating…' : 'Create pool'}</button></div>
        </div>
      </Modal>


      <Modal open={bulkOpen} onClose={() => setBulkOpen(false)} title="Import proxies">
        <div className="space-y-3 p-1">
          <p className="text-[11px] text-ink-faint">Supported: one proxy per line (<code>host:port</code>, <code>user:pass@host:port</code>, <code>socks5://user:pass@host:port</code>) or CSV.</p>
          <input type="file" accept=".txt,.csv" onChange={(e) => setBulkFile(e.target.files?.[0] ?? null)} className="field w-full" />
          <Field label="Pool"><select className="select w-full" value={bulkPoolId} onChange={(e) => setBulkPoolId(e.target.value)}><option value="">No pool</option>{pools.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}</select></Field>
          <div className="flex justify-end gap-2"><button className="btn btn-default" onClick={() => setBulkOpen(false)}>Cancel</button><button className="btn btn-primary" disabled={!bulkFile || busy==='bulk'} onClick={async () => { if(!bulkFile) return; setBusy('bulk'); try { await proxyAPI.bulkImportFile(bulkFile, {pool_id: bulkPoolId || undefined}); setBulkOpen(false); setBulkFile(null); setBulkPoolId(''); await load() } finally { setBusy(null) } }}>{busy==='bulk' ? 'Importing…' : 'Import'}</button></div>
        </div>
      </Modal>

      <Modal open={proxyOpen} onClose={() => setProxyOpen(false)} title="Add proxy">
        <div className="space-y-3 p-1">
          <Field label="Name"><input className="field w-full" placeholder="US Residential #001" value={proxyForm.name} onChange={(e) => setProxyForm({ ...proxyForm, name: e.target.value })} /></Field>
          <div className="grid grid-cols-2 gap-2"><Field label="Protocol"><select className="select w-full" value={proxyForm.proxy_type} onChange={(e) => setProxyForm({ ...proxyForm, proxy_type: e.target.value })}><option>http</option><option>https</option><option>socks4</option><option>socks5</option></select></Field><Field label="Country"><input className="field w-full" placeholder="US" value={proxyForm.country} onChange={(e) => setProxyForm({ ...proxyForm, country: e.target.value })} /></Field></div>
          <Field label="Server"><input className="field w-full font-mono" placeholder="host:port" value={proxyForm.server} onChange={(e) => setProxyForm({ ...proxyForm, server: e.target.value })} /></Field>
          <div className="grid grid-cols-2 gap-2"><Field label="Username"><input className="field w-full" value={proxyForm.username} onChange={(e) => setProxyForm({ ...proxyForm, username: e.target.value })} /></Field><Field label="Password"><input className="field w-full" type="password" value={proxyForm.password} onChange={(e) => setProxyForm({ ...proxyForm, password: e.target.value })} /></Field></div>
          <div className="grid grid-cols-2 gap-2"><Field label="Provider"><input className="field w-full" value={proxyForm.provider} onChange={(e) => setProxyForm({ ...proxyForm, provider: e.target.value })} /></Field><Field label="Pool"><select className="select w-full" value={proxyForm.pool_id} onChange={(e) => setProxyForm({ ...proxyForm, pool_id: e.target.value })}><option value="">No pool</option>{pools.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}</select></Field></div>
          <div className="flex justify-end gap-2 pt-2"><button className="btn btn-default" onClick={() => setProxyOpen(false)}>Cancel</button><button className="btn btn-primary" disabled={busy === 'proxy-create'} onClick={createProxy}>{busy === 'proxy-create' ? 'Adding…' : 'Add proxy'}</button></div>
        </div>
      </Modal>
    </div>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return <label className="block"><span className="mb-1.5 block text-[11px] text-ink-dim">{label}</span>{children}</label>
}

function Stat({ icon: Icon, label, value }: { icon: React.ComponentType<{ size?: number }>; label: string; value: string }) {
  return <div className="panel px-4 py-3"><div className="flex items-center gap-2 text-ink-faint"><Icon size={14} /><span className="text-[10px] uppercase tracking-[0.12em]">{label}</span></div><div className="mt-2 text-xl font-semibold">{value}</div></div>
}
