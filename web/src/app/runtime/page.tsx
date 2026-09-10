'use client'

import { useCallback, useEffect, useState } from 'react'
import { CheckCircle2, Download, RefreshCw, ShieldAlert, Trash2 } from 'lucide-react'
import { api } from '@/lib/api'
import { useToast } from '@/components/toast'

type Version = { version: string; path?: string | null; installed?: boolean; active?: boolean }
type Runtime = { available: boolean; executable?: string | null; message: string; active_version?: string | null; installed_versions: Version[] }

export default function RuntimePage() {
  const [runtime, setRuntime] = useState<Runtime | null>(null)
  const [specifier, setSpecifier] = useState('official/stable')
  const [busy, setBusy] = useState(false)
  const toast = useToast()
  const load = useCallback(async () => {
    try { setRuntime(await api.get<Runtime>('/api/v1/system/runtime')) }
    catch (e) { toast('error', 'Runtime manager unavailable', String(e)) }
  }, [toast])
  useEffect(() => { load() }, [load])
  const install = async () => { setBusy(true); try { await api.post('/api/v1/system/runtime/install', { specifier: specifier || undefined }); toast('ok', 'Runtime installed'); await load() } catch(e) { toast('error', 'Install failed', String(e)) } finally { setBusy(false) } }
  const activate = async (s: string) => { setBusy(true); try { await api.post('/api/v1/system/runtime/activate', { specifier: s }); toast('ok', 'Runtime activated'); await load() } catch(e) { toast('error', 'Activation failed', String(e)) } finally { setBusy(false) } }
  const remove = async (s: string) => { if (!window.confirm(`Remove runtime ${s}?`)) return; setBusy(true); try { await api.post('/api/v1/system/runtime/remove', { specifier: s }); toast('ok', 'Runtime removed'); await load() } catch(e) { toast('error', 'Removal failed', String(e)) } finally { setBusy(false) } }
  return <div className="page-shell">
    <header className="page-header"><div><div className="eyebrow">TRIADA NETWORK / DESKTOP</div><h1>Browser Runtime</h1><p className="page-subtitle">Install, inspect and activate the local Camoufox runtime used by profiles.</p></div><button className="btn btn-default" onClick={load}><RefreshCw size={14}/> Refresh</button></header>
    <section className="panel p-4"><div className="flex items-center gap-2">{runtime?.available ? <CheckCircle2 size={17}/> : <ShieldAlert size={17}/>}<div><div className="font-medium">{runtime?.available ? 'Runtime manager available' : 'Runtime not ready'}</div><div className="text-xs text-ink-faint">{runtime?.message ?? 'Loading…'}</div></div></div></section>
    <section className="mt-3 panel p-4"><div className="eyebrow">INSTALL</div><h2 className="mt-1">Browser channel or version</h2><div className="mt-4 flex gap-2"><input className="input flex-1" value={specifier} onChange={e => setSpecifier(e.target.value)} placeholder="official/stable"/><button className="btn btn-primary" disabled={busy} onClick={install}><Download size={14}/> Install</button></div><div className="mt-2 text-xs text-ink-faint">Example: <code>official/stable</code>. The desktop app invokes the upstream Camoufox CLI locally.</div></section>
    <section className="mt-3 panel p-4"><div className="mb-4"><div className="eyebrow">INSTALLED</div><h2 className="mt-1">Browser runtimes</h2></div>{runtime?.installed_versions?.length ? <div className="space-y-2">{runtime.installed_versions.map(v => <div key={v.version} className="flex items-center justify-between rounded-md border border-line bg-canvas px-3 py-3"><div><div className="font-mono text-xs">{v.version}</div>{v.path && <div className="mt-1 max-w-[620px] truncate text-[10px] text-ink-faint">{v.path}</div>}</div><div className="flex items-center gap-2">{v.active ? <span className="status-chip">Active</span> : <button className="btn btn-default" disabled={busy} onClick={() => activate(v.version)}>Activate</button>}<button className="btn btn-danger" disabled={busy || v.active} onClick={() => remove(v.version)}><Trash2 size={13}/> Remove</button></div></div>)}</div> : <div className="border border-dashed border-line rounded-md p-10 text-center text-sm text-ink-faint">No installed browser runtimes detected.</div>}</section>
  </div>
}
