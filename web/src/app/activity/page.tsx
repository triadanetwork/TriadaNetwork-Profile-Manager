'use client'
import { useEffect, useMemo, useState } from 'react'
import { Activity, RefreshCw, Search } from 'lucide-react'
import { operationsAPI, type WorkspaceMember } from '@/lib/api'

function displayAction(action: string) {
  return action.replaceAll('.', ' · ').replaceAll('_', ' ')
}

export default function ActivityPage(){
 const [rows,setRows]=useState<Array<Record<string,unknown>>>([]); const [actions,setActions]=useState<string[]>([]); const [members,setMembers]=useState<WorkspaceMember[]>([]);
 const [action,setAction]=useState(''); const [actor,setActor]=useState(''); const [query,setQuery]=useState(''); const [error,setError]=useState(''); const [loading,setLoading]=useState(false);
 const load=async()=>{setLoading(true);setError('');try{const [r,a,m]=await Promise.all([operationsAPI.getAudit({limit:250,action:action||undefined,actor_user_id:actor||undefined}),operationsAPI.getAuditActions(),operationsAPI.getMembers()]);setRows(r);setActions(a);setMembers(m)}catch(e){setError(e instanceof Error?e.message:'Failed to load activity')}finally{setLoading(false)}};
 useEffect(()=>{load()},[action,actor]);
 const visible=useMemo(()=>{const q=query.trim().toLowerCase();if(!q)return rows;return rows.filter(r=>JSON.stringify(r).toLowerCase().includes(q))},[rows,query]);
 return <><header className="sticky top-0 z-20 flex min-h-[58px] flex-wrap items-center gap-2 border-b border-line bg-canvas/90 px-5 py-2"><div className="mr-auto"><h1 className="text-[15px] font-semibold">Activity</h1><p className="text-[11px] text-ink-faint">Workspace audit trail and operational history.</p></div><button onClick={load} className="btn" disabled={loading}><RefreshCw size={13} className={loading?'animate-spin':''}/>Refresh</button></header>
 <div className="p-5 space-y-3">
  <div className="panel flex flex-wrap gap-2 p-3"><div className="relative min-w-[220px] flex-1"><Search size={13} className="absolute left-2.5 top-2.5 text-ink-faint"/><input value={query} onChange={e=>setQuery(e.target.value)} placeholder="Search activity" className="field pl-8 h-8"/></div><select className="field h-8 w-[210px]" value={action} onChange={e=>setAction(e.target.value)}><option value="">All actions</option>{actions.map(x=><option key={x} value={x}>{displayAction(x)}</option>)}</select><select className="field h-8 w-[170px]" value={actor} onChange={e=>setActor(e.target.value)}><option value="">All actors</option>{members.map(m=><option key={m.id} value={m.id}>{m.username}</option>)}</select></div>
  <div className="panel overflow-hidden"><div className="border-b border-line px-4 py-3 text-[11px] text-ink-faint">{visible.length} events</div><table className="w-full text-left text-[12px]"><thead className="border-b border-line text-ink-faint"><tr><th className="px-4 py-2">Time</th><th>Actor</th><th>Action</th><th>Entity</th><th>Details</th></tr></thead><tbody className="divide-y divide-line">{visible.map((r,i)=><tr key={String(r.id??i)} className="hover:bg-raised/40"><td className="px-4 py-3 font-mono text-[10px] whitespace-nowrap">{String(r.created_at??'')}</td><td className="whitespace-nowrap">{String(r.username??'system')}</td><td><span className="status-chip">{displayAction(String(r.action??''))}</span></td><td className="font-mono text-[10px]">{String(r.entity_type??'')} {r.entity_id?`· ${String(r.entity_id)}`:''}</td><td className="max-w-[520px] truncate text-ink-dim" title={String(r.metadata??'')}>{String(r.metadata??'{}')}</td></tr>)}</tbody></table>{!visible.length&&!error&&<div className="p-10 text-center text-sm text-ink-faint"><Activity size={18} className="mx-auto mb-2"/>No matching activity.</div>}{error&&<div className="p-4 text-[12px] text-danger">{error}</div>}</div>
 </div></>
}
