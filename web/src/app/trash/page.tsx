'use client'
import { useEffect, useState } from 'react'
import { RefreshCw, RotateCcw, Trash2 } from 'lucide-react'
import { trashAPI, type TrashProfile } from '@/lib/api'

export default function TrashPage(){
 const [items,setItems]=useState<TrashProfile[]>([])
 async function load(){setItems(await trashAPI.list())}
 useEffect(()=>{load().catch(()=>undefined)},[])
 return <div><header className="sticky top-0 z-20 flex min-h-[58px] items-center justify-between border-b border-line bg-canvas/90 px-5"><div><div className="text-sm font-semibold">Trash</div><div className="text-[11px] text-ink-faint">Deleted profiles retained locally for recovery.</div></div><button className="btn btn-default" onClick={()=>load()}><RefreshCw size={14}/>Refresh</button></header><div className="space-y-4 p-5"><div className="panel overflow-hidden"><div className="overflow-x-auto"><table className="w-full text-left text-[12px]"><thead className="border-b border-line text-ink-faint"><tr><th className="px-4 py-2">Profile</th><th>Deleted</th><th>Tags</th><th className="w-[180px]">Actions</th></tr></thead><tbody className="divide-y divide-line">{items.map(i=><tr key={i.profile_id}><td className="px-4 py-3"><div className="font-medium">{i.name}</div><div className="font-mono text-[10px] text-ink-faint">{i.profile_id}</div></td><td>{new Date(i.deleted_at).toLocaleString()}</td><td>{i.tags.map(t=><span key={t.id} className="mr-1 rounded border border-line px-1.5 py-0.5 text-[10px]">{t.name}</span>)}</td><td><div className="flex gap-1"><button className="icon-btn" title="Restore" onClick={async()=>{await trashAPI.restore(i.profile_id); await load()}}><RotateCcw size={13}/></button><button className="icon-btn text-danger" title="Permanently delete" onClick={async()=>{if(confirm('Permanently delete this profile?')){await trashAPI.purge(i.profile_id);await load()}}}><Trash2 size={13}/></button></div></td></tr>)}{!items.length&&<tr><td colSpan={4} className="px-4 py-12 text-center text-ink-faint">Trash is empty.</td></tr>}</tbody></table></div></div></div></div>
}
