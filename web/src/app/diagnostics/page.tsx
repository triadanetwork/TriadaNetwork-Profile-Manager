'use client'

import { useCallback, useEffect, useState } from 'react'
import { CheckCircle2, CircleAlert, RefreshCw } from 'lucide-react'
import { desktopAPI, type DesktopDiagnostics } from '@/lib/api'
import { useToast } from '@/components/toast'

export default function DiagnosticsPage() {
  const [data, setData] = useState<DesktopDiagnostics | null>(null)
  const [loading, setLoading] = useState(true)
  const toast = useToast()
  const load = useCallback(async () => { try { setData(await desktopAPI.diagnostics()) } catch(e) { toast('error','Diagnostics unavailable',String(e)) } finally { setLoading(false) } }, [toast])
  useEffect(() => { load() }, [load])
  const row = (label: string, value: string | number | boolean, ok?: boolean) => <div className="flex items-center justify-between border-b border-line py-3 last:border-0"><span className="text-sm text-ink-dim">{label}</span><span className="flex items-center gap-2 font-mono text-xs text-ink">{ok !== undefined ? (ok ? <CheckCircle2 size={14} className="text-ok"/> : <CircleAlert size={14} className="text-warn"/>) : null}{String(value)}</span></div>
  return <div className="page-shell"><header className="page-header"><div><div className="eyebrow">TRIADA NETWORK / DESKTOP</div><h1>Diagnostics</h1><p className="page-subtitle">Local runtime health and support information.</p></div><button className="btn btn-default" onClick={load}><RefreshCw size={14}/> Refresh</button></header><div className="panel p-4"><div className="eyebrow mb-2">RUNTIME</div>{loading && !data ? <div className="p-6 text-sm text-ink-faint">Checking desktop runtime…</div> : data ? <div>{row('Platform',data.platform)}{row('Python',data.python)}{row('Camoufox engine',data.camoufox_available?'Available':'Missing',data.camoufox_available)}{row('Active browsers',data.active_browsers)}{row('Disk free',`${data.disk_free_gb} GB`,data.disk_free_gb > 5)}{row('Memory usage',`${data.memory_percent}%`,data.memory_percent < 90)}{row('Database',data.database_path)}{row('Logs',data.log_directory)}</div> : <div className="p-6 text-sm text-ink-faint">No diagnostics available.</div>}</div></div>
}
