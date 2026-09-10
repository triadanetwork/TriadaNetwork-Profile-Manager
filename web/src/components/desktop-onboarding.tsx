'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { ArrowRight, Check, X } from 'lucide-react'

const KEY='triada.desktop.onboarding.v1'
export function DesktopOnboarding() {
  const [open,setOpen]=useState(false)
  useEffect(()=>{ setOpen(localStorage.getItem(KEY)!=='done') },[])
  const finish=()=>{ localStorage.setItem(KEY,'done'); setOpen(false) }
  if(!open) return null
  return <div className="fixed inset-x-0 bottom-5 z-40 mx-auto w-[min(720px,calc(100vw-32px))]"><div className="panel border border-line bg-surface/95 p-5 shadow-2xl shadow-black/40 backdrop-blur"><div className="flex items-start justify-between gap-4"><div><div className="eyebrow">WELCOME TO TRIADA NETWORK</div><h2 className="mt-1">Desktop workspace ready</h2><p className="mt-1 text-sm text-ink-dim">A few quick actions will get your local browser infrastructure ready.</p></div><button className="text-ink-faint hover:text-ink" onClick={finish} aria-label="Dismiss"><X size={16}/></button></div><div className="mt-5 grid gap-2 sm:grid-cols-3"><Step done label="Local runtime"/><Link href="/" onClick={finish} className="rounded-md border border-line bg-canvas p-3 hover:bg-raised"><div className="flex items-center justify-between"><span className="text-sm font-medium">Create profile</span><ArrowRight size={14}/></div><div className="mt-1 text-xs text-ink-faint">Set up your first browser profile.</div></Link><Link href="/proxy-pools/" onClick={finish} className="rounded-md border border-line bg-canvas p-3 hover:bg-raised"><div className="flex items-center justify-between"><span className="text-sm font-medium">Add proxy</span><ArrowRight size={14}/></div><div className="mt-1 text-xs text-ink-faint">Connect or import your proxy pool.</div></Link></div><div className="mt-4 flex justify-end"><button className="btn btn-primary" onClick={finish}><Check size={13}/> Got it</button></div></div></div>
}
function Step({done,label}:{done:boolean;label:string}){return <div className="rounded-md border border-line bg-canvas p-3"><div className="flex items-center gap-2"><span className="flex h-5 w-5 items-center justify-center rounded-full border border-ok/30 bg-ok/10 text-ok"><Check size={12}/></span><span className="text-sm font-medium">{label}</span></div><div className="mt-2 text-xs text-ink-faint">Healthy</div></div>}
