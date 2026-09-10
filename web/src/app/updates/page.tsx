'use client'

import { useEffect, useState } from 'react'
import { RefreshCw, Download, PlayCircle } from 'lucide-react'
import { updateAPI, type PendingUpdate, type UpdateCheckResult } from '@/lib/api'
import { useToast } from '@/components/toast'

export default function UpdatesPage() {
  const toast = useToast()
  const [channel, setChannel] = useState<'stable' | 'beta'>('stable')
  const [manifestUrl, setManifestUrl] = useState('')
  const [check, setCheck] = useState<UpdateCheckResult | null>(null)
  const [pending, setPending] = useState<PendingUpdate | null>(null)
  const [busy, setBusy] = useState(false)

  const loadPending = async () => { try { setPending(await updateAPI.pending()) } catch { /* local update status unavailable */ } }
  useEffect(() => { void loadPending() }, [])

  const doCheck = async () => {
    setBusy(true)
    try { const result = await updateAPI.check({ manifest_url: manifestUrl || undefined, channel }); setCheck(result); toast('ok', 'Update check complete', result.update_available ? `Version ${result.version} is available` : 'You are up to date') }
    catch (e) { toast('error', 'Update check failed', String(e)) }
    finally { setBusy(false) }
  }

  const stage = async () => {
    setBusy(true)
    try { const result = await updateAPI.stage({ manifest_url: manifestUrl || undefined, channel }); setCheck(result); await loadPending(); toast('ok', 'Update staged', result.version) }
    catch (e) { toast('error', 'Update staging failed', String(e)) }
    finally { setBusy(false) }
  }

  const install = async () => {
    if (!window.confirm('Install the verified update and restart Triada Network?')) return
    setBusy(true)
    try { await updateAPI.install(); toast('ok', 'Update installer started', 'Triada Network will restart') }
    catch (e) { toast('error', 'Update install failed', String(e)) }
    finally { setBusy(false) }
  }

  return <div className="p-6">
    <div className="mb-6 flex items-end justify-between gap-4">
      <div><h1 className="text-xl font-semibold">Update Center</h1><p className="mt-1 text-sm text-ink-dim">Verified application updates for the local desktop installation.</p></div>
      <div className="flex items-center gap-2"><select className="select" value={channel} onChange={(e) => setChannel(e.target.value as 'stable'|'beta')}><option value="stable">Stable</option><option value="beta">Beta</option></select><button className="btn btn-default" onClick={doCheck} disabled={busy}><RefreshCw size={14}/> Check</button></div>
    </div>

    <div className="grid gap-4 md:grid-cols-2">
      <section className="panel p-4">
        <div className="text-xs uppercase tracking-[0.12em] text-ink-faint">Manifest</div>
        <input className="input mt-3 w-full" placeholder="https://updates.example.com/stable.json" value={manifestUrl} onChange={(e) => setManifestUrl(e.target.value)} />
        <p className="mt-2 text-xs text-ink-faint">The updater accepts HTTPS manifests only.</p>
      </section>

      <section className="panel p-4">
        <div className="text-xs uppercase tracking-[0.12em] text-ink-faint">Current state</div>
        <div className="mt-3 space-y-2 text-sm">
          <div className="flex justify-between"><span>Channel</span><span className="font-mono">{channel}</span></div>
          <div className="flex justify-between"><span>Pending update</span><span>{pending?.pending ? `${pending.pending.version} · ${pending.pending.channel}` : 'None'}</span></div>
        </div>
      </section>

      {check && <section className="panel p-4 md:col-span-2">
        <div className="flex items-center justify-between"><div><div className="text-xs uppercase tracking-[0.12em] text-ink-faint">Result</div><div className="mt-1 text-lg font-medium">{check.update_available ? `Version ${check.version} available` : 'No update available'}</div></div>{check.update_available && <button className="btn btn-default" onClick={stage} disabled={busy}><Download size={14}/> Stage update</button>}</div>
      </section>}

      {pending?.pending && <section className="panel p-4 md:col-span-2">
        <div className="flex items-center justify-between"><div><div className="text-xs uppercase tracking-[0.12em] text-ink-faint">Verified package</div><div className="mt-1 font-medium">{pending.pending.version} · {pending.pending.channel}</div><div className="mt-1 text-xs text-ink-faint">SHA-256: <span className="font-mono">{pending.pending.sha256}</span></div></div><button className="btn btn-primary" onClick={install} disabled={busy}><PlayCircle size={14}/> Install & restart</button></div>
      </section>}
    </div>
  </div>
}
