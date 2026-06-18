import { useEffect, useState } from 'react'
import { Download, Pause, Play, X, Trash2, CheckCircle2, RefreshCw, HardDrive } from 'lucide-react'
import { api, fmtBytes, fmtETA } from '../api'
import { useStore } from '../store'

const CATEGORY_LABELS = {
  checkpoints:   { label: 'Checkpoints',  emoji: '🧠', desc: 'Base models — the foundation of image generation' },
  vae:           { label: 'VAE',          emoji: '🎨', desc: 'Color & detail encoders — fix washed colors' },
  loras:         { label: 'LoRAs',        emoji: '🔧', desc: 'Fine-tune adapters — style, detail, character' },
  controlnet:    { label: 'ControlNet',   emoji: '🎯', desc: 'Structural control — pose, edges, depth' },
  ipadapter:     { label: 'IP-Adapter',   emoji: '👤', desc: 'Face & style consistency from reference images' },
  upscale_models:{ label: 'Upscalers',   emoji: '🔍', desc: 'Increase output resolution up to 4x' },
  embeddings:    { label: 'Embeddings',  emoji: '💬', desc: 'Textual inversions — prompt helpers' },
  video:         { label: 'Video',        emoji: '🎬', desc: 'Text-to-video and image-to-video models' },
}
const ALL_CATS = Object.keys(CATEGORY_LABELS)

const INSTALLED_CATS = {
  checkpoints:   { label: 'Checkpoints',  emoji: '🧠' },
  loras:         { label: 'LoRAs',        emoji: '🔧' },
  vae:           { label: 'VAE',          emoji: '🎨' },
  text_encoders: { label: 'Text Encoders',emoji: '📝' },
  clip_vision:   { label: 'CLIP Vision',  emoji: '👁' },
  controlnet:    { label: 'ControlNet',   emoji: '🎯' },
  ipadapter:     { label: 'IP-Adapter',   emoji: '👤' },
  video:         { label: 'Video',        emoji: '🎬' },
  embeddings:    { label: 'Embeddings',   emoji: '💬' },
  upscalers:     { label: 'Upscalers',    emoji: '🔍' },
}

const ARCH_COLORS = {
  'SD 1.5':        { bg: 'rgba(99,179,237,.15)',  color: '#63b3ed' },
  'SDXL':          { bg: 'rgba(154,117,234,.15)', color: '#9a75ea' },
  'Pony XL':       { bg: 'rgba(236,72,153,.15)',  color: '#ec4899' },
  'Illustrious XL':{ bg: 'rgba(251,146,60,.15)',  color: '#fb923c' },
  'Wan 2.1':       { bg: 'rgba(52,211,153,.15)',  color: '#34d399' },
  'Wan 2.2':       { bg: 'rgba(16,185,129,.15)',  color: '#10b981' },
  'LTX Video':     { bg: 'rgba(251,191,36,.15)',  color: '#fbbf24' },
}

function ArchBadge({ arch, quant, variant }) {
  const style = arch ? (ARCH_COLORS[arch] ?? { bg: 'rgba(148,163,184,.15)', color: '#94a3b8' }) : null
  return (
    <div style={{ display:'flex', gap:4, flexWrap:'wrap', marginTop:4 }}>
      {arch && (
        <span style={{ fontSize:10.5, padding:'1px 7px', borderRadius:999, background:style.bg, color:style.color, fontWeight:600 }}>
          {arch}
        </span>
      )}
      {quant && (
        <span style={{ fontSize:10.5, padding:'1px 7px', borderRadius:999, background:'rgba(148,163,184,.12)', color:'#94a3b8', fontWeight:500 }}>
          {quant}
        </span>
      )}
      {variant && (
        <span style={{ fontSize:10.5, padding:'1px 7px', borderRadius:999, background:'rgba(255,179,71,.1)', color:'var(--amber)', fontWeight:500 }}>
          {variant}
        </span>
      )}
    </div>
  )
}

