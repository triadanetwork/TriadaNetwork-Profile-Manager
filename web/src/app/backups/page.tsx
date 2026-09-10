'use client'

import { useRef, useState } from 'react'
import { ArchiveRestore, Download, ShieldCheck, Upload } from 'lucide-react'
import { desktopAPI } from '@/lib/api'
import { useToast } from '@/components/toast'

export default function BackupsPage(){
  const [include,setInclude]=useState(false); const [busy,setBusy]=useState(false); const input=useRef<HTMLInputElement>(null); const toast=useToast()
  const create=async()=>{setBusy(true); try{const r=await desktopAPI.createBackup(include); toast('ok','Backup created',r.path)}catch(e){toast('error','Backup failed',String(e))}finally{setBusy(false)}}
  const restore=async(file:File)=>{setBusy(true); try{const m=await desktopAPI.inspectBackup(file); toast('ok','Backup verified',String(m.created_at ?? 'Ready to restore')); if(confirm('Restore this verified backup? Running browsers must be closed.')){await desktopAPI.restoreBackup(file,include); toast('ok','Backup restored','Restart Triada to reload local data.')}}catch(e){toast('error','Restore failed',String(e))}finally{setBusy(false)}}
  return <div className="page-shell"><header className="page-header"><div><div className="eyebrow">TRIADA NETWORK / DESKTOP</div><h1>Backups</h1><p className="page-subtitle">Create and restore local workspace backups.</p></div></header><div className="grid gap-3 lg:grid-cols-2"><div className="panel p-5"><ShieldCheck size={18}/><h2 className="mt-3">Create backup</h2><p className="mt-1 text-sm text-ink-dim">SQLite snapshot, manifest and checksum. Browser data is optional.</p><label className="mt-4 flex items-center gap-2 text-sm"><input type="checkbox" checked={include} onChange={e=>setInclude(e.target.checked)}/> Include browser data</label><button className="btn btn-primary mt-5" disabled={busy} onClick={create}><Download size={13}/> Create backup</button></div><div className="panel p-5"><ArchiveRestore size={18}/><h2 className="mt-3">Restore backup</h2><p className="mt-1 text-sm text-ink-dim">The archive is verified before restore. Close all running browsers first.</p><label className="mt-5 btn btn-default inline-flex cursor-pointer"><Upload size={13}/> Choose .tnb<input ref={input} hidden type="file" accept=".tnb" onChange={e=>e.target.files?.[0]&&restore(e.target.files[0])}/></label></div></div></div>
}
