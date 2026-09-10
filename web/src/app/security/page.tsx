'use client'

import { useCallback, useEffect, useState } from 'react'
import { CheckCircle2, Download, RefreshCw, Shield, TriangleAlert, Wrench } from 'lucide-react'
import { securityAPI } from '@/lib/api'
import { useToast } from '@/components/toast'

import type { DesktopDataStatus, IntegrityReport } from '@/lib/api'

export default function SecurityPage() {
  const [report, setReport] = useState<IntegrityReport | null>(null)
  const [status, setStatus] = useState<DesktopDataStatus | null>(null)
  const [busy, setBusy] = useState(false)
  const toast = useToast()
  const load = useCallback(async () => {
    setBusy(true)
    try { const [r, s] = await Promise.all([securityAPI.integrity(), securityAPI.status()]); setReport(r); setStatus(s) }
    catch (e) { toast('error', 'Security status failed', String(e)) }
    finally { setBusy(false) }
  }, [toast])
  useEffect(() => { load() }, [load])
  const migrate = async () => { setBusy(true); try { await securityAPI.migrate(); toast('ok', 'Data migration complete'); await load() } catch (e) { toast('error', 'Migration failed', String(e)) } finally { setBusy(false) } }
  const rollback = async () => { if (!window.confirm('Rollback to the last pre-restore database snapshot?')) return; setBusy(true); try { await securityAPI.rollbackLastRestore(); toast('ok', 'Database rolled back', 'Restart Triada Network to reload data.'); await load() } catch (e) { toast('error', 'Rollback failed', String(e)) } finally { setBusy(false) } }
  const quarantine = async () => { if (!window.confirm('Move orphaned profile directories into quarantine?')) return; setBusy(true); try { const r = await securityAPI.quarantineOrphans(); toast('ok', 'Orphans quarantined', `${r.count ?? 0} moved`); await load() } catch (e) { toast('error', 'Quarantine failed', String(e)) } finally { setBusy(false) } }
  const support = async () => { setBusy(true); try { const r = await securityAPI.createSupportBundle(); toast('ok', 'Support bundle created', r.path) } catch (e) { toast('error', 'Support bundle failed', String(e)) } finally { setBusy(false) } }
  return <div className="page-shell">
    <header className="page-header"><div><div className="eyebrow">TRIADA NETWORK / DESKTOP</div><h1>Security & Data</h1><p className="page-subtitle">Integrity, migrations, recovery and protected local data operations.</p></div><button className="btn btn-default" disabled={busy} onClick={load}><RefreshCw size={14}/> Refresh</button></header>
    <section className="panel p-5"><div className="flex items-start gap-3">{report?.ok ? <CheckCircle2 size={20}/> : <TriangleAlert size={20}/>}<div className="flex-1"><h2>Local data integrity</h2><p className="mt-1 text-sm text-ink-dim">SQLite integrity and profile storage reconciliation.</p>{report && <div className="mt-5 grid gap-3 md:grid-cols-4"><div className="stat"><div className="eyebrow">DATABASE</div><div className="mt-1 font-semibold">{report.database.integrity ?? 'unknown'}</div></div><div className="stat"><div className="eyebrow">PROFILES</div><div className="mt-1 font-semibold">{report.profiles.referenced}</div></div><div className="stat"><div className="eyebrow">ORPHANS</div><div className="mt-1 font-semibold">{report.profiles.orphaned.length}</div></div><div className="stat"><div className="eyebrow">RESULT</div><div className="mt-1 font-semibold">{report.ok ? 'HEALTHY' : 'ATTENTION'}</div></div></div>}</div></div></section>
    <section className="mt-3 grid gap-3 md:grid-cols-2"><div className="panel p-5"><Wrench size={18}/><h2 className="mt-3">Local schema</h2><p className="mt-1 text-sm text-ink-dim">Current {status?.migration.current ?? '—'} · Target {status?.migration.target ?? '—'}.</p><button className="btn btn-default mt-4" disabled={busy || status?.migration.up_to_date} onClick={migrate}>Apply migrations</button></div><div className="panel p-5"><Shield size={18}/><h2 className="mt-3">Recovery</h2><p className="mt-1 text-sm text-ink-dim">Rollback becomes available after a restore. Orphaned profile data can be quarantined instead of deleted.</p><div className="mt-4 flex flex-wrap gap-2"><button className="btn btn-default" disabled={busy || !status?.recovery.rollback_available} onClick={rollback}>Rollback restore</button><button className="btn btn-default" disabled={busy || !report?.profiles.orphaned.length} onClick={quarantine}>Quarantine orphans</button></div></div></section>
    <section className="mt-3 panel p-5"><Download size={18}/><h2 className="mt-3">Support bundle</h2><p className="mt-1 text-sm text-ink-dim">Creates diagnostics and redacted logs for troubleshooting. Cookies, proxy passwords and API secrets are excluded.</p><button className="btn btn-default mt-4" disabled={busy} onClick={support}>Create support bundle</button></section>
  </div>
}