function InstalledTab() {
  const { toast } = useStore()
  const [data, setData]       = useState(null)
  const [loading, setLoading] = useState(true)

  const refresh = async () => {
    setLoading(true)
    try { setData(await api.models()) }
    catch (e) { toast(e.message, 'err') }
    finally { setLoading(false) }
  }

  useEffect(() => { refresh() }, [])

  if (loading) return <div className="empty"><span className="spinner lg"/></div>
  if (!data) return <div className="empty muted">No scan data.</div>

  const summary = data._summary ?? {}
  const totalModels = Object.values(summary).reduce((a, b) => a + b, 0)

  // Flatten loras (grouped by subfolder) into a flat list with group label
  const flatLoras = []
  if (data.loras && typeof data.loras === 'object') {
    for (const [grp, items] of Object.entries(data.loras)) {
      for (const m of items) flatLoras.push({ ...m, _group: grp })
    }
  }

  return (
    <div>
      <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', marginBottom:18, flexWrap:'wrap', gap:10 }}>
        <div style={{ display:'flex', gap:10, flexWrap:'wrap' }}>
          <div className="chip green"><HardDrive size={11}/> {totalModels} installed</div>
          {Object.entries(summary).filter(([, v]) => v > 0).map(([k, v]) => (
            <div key={k} className="chip">{INSTALLED_CATS[k]?.emoji ?? '📦'} {INSTALLED_CATS[k]?.label ?? k}: {v}</div>
          ))}
        </div>
        <button className="btn btn-sm btn-ghost" onClick={refresh}><RefreshCw size={13}/> Rescan</button>
      </div>

      {Object.entries(INSTALLED_CATS).map(([cat, info]) => {
        const items = cat === 'loras' ? flatLoras : (data[cat] ?? [])
        if (!items.length) return null
        return (
          <div key={cat} style={{ marginBottom:28 }}>
            <div style={{ display:'flex', alignItems:'center', gap:10, marginBottom:12, paddingBottom:10, borderBottom:'1px solid var(--line)' }}>
              <span style={{ fontSize:22 }}>{info.emoji}</span>
              <div>
                <div style={{ fontFamily:'var(--font-display)', fontWeight:700, fontSize:15 }}>
                  {info.label}
                  <span style={{ marginLeft:10, fontSize:11.5, color:'var(--green)', padding:'2px 8px', borderRadius:999, background:'rgba(74,222,128,.1)' }}>
                    {items.length} {items.length === 1 ? 'model' : 'models'}
                  </span>
                </div>
                <div className="muted" style={{ fontSize:12 }}>{items[0]?.task ?? ''}</div>
              </div>
            </div>
            <div className="dl-grid">
              {items.map((m, i) => (
                <div key={i} className="panel dl-card" style={{ borderColor:'rgba(74,222,128,.2)', background:'linear-gradient(160deg,rgba(74,222,128,.04) 0%,var(--ink-850) 100%)' }}>
                  <div style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-start', gap:8 }}>
                    <div style={{ flex:1, minWidth:0 }}>
                      <div className="dl-name" style={{ wordBreak:'break-word' }}>{m.name}</div>
                      {m._group && m._group !== 'root' && (
                        <div className="muted" style={{ fontSize:11 }}>group: {m._group}</div>
                      )}
                    </div>
                    <span className="badge done" style={{ flexShrink:0 }}>
                      <CheckCircle2 size={10} style={{ verticalAlign:-1 }}/> Ready
                    </span>
                  </div>
                  <ArchBadge arch={m.arch} quant={m.quant} variant={m.variant} />
                  <div className="dl-meta" style={{ marginTop:6 }}>
                    <span className="muted" style={{ fontSize:12 }}>
                      {m.size_gb >= 1 ? `${m.size_gb} GB` : `${m.size_mb} MB`}
                    </span>
                    <span className="muted" style={{ fontSize:11.5 }}>{m.task}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )
      })}
    </div>
  )
}

export default function DownloadsPage() {
  const { toast } = useStore()
  const [tab, setTab]         = useState('installed')
  const [models, setModels]   = useState([])
  const [loading, setLoading] = useState(true)
  const [cat, setCat]         = useState('all')

  const refresh = async (showLoad = false) => {
    if (showLoad) setLoading(true)
    try { setModels((await api.downloads()).models ?? []) }
    catch (e) { toast(e.message, 'err') }
    finally { setLoading(false) }
  }

  useEffect(() => {
    refresh(true)
    const id = setInterval(() => refresh(false), 1500)
    return () => clearInterval(id)
  }, [])

  const act = (fn, id) => async () => {
    try { await fn(id); refresh() } catch (e) { toast(e.message, 'err') }
  }

  const delModel = async (m) => {
    try { await api.delModel({ model_id: m.id }); toast(`Removed ${m.name}`, 'info'); refresh() }
    catch (e) { toast(e.message, 'err') }
  }

  // compute stats
  const installed = models.filter((m) => m.downloaded).length
  const active    = models.filter((m) => m.status?.status === 'downloading').length

  // filter by category
  const visible = cat === 'all' ? models : models.filter((m) => m.category === cat)

  // group by category for display
  const grouped = {}
  for (const m of visible) {
    if (!grouped[m.category]) grouped[m.category] = []
    grouped[m.category].push(m)
  }

  return (
    <div className="page">
      <div className="page-narrow">

        {/* main tab: Installed vs Download Catalog */}
        <div className="tab-bar" style={{ marginBottom:22 }}>
          <button className={'tab' + (tab === 'installed' ? ' active' : '')} onClick={() => setTab('installed')}>
            <HardDrive size={13}/> Installed
          </button>
          <button className={'tab' + (tab === 'catalog' ? ' active' : '')} onClick={() => setTab('catalog')}>
            <Download size={13}/> Download Catalog
          </button>
        </div>

        {tab === 'installed' && <InstalledTab />}

        {tab === 'catalog' && <>
        {/* header */}
        <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', marginBottom:18, flexWrap:'wrap', gap:10 }}>
          <div style={{ display:'flex', gap:12 }}>
            <div className="chip green">✓ {installed} installed</div>
            {active > 0 && <div className="chip amber">↓ {active} downloading</div>}
            <div className="chip">{models.length} total</div>
          </div>
          <div style={{ display:'flex', gap:8, alignItems:'center' }}>
            <span className="muted" style={{ fontSize:12 }}>
              Saves to <span className="kbd">backend\models</span>
            </span>
            <button className="btn btn-sm btn-ghost" onClick={() => refresh(true)}>
              <RefreshCw size={13}/> Scan
            </button>
          </div>
        </div>

        {/* category tabs */}
        <div className="tab-bar" style={{ marginBottom:20 }}>
          <button className={'tab' + (cat === 'all' ? ' active' : '')} onClick={() => setCat('all')}>
            All
          </button>
          {ALL_CATS.map((c) => {
            const info  = CATEGORY_LABELS[c]
            const count = models.filter((m) => m.category === c && m.downloaded).length
            const total = models.filter((m) => m.category === c).length
            if (!total) return null
            return (
              <button key={c} className={'tab' + (cat === c ? ' active' : '')} onClick={() => setCat(c)}>
                {info.emoji} {info.label}
                {count > 0 && (
                  <span style={{
                    marginLeft:6, fontSize:10.5, padding:'1px 6px', borderRadius:999,
                    background:'rgba(74,222,128,.15)', color:'var(--green)',
                  }}>
                    {count}/{total}
                  </span>
                )}
              </button>
            )
          })}
        </div>

        {loading ? (
          <div className="empty"><span className="spinner lg"/></div>
        ) : (
          Object.entries(grouped).map(([category, items]) => {
            const info = CATEGORY_LABELS[category] ?? { label: category, emoji: '📦', desc:'' }
            const catInstalled = items.filter((m) => m.downloaded).length
            return (
              <div key={category} style={{ marginBottom:28 }}>
                {/* category header */}
                <div style={{
                  display:'flex', alignItems:'center', gap:10, marginBottom:12,
                  paddingBottom:10, borderBottom:'1px solid var(--line)',
                }}>
                  <span style={{ fontSize:22 }}>{info.emoji}</span>
                  <div>
                    <div style={{ fontFamily:'var(--font-display)', fontWeight:700, fontSize:15 }}>
                      {info.label}
                      <span style={{
                        marginLeft:10, fontSize:11.5, color:'var(--green)',
                        padding:'2px 8px', borderRadius:999,
                        background:'rgba(74,222,128,.1)',
                      }}>
                        {catInstalled}/{items.length} installed
                      </span>
                    </div>
                    <div className="muted" style={{ fontSize:12 }}>{info.desc}</div>
                  </div>
                </div>

                {/* model cards */}
                <div className="dl-grid">
                  {items.map((m) => {
                    const st          = m.status ?? {}
                    const downloading = st.status === 'downloading'
                    const paused      = st.status === 'paused'
                    const prog        = st.progress ?? 0

                    return (
                      <div key={m.id} className="panel dl-card" style={{
                        borderColor: m.downloaded ? 'rgba(74,222,128,.2)' : undefined,
                        background: m.downloaded
                          ? 'linear-gradient(160deg,rgba(74,222,128,.05) 0%,var(--ink-850) 100%)'
                          : undefined,
                      }}>
                        {/* card top */}
                        <div style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-start', gap:8 }}>
                          <div style={{ flex:1, minWidth:0 }}>
                            <div className="dl-name">{m.name}</div>
                          </div>
                          {m.downloaded && (
                            <span className="badge done" style={{ flexShrink:0 }}>
                              <CheckCircle2 size={10} style={{ verticalAlign:-1 }}/> Ready
                            </span>
                          )}
                          {(downloading || paused) && (
                            <span className="badge active" style={{ flexShrink:0 }}>{prog}%</span>
                          )}
                        </div>

                        <div className="dl-desc">{m.description}</div>

                        {/* progress */}
                        {(downloading || paused) && (
                          <>
                            <div className="progress-bar">
                              <div className="progress-fill" style={{ width:`${prog}%` }}/>
                            </div>
                            <div className="dl-meta">
                              <span>{fmtBytes(st.downloaded_bytes)} / {fmtBytes(st.total_bytes)}</span>
                              <span>
                                {paused
                                  ? '⏸ paused'
                                  : `${fmtBytes(st.speed_bps)}/s · ${fmtETA(st.eta_sec)}`}
                              </span>
                            </div>
                          </>
                        )}

                        {/* meta row */}
                        <div className="dl-meta">
                          <span className="muted" style={{ fontSize:12 }}>{m.size}</span>
                          {m.requires_hf_token && (
                            <span className="muted" style={{ fontSize:11.5 }}>🔑 HF token needed</span>
                          )}
                          {m.requires_civitai_token && (
                            <span className="muted" style={{ fontSize:11.5 }}>🔑 CivitAI token needed</span>
                          )}
                        </div>

                        {/* actions */}
                        <div className="row">
                          {m.downloaded ? (
                            <button className="btn btn-sm btn-danger btn-full"
                              onClick={() => delModel(m)}>
                              <Trash2 size={12}/> Remove
                            </button>
                          ) : downloading ? (
                            <>
                              <button className="btn btn-sm btn-full" onClick={act(api.dlPause, m.id)}>
                                <Pause size={12}/> Pause
                              </button>
                              <button className="btn btn-sm btn-danger" onClick={act(api.dlCancel, m.id)}>
                                <X size={12}/>
                              </button>
                            </>
                          ) : paused ? (
                            <>
                              <button className="btn btn-sm btn-primary btn-full" onClick={act(api.dlResume, m.id)}>
                                <Play size={12}/> Resume
                              </button>
                              <button className="btn btn-sm btn-danger" onClick={act(api.dlCancel, m.id)}>
                                <X size={12}/>
                              </button>
                            </>
                          ) : (
                            <button className="btn btn-sm btn-primary btn-full" onClick={act(api.dlStart, m.id)}>
                              <Download size={12}/> Download
                            </button>
                          )}
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>
            )
          })
        )}
        </>}

      </div>
    </div>
  )
}
