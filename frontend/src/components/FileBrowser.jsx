import { useEffect, useState, useCallback } from 'react'
import { FolderOpen, ChevronRight, ChevronUp, HardDrive, File, Folder, RefreshCw, X } from 'lucide-react'
import { api } from '../api'

export default function FileBrowser({ title, exts, onSelect, onClose }) {
  const [path, setPath]     = useState('')
  const [items, setItems]   = useState([])
  const [parent, setParent] = useState(null)
  const [loading, setLoading] = useState(true)
  const [err, setErr]       = useState('')

  const go = useCallback(async (p) => {
    setLoading(true); setErr('')
    try {
      const r = await api.browse(p, exts)
      setItems(r.items); setPath(r.current); setParent(r.parent)
    } catch (e) { setErr(e.message) }
    finally { setLoading(false) }
  }, [exts])

  useEffect(() => { go('') }, [go])

  return (
    <div style={{
      position:'fixed', inset:0, zIndex:200,
      background:'rgba(7,9,16,.88)', backdropFilter:'blur(8px)',
      display:'flex', alignItems:'center', justifyContent:'center',
    }}>
      <div style={{
        width:680, maxHeight:'80vh', display:'flex', flexDirection:'column',
        background:'var(--ink-800)', border:'1px solid var(--line-lg)',
        borderRadius:'var(--r-xl)', overflow:'hidden',
        boxShadow:'0 24px 60px -16px rgba(0,0,0,.9)',
      }}>
        {/* header */}
        <div style={{
          display:'flex', alignItems:'center', gap:10, padding:'14px 18px',
          borderBottom:'1px solid var(--line)', flexShrink:0,
        }}>
          <FolderOpen size={18} style={{ color:'var(--amber)' }}/>
          <div style={{ flex:1 }}>
            <div style={{ fontWeight:700, fontSize:14 }}>{title}</div>
            <div style={{ fontSize:11, color:'var(--text-faint)', fontFamily:'var(--font-mono)', marginTop:2, wordBreak:'break-all' }}>
              {path || 'Select a drive to start'}
            </div>
          </div>
          <button className="btn btn-ghost btn-icon btn-sm" onClick={onClose}><X size={16}/></button>
        </div>

        {/* nav */}
        <div style={{ display:'flex', gap:6, padding:'8px 14px', borderBottom:'1px solid var(--line)', flexShrink:0 }}>
          <button className="btn btn-sm btn-ghost" onClick={() => go('')}><HardDrive size={13}/> Drives</button>
          {parent !== null && (
            <button className="btn btn-sm btn-ghost" onClick={() => go(parent)}><ChevronUp size={13}/> Up</button>
          )}
          <button className="btn btn-sm btn-ghost" onClick={() => go(path)}><RefreshCw size={12}/></button>
          <span className="muted" style={{ fontSize:11, alignSelf:'center', marginLeft:4 }}>{exts}</span>
        </div>

        {/* list */}
        <div style={{ flex:1, overflowY:'auto', padding:'6px 8px' }}>
          {err && <div style={{ color:'var(--rose)', padding:12, fontSize:13 }}>{err}</div>}
          {loading
            ? <div style={{ display:'flex', justifyContent:'center', padding:30 }}><span className="spinner lg"/></div>
            : items.length === 0
              ? <div className="muted" style={{ padding:20, textAlign:'center' }}>No matching files here.</div>
              : items.map((item) => (
                  <div key={item.path} onClick={() => item.type === 'file' ? onSelect(item) : go(item.path)}
                    style={{
                      display:'flex', alignItems:'center', gap:10, padding:'9px 12px',
                      borderRadius:'var(--r-md)', cursor:'pointer', fontSize:13.5,
                      color: item.type === 'file' ? 'var(--text)' : 'var(--text-dim)',
                      transition:'background .12s',
                    }}
                    onMouseOver={(e) => e.currentTarget.style.background = 'var(--ink-700)'}
                    onMouseOut={(e)  => e.currentTarget.style.background = 'transparent'}>
                    {item.type === 'drive'
                      ? <HardDrive size={16} style={{ color:'var(--amber)', flexShrink:0 }}/>
                      : item.type === 'dir'
                        ? <Folder size={16} style={{ color:'var(--cyan)', flexShrink:0 }}/>
                        : <File size={16} style={{ color:'var(--violet)', flexShrink:0 }}/>}
                    <span style={{ flex:1, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>
                      {item.name}
                    </span>
                    {item.size_mb != null && (
                      <span style={{ fontSize:11, color:'var(--text-faint)', flexShrink:0 }}>{item.size_mb}MB</span>
                    )}
                    {item.type !== 'file' && (
                      <ChevronRight size={14} style={{ color:'var(--text-faint)', flexShrink:0 }}/>
                    )}
                  </div>
                ))}
        </div>
      </div>
    </div>
  )
}
