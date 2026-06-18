import { useEffect, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { RefreshCw, Save, KeyRound, FolderOpen,
         Bot, Eye, Download as DlIcon, Plus, X, Trash2, Copy, ZoomIn,
         Search, ScanLine, Cpu, Zap, CheckCircle2, AlertCircle, Layers, Brain,
         Star, CheckSquare, Square, Sparkles, ImagePlus } from 'lucide-react'
import { api } from '../api'
import { useStore } from '../store'

const urlToB64 = async (url) => {
  const res  = await fetch(url)
  const blob = await res.blob()
  return new Promise((resolve, reject) => {
    const r = new FileReader()
    r.onload  = () => resolve(r.result)
    r.onerror = reject
    r.readAsDataURL(blob)
  })
}

function relTime(ts) {
  const d = (Date.now() / 1000) - ts
  if (d < 60)   return 'just now'
  if (d < 3600) return `${Math.floor(d/60)}m ago`
  if (d < 86400) return `${Math.floor(d/3600)}h ago`
  return `${Math.floor(d/86400)}d ago`
}

/* ═══════════════════════════════════════════════════════════
   GALLERY
═══════════════════════════════════════════════════════════ */
export function GalleryPage() {
  const { toast, setPendingRef } = useStore()
  const navigate = useNavigate()
  const [files, setFiles]       = useState([])
  const [loading, setLoading]   = useState(true)
  const [lightbox, setLightbox] = useState(null)
  const [filter, setFilter]     = useState('all')
  const [search, setSearch]     = useState('')
  const [favorites, setFavorites] = useState(() => {
    try { return new Set(JSON.parse(localStorage.getItem('acs_favs') || '[]')) } catch { return new Set() }
  })
  const [selected, setSelected] = useState(new Set())
  const [selectMode, setSelectMode] = useState(false)
  const [upscaling, setUpscaling] = useState(null)

  const refresh = async () => {
    setLoading(true)
    try { setFiles((await api.outputs()).files ?? []) } catch {}
    setLoading(false)
  }
  useEffect(() => { refresh() }, [])

  const remove = async (f) => {
    try {
      await api.delOutput(f.name)
      setFiles((prev) => prev.filter((x) => x.name !== f.name))
      if (lightbox?.name === f.name) setLightbox(null)
      toast('Deleted', 'ok')
    } catch (e) { toast(e.message, 'err') }
  }

  const copyPrompt = (f) => {
    const p = f.meta?.prompt
    if (!p) return toast('No prompt metadata', 'info')
    navigator.clipboard.writeText(p).then(() => toast('Prompt copied', 'ok'))
  }

  const toggleFav = (name) => {
    setFavorites((prev) => {
      const next = new Set(prev)
      next.has(name) ? next.delete(name) : next.add(name)
      localStorage.setItem('acs_favs', JSON.stringify([...next]))
      return next
    })
  }

  const toggleSelect = (name) => {
    setSelected((prev) => {
      const next = new Set(prev)
      next.has(name) ? next.delete(name) : next.add(name)
      return next
    })
  }

  const bulkDelete = async () => {
    if (!selected.size) return
    for (const name of selected) {
      try { await api.delOutput(name); setFiles((p) => p.filter((f) => f.name !== name)) }
      catch {}
    }
    setSelected(new Set())
    toast(`Deleted ${selected.size} items`, 'ok')
  }

  const upscaleFromGallery = async (f) => {
    setUpscaling(f.name)
    try {
      const b64 = await urlToB64(f.url)
      const r = await api.generate({
        prompt: f.meta?.prompt || 'high quality image', negative: '', mode: 'upscale',
        ref_image: b64, upscale_factor: 4,
      })
      if (r.error) { toast(r.error, 'err'); return }
      toast('Upscale done — check Gallery', 'ok')
      await refresh()
    } catch (e) { toast(e.message, 'err') }
    finally { setUpscaling(null) }
  }

  const sendToGenerate = async (f) => {
    try {
      const b64 = await urlToB64(f.url)
      setPendingRef(b64, f.type === 'video' ? 't2v' : 'i2i')
      navigate('/generate')
    } catch (e) { toast(e.message, 'err') }
  }

  const images = files.filter((f) => f.type === 'image')
  const videos = files.filter((f) => f.type === 'video')
  const favFiles = files.filter((f) => favorites.has(f.name))
  const byType = filter === 'image' ? images : filter === 'video' ? videos : filter === 'fav' ? favFiles : files
  const q = search.trim().toLowerCase()
  const visible = q ? byType.filter((f) => (f.meta?.prompt ?? f.name).toLowerCase().includes(q)) : byType

  return (
    <div className="page">
      {/* Lightbox */}
      {lightbox && (
        <div className="lightbox-overlay" onClick={() => setLightbox(null)}>
          <div className="lightbox-box" onClick={(e) => e.stopPropagation()}>
            {lightbox.type === 'video'
              ? <video src={lightbox.url} controls autoPlay loop className="lightbox-media"/>
              : <img src={lightbox.url} alt={lightbox.name} className="lightbox-media"/>}
            <div className="lightbox-bar">
              <div style={{ flex:1 }}>
                {lightbox.meta?.prompt && (
                  <div style={{ fontSize:12.5, marginBottom:8, lineHeight:1.5, color:'var(--text)' }}>
                    {lightbox.meta.prompt.slice(0, 200)}{lightbox.meta.prompt.length > 200 ? '…' : ''}
                  </div>
                )}
                <div className="row" style={{ gap:6, flexWrap:'wrap' }}>
                  {lightbox.meta?.mode   && <span className="chip">{lightbox.meta.mode}</span>}
                  {lightbox.meta?.seed != null && <span className="chip">seed {lightbox.meta.seed}</span>}
                  {lightbox.meta?.steps  && <span className="chip">{lightbox.meta.steps} steps</span>}
                  {lightbox.meta?.cfg    && <span className="chip">CFG {lightbox.meta.cfg}</span>}
                  {lightbox.meta?.width  && <span className="chip">{lightbox.meta.width}×{lightbox.meta.height}</span>}
                  {lightbox.meta?.model  && <span className="chip" title={lightbox.meta.model}>
                    {lightbox.meta.model.split(/[\\/]/).pop()}</span>}
                </div>
              </div>
              <div className="row" style={{ gap:8, flexShrink:0 }}>
                {lightbox.type === 'image' && (
                  <button className="btn btn-sm" onClick={() => sendToGenerate(lightbox)}>
                    <ImagePlus size={13}/> Use as Ref
                  </button>
                )}
                <button className="btn btn-sm" onClick={() => copyPrompt(lightbox)}><Copy size={13}/> Copy prompt</button>
                <a className="btn btn-sm" href={lightbox.url} download={lightbox.name}><DlIcon size={13}/> Save</a>
                <button className="btn btn-sm" style={{ color:'var(--red)' }} onClick={() => remove(lightbox)}><Trash2 size={13}/> Delete</button>
                <button className="btn btn-sm" onClick={() => setLightbox(null)}><X size={13}/></button>
              </div>
            </div>
          </div>
        </div>
      )}

      <div className="page-narrow">
        {/* Header */}
        <div className="gallery-header">
          <div className="gallery-filters">
            {[
              ['all',   `All (${files.length})`],
              ['image', `Images (${images.length})`],
              ['video', `Videos (${videos.length})`],
              ['fav',   `★ (${favFiles.length})`],
            ].map(([id, label]) => (
              <button key={id} className={'gallery-filter-btn' + (filter === id ? ' active' : '')}
                onClick={() => setFilter(id)}>{label}</button>
            ))}
          </div>
          <div className="gallery-search-wrap">
            <Search size={13} className="gallery-search-icon"/>
            <input className="input gallery-search-input" placeholder="Search prompts…"
              value={search} onChange={(e) => setSearch(e.target.value)}/>
            {search && <button className="btn-ghost btn-icon" style={{padding:2}} onClick={() => setSearch('')}><X size={12}/></button>}
          </div>
          <button className={'btn btn-sm' + (selectMode ? ' btn-primary' : '')}
            onClick={() => { setSelectMode((v) => !v); setSelected(new Set()) }}>
            <CheckSquare size={13}/> {selectMode ? 'Cancel' : 'Select'}
          </button>
          <button className="btn btn-sm" onClick={refresh}><RefreshCw size={13}/> Refresh</button>
        </div>

        {/* Bulk action bar */}
        {selectMode && selected.size > 0 && (
          <div className="gallery-bulk-bar">
            <span>{selected.size} selected</span>
            <button className="btn btn-sm" onClick={() => setSelected(new Set(visible.map(f=>f.name)))}>All</button>
            <button className="btn btn-sm" onClick={() => setSelected(new Set())}>None</button>
            <button className="btn btn-sm" style={{ color:'var(--rose)', marginLeft:'auto' }} onClick={bulkDelete}>
              <Trash2 size={13}/> Delete selected
            </button>
          </div>
        )}

        {loading
          ? <div className="empty"><span className="spinner lg"/></div>
          : visible.length === 0
            ? <div className="empty">
                <div className="glyph">🖼</div>
                <h3>{files.length === 0 ? 'Nothing yet' : 'No ' + filter + 's'}</h3>
                <p>{files.length === 0 ? 'Generate an image or video to see it here.' : 'Try a different filter.'}</p>
              </div>
            : <div className="gallery-grid">
                {visible.map((f) => (
                  <div key={f.name} className={'gallery-item' + (selected.has(f.name) ? ' selected' : '')}>
                    <div className="gallery-thumb"
                      onClick={() => selectMode ? toggleSelect(f.name) : setLightbox(f)}>
                      {f.type === 'video'
                        ? <video src={f.url} muted loop
                            onMouseOver={(e) => e.target.play()}
                            onMouseOut={(e) => e.target.pause()} />
                        : <img src={f.url} alt={f.name} loading="lazy"/>}
                      {selectMode
                        ? <div className="gallery-select-check">
                            {selected.has(f.name) ? <CheckSquare size={18} style={{color:'var(--cyan)'}}/> : <Square size={18}/>}
                          </div>
                        : <div className="gallery-zoom"><ZoomIn size={18}/></div>}
                      {f.meta?.mode && <span className="gallery-mode-badge">{f.meta.mode}</span>}
                      <button className={'gallery-fav-btn' + (favorites.has(f.name) ? ' active' : '')}
                        onClick={(e) => { e.stopPropagation(); toggleFav(f.name) }}>
                        <Star size={13} fill={favorites.has(f.name) ? 'currentColor' : 'none'}/>
                      </button>
                    </div>

                    <div className="gallery-info">
                      {f.meta?.prompt
                        ? <div className="gallery-prompt-text" title={f.meta.prompt}>
                            {f.meta.prompt.slice(0, 72)}{f.meta.prompt.length > 72 ? '…' : ''}
                          </div>
                        : <div className="gallery-prompt-text muted">{f.name}</div>}
                      <div className="gallery-meta-row">
                        <span>{relTime(f.time)}</span>
                        <span>{f.size_mb} MB</span>
                        {f.meta?.width && <span>{f.meta.width}×{f.meta.height}</span>}
                      </div>
                    </div>

                    <div className="gallery-actions">
                      <button className="btn-ghost btn-icon" title="Copy prompt" onClick={() => copyPrompt(f)}><Copy size={13}/></button>
                      {f.type === 'image' && (
                        <button className="btn-ghost btn-icon" title="4× Upscale"
                          disabled={upscaling === f.name}
                          onClick={() => upscaleFromGallery(f)}>
                          {upscaling === f.name ? <span className="spinner"/> : <Sparkles size={13}/>}
                        </button>
                      )}
                      <a className="btn-ghost btn-icon" href={f.url} download={f.name} title="Download"><DlIcon size={13}/></a>
                      <button className="btn-ghost btn-icon" title="Delete"
                        style={{ color:'var(--rose)' }} onClick={() => remove(f)}><Trash2 size={13}/></button>
                    </div>
                  </div>
                ))}
              </div>}
      </div>
    </div>
  )
}

/* ═══════════════════════════════════════════════════════════
   SETTINGS
═══════════════════════════════════════════════════════════ */
// Classify Ollama models so each dropdown shows only relevant ones.
const _VISION_HINTS = ['moondream', 'llava', 'bakllava', 'minicpm-v', 'vision', 'qwen2-vl', 'qwen2.5-vl', '-vl', 'llama3.2-vision']
const isEmbedModel  = (m) => /embed|bge|nomic|e5|gte/i.test(m)
const isVisionModel = (m) => _VISION_HINTS.some((h) => m.toLowerCase().includes(h))
const isChatModel   = (m) => !isEmbedModel(m) && !isVisionModel(m)

export function SettingsPage() {
  const { status, config, loadConfig, toast } = useStore()
  const [hf, setHf]                   = useState('')
  const [civitai, setCivitai]         = useState('')
  const [textModel, setTextModel]     = useState('')
  const [visionModel, setVisionModel] = useState('')
  const [comfyuiDir, setComfyuiDir]   = useState('')
  const [comfyuiUrl, setComfyuiUrl]   = useState('http://localhost:8188')
  const [extraDirs, setExtraDirs]     = useState([])
  const [ollamaList, setOllamaList]   = useState([])
  const [pullName, setPullName]       = useState('')
  const [aiName, setAiName]           = useState('')
  const [aiGender, setAiGender]       = useState('female')
  const [aiPersonality, setAiPersonality] = useState('')
  const [savingPersona, setSavingPersona] = useState(false)
  const [useLocalEngine, setUseLocalEngine] = useState(false)
  const [localGguf, setLocalGguf]     = useState('')
  const [localModels, setLocalModels] = useState([])
  const [localAvail, setLocalAvail]   = useState(true)
  const [saving, setSaving]           = useState(false)
  const [scanning, setScanning]       = useState(false)
  const [finding, setFinding]         = useState(false)
  const [foundPaths, setFoundPaths]   = useState([])
  const [scanResult, setScanResult]   = useState(null)
  const [didSearch, setDidSearch]     = useState(false)
  const [testingComfy, setTestingComfy] = useState(false)
  const [comfyTestResult, setComfyTestResult] = useState(null)
  const [memory, setMemory]         = useState({ facts: [], preferences: [] })
  const [newFact, setNewFact]       = useState('')
  const [newPref, setNewPref]       = useState('')

  useEffect(() => { loadConfig() }, [])
  useEffect(() => {
    if (config) {
      setTextModel(config.ollama_text_model ?? '')
      setVisionModel(config.ollama_vision_model ?? '')
      setComfyuiDir(config.comfyui_dir ?? '')
      setComfyuiUrl(config.comfyui_url ?? 'http://localhost:8188')
      setExtraDirs(config.extra_scan_dirs ?? [])
      setUseLocalEngine(!!config.use_local_engine)
      setLocalGguf(config.local_gguf_path ?? '')
    }
  }, [config])
  useEffect(() => {
    api.ollamaModels().then((m) => setOllamaList(m.models ?? [])).catch(() => {})
    api.localModels().then((r) => {
      setLocalAvail(!!r.available)
      setLocalModels(r.models ?? [])
      if (!localGguf && r.models?.length) setLocalGguf(r.models[0].path)
    }).catch(() => {})
    api.getPersona().then((p) => {
      if (p?.name) setAiName(p.name)
      if (p?.gender) setAiGender(p.gender)
      if (p?.personality) setAiPersonality(p.personality)
    }).catch(() => {})
  }, [])

  const savePersona = async () => {
    if (!aiName.trim()) { toast('Please enter a name', 'err'); return }
    setSavingPersona(true)
    try {
      await api.setPersona({ name: aiName.trim(), gender: aiGender, personality: aiPersonality })
      useStore.getState().fetchStatus?.()
      toast(`Saved — your assistant is now ${aiName.trim()}`, 'ok')
    } catch (e) { toast(e.message, 'err') }
    finally { setSavingPersona(false) }
  }

  const pullModel = async (m) => {
    if (!m.trim()) return
    try {
      await api.ollamaPull(m.trim()); toast(`Downloading ${m}…`, 'info'); setPullName('')
      ;[15000, 45000, 90000].forEach((d) => setTimeout(() =>
        api.ollamaModels().then((r) => setOllamaList(r.models ?? [])).catch(() => {}), d))
    } catch (e) { toast(e.message, 'err') }
  }

  const loadMemory = useCallback(async () => {
    try { setMemory(await api.getMemory()) } catch {}
  }, [])
  useEffect(() => { loadMemory() }, [loadMemory])

  const addFact = async () => {
    const f = newFact.trim(); if (!f) return
    try { await api.addMemoryFact(f); setNewFact(''); loadMemory(); toast('Fact saved', 'ok') }
    catch (e) { toast(e.message, 'err') }
  }
  const addPref = async () => {
    const p = newPref.trim(); if (!p) return
    try { await api.addMemoryPref(p); setNewPref(''); loadMemory(); toast('Preference saved', 'ok') }
    catch (e) { toast(e.message, 'err') }
  }
  const delFact = async (i) => { try { await api.delMemoryFact(i); loadMemory() } catch (e) { toast(e.message, 'err') } }
  const delPref = async (i) => { try { await api.delMemoryPref(i); loadMemory() } catch (e) { toast(e.message, 'err') } }
  const clearMem = async () => {
    if (!window.confirm('Clear all AI memory? This cannot be undone.')) return
    await api.clearMemory(); loadMemory(); toast('Memory cleared', 'ok')
  }

  const findComfyUI = async () => {
    setFinding(true); setFoundPaths([]); setDidSearch(true)
    try {
      const r = await api.findComfyUI()
      setFoundPaths(r.found ?? [])
      if (r.found?.length) toast(`Found ${r.found.length} ComfyUI installation(s)`, 'ok')
      else toast('No ComfyUI found — enter path manually below', 'info')
    } catch (e) { toast(e.message, 'err') }
    finally { setFinding(false) }
  }

  const save = async () => {
    setSaving(true)
    try {
      const body = {
        ollama_text_model: textModel,
        ollama_vision_model: visionModel,
        comfyui_dir: comfyuiDir,
        comfyui_url: comfyuiUrl,
        extra_scan_dirs: extraDirs.filter(Boolean),
        use_local_engine: useLocalEngine,
        local_gguf_path: localGguf,
      }
      if (hf.trim()) body.hf_token = hf.trim()
      if (civitai.trim()) body.civitai_token = civitai.trim()
      await api.setConfig(body)
      toast('Settings saved ✓', 'ok')
      setHf(''); setCivitai(''); loadConfig()
    } catch (e) { toast(e.message, 'err') }
    finally { setSaving(false) }
  }

  const testComfyUI = async () => {
    setTestingComfy(true); setComfyTestResult(null)
    try {
      await api.setConfig({ comfyui_url: comfyuiUrl })
      const r = await api.comfyuiStatus()
      setComfyTestResult(r)
      toast(r.connected ? `ComfyUI connected — v${r.version} ✓` : 'ComfyUI not reachable', r.connected ? 'ok' : 'err')
    } catch (e) { toast(e.message, 'err') }
    finally { setTestingComfy(false) }
  }

  const scan = async () => {
    setScanning(true); setScanResult(null)
    try {
      await api.setConfig({
        comfyui_dir: comfyuiDir,
        extra_scan_dirs: extraDirs.filter(Boolean),
      })
      const r = await api.scan()
      setScanResult(r)
      const total = Object.entries(r._summary ?? {}).reduce((a,[,v])=>a+v,0)
      toast(`Scan complete — ${total} model files found ✓`, 'ok')
    } catch (e) { toast(e.message, 'err') }
    finally { setScanning(false) }
  }

  const pull = async (m) => {
    if (!m.trim()) return toast('Enter a model name', 'info')
    try { await api.ollamaPull(m); toast(`Pulling ${m}…`, 'info') }
    catch (e) { toast(e.message, 'err') }
  }

  const addExtraDir = () => setExtraDirs((d) => [...d, ''])
  const setDir = (i, v) => setExtraDirs((d) => d.map((x,j) => j===i ? v : x))
  const removeDir = (i) => setExtraDirs((d) => d.filter((_,j) => j!==i))

  const summary = scanResult?._summary ?? {}
  const CAT_ICONS = {
    checkpoints:'🧠', loras:'🔧', vae:'🎨', text_encoders:'📝',
    controlnet:'🎯', upscalers:'🔍', ipadapter:'👤', video:'🎬',
    embeddings:'💬', hypernetworks:'🔀', clip_vision:'👁', style_models:'🖌',
    gligen:'📌', other:'📦',
  }

  return (
    <div className="page">
      <div className="page-narrow" style={{ maxWidth:820 }}>

        {/* ── STEP 1: Find ComfyUI ── */}
        <div className="panel" style={{ marginBottom:14 }}>
          <div className="panel-title">
            <span style={{ marginRight:8 }}>🔍</span>
            Step 1 — Find your models folder
          </div>
          <p className="muted" style={{ fontSize:13, lineHeight:1.65, marginBottom:16 }}>
            Click <strong style={{ color:'var(--text)' }}>Auto-detect ComfyUI</strong> — the app will search
            all drives (<span className="kbd">C:\</span> <span className="kbd">D:\</span> etc.) for a ComfyUI
            installation and find its <span className="kbd">models\</span> folder automatically.
            If you have models elsewhere, add the path manually below.
          </p>

          <button className="btn btn-primary" onClick={findComfyUI} disabled={finding}
            style={{ marginBottom:14 }}>
            {finding
              ? <><span className="spinner"/> Searching all drives…</>
              : <><Search size={16}/> Auto-detect ComfyUI</>}
          </button>

          {/* found results */}
          {didSearch && !finding && (
            foundPaths.length === 0 ? (
              <div style={{
                display:'flex', alignItems:'center', gap:10, padding:'12px 14px',
                background:'rgba(248,113,113,.08)', border:'1px solid rgba(248,113,113,.25)',
                borderRadius:'var(--r-md)', fontSize:13, color:'var(--text-dim)',
              }}>
                <AlertCircle size={16} style={{ color:'var(--rose)', flexShrink:0 }}/>
                No ComfyUI installation found automatically.
                Enter the path to your models folder manually in the field below.
              </div>
            ) : (
              <div style={{ display:'flex', flexDirection:'column', gap:6 }}>
                <div className="muted" style={{ fontSize:12, marginBottom:4 }}>
                  Found {foundPaths.length} installation{foundPaths.length>1?'s':''} — click to use:
                </div>
                {foundPaths.map((p) => (
                  <button key={p}
                    onClick={() => { setComfyuiDir(p); toast(`Selected: ${p}`, 'ok') }}
                    style={{
                      display:'flex', alignItems:'center', gap:10, padding:'11px 14px',
                      background: comfyuiDir===p ? 'rgba(74,222,128,.1)' : 'var(--ink-900)',
                      border: `1px solid ${comfyuiDir===p ? 'rgba(74,222,128,.4)' : 'var(--line)'}`,
                      borderRadius:'var(--r-md)', cursor:'pointer', textAlign:'left',
                      transition:'all .14s',
                    }}>
                    {comfyuiDir===p
                      ? <CheckCircle2 size={16} style={{ color:'var(--green)', flexShrink:0 }}/>
                      : <FolderOpen size={16} style={{ color:'var(--amber)', flexShrink:0 }}/>}
                    <div style={{ flex:1, minWidth:0 }}>
                      <div style={{ fontFamily:'var(--font-mono)', fontSize:12.5, wordBreak:'break-all', color:'var(--text)' }}>{p}</div>
                      <div className="muted" style={{ fontSize:11.5, marginTop:2 }}>
                        {p}\models\ will be scanned
                      </div>
                    </div>
                  </button>
                ))}
              </div>
            )
          )}

          {/* manual path input */}
          <div style={{ marginTop:14 }}>
            <div className="field" style={{ margin:0 }}>
              <label>ComfyUI folder path (manual)</label>
              <input className="input" value={comfyuiDir}
                onChange={(e) => setComfyuiDir(e.target.value)}
                placeholder="e.g. C:\ComfyUI  or  D:\AI\ComfyUI_windows_portable"/>
            </div>
            {comfyuiDir && (
              <div className="muted" style={{ fontSize:11.5, marginTop:6 }}>
                Will scan: <span className="kbd">{comfyuiDir}\models\</span>
              </div>
            )}
          </div>
        </div>

        {/* ── STEP 2: Extra dirs ── */}
        <div className="panel" style={{ marginBottom:14 }}>
          <div className="panel-title">
            <span style={{ marginRight:8 }}>📂</span>
            Step 2 — Add any other model directories (optional)
          </div>
          <p className="muted" style={{ fontSize:12.5, marginBottom:12 }}>
            Have models scattered in multiple folders? Add them all here.
            <span className="kbd" style={{ marginLeft:6 }}>backend\models\</span> is always scanned automatically.
          </p>
          <div style={{ display:'flex', flexDirection:'column', gap:6 }}>
            {extraDirs.map((d, i) => (
              <div key={i} className="row">
                <input className="input" value={d}
                  onChange={(e) => setDir(i, e.target.value)}
                  placeholder="D:\SharedModels  or  E:\StableDiffusion\models"/>
                <button className="btn btn-icon btn-ghost btn-danger" onClick={() => removeDir(i)}>
                  <X size={14}/>
                </button>
              </div>
            ))}
            <button className="btn btn-sm btn-ghost" style={{ alignSelf:'flex-start' }}
              onClick={addExtraDir}>
              <Plus size={13}/> Add another directory
            </button>
          </div>
        </div>

        {/* ── STEP 3: Scan ── */}
        <div className="panel" style={{ marginBottom:14 }}>
          <div className="panel-title">
            <span style={{ marginRight:8 }}>⚡</span>
            Step 3 — Scan & detect all models
          </div>
          <p className="muted" style={{ fontSize:12.5, marginBottom:14 }}>
            Scans every configured directory instantly. Detects checkpoints, LoRAs, VAE,
            text encoders (CLIP, T5), ControlNet, upscalers, WAN, IP-Adapters,
            embeddings — everything ComfyUI uses.
          </p>

          <button className="btn btn-primary btn-full" style={{ marginBottom:14 }}
            onClick={scan} disabled={scanning}>
            {scanning
              ? <><span className="spinner"/> Scanning…</>
              : <><ScanLine size={16}/> Scan all directories now</>}
          </button>

          {/* Scan results */}
          {scanResult && (
            <div style={{
              background:'var(--ink-900)', borderRadius:'var(--r-md)',
              border:'1px solid var(--line)', overflow:'hidden',
            }}>
              {/* summary bar */}
              <div style={{
                padding:'12px 16px', borderBottom:'1px solid var(--line)',
                display:'flex', alignItems:'center', gap:10, flexWrap:'wrap',
              }}>
                <CheckCircle2 size={16} style={{ color:'var(--green)', flexShrink:0 }}/>
                <span style={{ fontWeight:700, fontSize:14 }}>
                  {Object.values(summary).reduce((a,b)=>a+b,0)} model files found
                </span>
                <div style={{ display:'flex', flexWrap:'wrap', gap:6 }}>
                  {Object.entries(summary).map(([k,v]) => v > 0 && (
                    <span key={k} className="chip" style={{ fontSize:11.5 }}>
                      {CAT_ICONS[k] ?? '📦'} <strong style={{ color:'var(--amber-bright)' }}>{v}</strong> {k.replace(/_/g,' ')}
                    </span>
                  ))}
                </div>
              </div>

              {/* detailed list */}
              <div style={{ padding:'8px 0' }}>
                {Object.entries(scanResult).map(([cat, val]) => {
                  if (cat.startsWith('_') || !val) return null
                  const items = Array.isArray(val) ? val : Object.values(val).flat()
                  if (!items.length) return null
                  return (
                    <details key={cat} style={{ borderBottom:'1px solid var(--line-soft)' }}>
                      <summary style={{
                        cursor:'pointer', padding:'10px 16px',
                        display:'flex', alignItems:'center', gap:8,
                        fontSize:13.5, fontWeight:600, userSelect:'none',
                        listStyle:'none',
                      }}>
                        <span>{CAT_ICONS[cat] ?? '📦'}</span>
                        <span style={{ flex:1 }}>{cat.replace(/_/g,' ')}</span>
                        <span style={{
                          fontSize:11.5, padding:'2px 8px', borderRadius:999,
                          background:'rgba(255,179,71,.12)', color:'var(--amber-bright)',
                        }}>
                          {items.length} file{items.length!==1?'s':''}
                        </span>
                      </summary>
                      <div style={{ padding:'0 16px 12px', display:'flex', flexDirection:'column', gap:3 }}>
                        {items.map((m, i) => (
                          <div key={i} style={{
                            display:'flex', alignItems:'center', justifyContent:'space-between',
                            padding:'5px 0', borderBottom:'1px solid var(--line-soft)',
                          }}>
                            <div style={{ flex:1, minWidth:0 }}>
                              <div style={{ fontSize:13, fontWeight:500, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>
                                {m.name}
                              </div>
                              <div style={{ fontSize:11, color:'var(--text-faint)', fontFamily:'var(--font-mono)', overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>
                                {m.path}
                              </div>
                            </div>
                            <div style={{ flexShrink:0, marginLeft:12, textAlign:'right' }}>
                              <span className="chip" style={{ fontSize:11 }}>{m.size_gb}GB</span>
                            </div>
                          </div>
                        ))}
                      </div>
                    </details>
                  )
                })}
              </div>
            </div>
          )}
        </div>

        {/* ── Assistant persona ── */}
        <div className="panel" style={{ marginBottom:14 }}>
          <div className="panel-title"><Bot size={13} style={{ verticalAlign:-2, marginRight:6 }}/>Assistant persona</div>
          <p className="muted" style={{ fontSize:12.5, marginBottom:10 }}>
            Customise your AI assistant — its name, voice, and personality. This changes how it introduces
            itself and which voice reads replies aloud.
          </p>
          <div className="row" style={{ gap:12, flexWrap:'wrap', alignItems:'flex-end' }}>
            <div className="field" style={{ margin:0, flex:'1 1 220px' }}>
              <label>Assistant name</label>
              <input className="input" value={aiName} onChange={(e)=>setAiName(e.target.value)} placeholder="e.g. Nova, Aria, Max…"/>
            </div>
            <div className="field" style={{ margin:0, width:150 }}>
              <label>Voice</label>
              <select className="select" value={aiGender} onChange={(e)=>setAiGender(e.target.value)}>
                <option value="female">Female</option>
                <option value="male">Male</option>
              </select>
            </div>
          </div>
          <div className="field" style={{ marginTop:12, marginBottom:0 }}>
            <label>Personality &amp; behaviour (optional)</label>
            <textarea className="input" rows={3} value={aiPersonality} onChange={(e)=>setAiPersonality(e.target.value)}
              placeholder="e.g. 'Friendly and concise. Explains things simply and cracks the occasional joke.'"
              style={{ resize:'vertical', fontFamily:'inherit' }}/>
          </div>
          <div className="row" style={{ marginTop:12, justifyContent:'flex-end' }}>
            <button className="btn btn-primary" onClick={savePersona} disabled={savingPersona}>
              {savingPersona ? <span className="spinner"/> : 'Save persona'}
            </button>
          </div>
        </div>

        {/* ── AI Engine ── */}
        <div className="panel" style={{ marginBottom:14 }}>
          <div className="panel-title"><Bot size={13} style={{ verticalAlign:-2, marginRight:6 }}/>AI Engine (100% free &amp; local)</div>
          <p className="muted" style={{ fontSize:12.5, marginBottom:10 }}>
            Choose what runs chat. Both are free and run on your PC — no cloud, no API keys, no limits.
          </p>
          <div className="row" style={{ gap:8, marginBottom:10 }}>
            <button className={'btn btn-sm' + (!useLocalEngine ? ' btn-primary' : '')} onClick={()=>setUseLocalEngine(false)}>Ollama</button>
            <button className={'btn btn-sm' + (useLocalEngine ? ' btn-primary' : '')} onClick={()=>setUseLocalEngine(true)}>Built-in (no Ollama)</button>
          </div>
          {useLocalEngine ? (
            <div>
              {!localAvail && (
                <p className="muted" style={{ fontSize:12, color:'#e0a458', marginBottom:8 }}>
                  Engine not installed — run <span className="kbd">install.bat</span> (adds llama-cpp-python), then restart.
                </p>
              )}
              <label style={{ fontSize:12, display:'block', marginBottom:4 }}>Local GGUF chat model</label>
              {localModels.length ? (
                <select className="select" value={localGguf} onChange={(e)=>setLocalGguf(e.target.value)}>
                  {localModels.map((m)=>(<option key={m.path} value={m.path}>{m.name} ({m.size_gb} GB)</option>))}
                </select>
              ) : (
                <p className="muted" style={{ fontSize:12 }}>
                  No .gguf chat model found. Download one (e.g. from huggingface.co) and drop it in
                  <span className="kbd"> models\llm\ </span>, then reopen this page.
                </p>
              )}
            </div>
          ) : (
            <div className="grid-2">
              <div className="field" style={{ margin:0 }}>
                <label>Text model <span className="muted" style={{ fontWeight:400 }}>(chat)</span></label>
                <select className="select" value={textModel} onChange={(e)=>setTextModel(e.target.value)}>
                  {!textModel && <option value="">Select…</option>}
                  {[...new Set([textModel, ...ollamaList.filter(isChatModel)].filter(Boolean))].map((m)=>(<option key={m} value={m}>{m}</option>))}
                </select>
              </div>
              <div className="field" style={{ margin:0 }}>
                <label>Vision model <span className="muted" style={{ fontWeight:400 }}>(image understanding)</span></label>
                <select className="select" value={visionModel} onChange={(e)=>setVisionModel(e.target.value)}>
                  {!visionModel && <option value="">Select…</option>}
                  {[...new Set([visionModel, ...ollamaList.filter(isVisionModel)].filter(Boolean))].map((m)=>(<option key={m} value={m}>{m}</option>))}
                </select>
              </div>
            </div>
          )}
          {!useLocalEngine && (
            <div className="row" style={{ gap:8, alignItems:'flex-end', marginTop:10, flexWrap:'wrap' }}>
              <div className="field" style={{ margin:0, flex:'1 1 240px' }}>
                <label>Download a new Ollama model</label>
                <input className="input" value={pullName} onChange={(e)=>setPullName(e.target.value)} placeholder="e.g. llama3.2:3b, qwen2.5:3b"/>
              </div>
              <button className="btn btn-sm" disabled={!pullName.trim()} onClick={()=>pullModel(pullName)}><DlIcon size={13}/> Download</button>
            </div>
          )}
          <p className="muted" style={{ fontSize:12, marginTop:10 }}>
            Installed (Ollama): {ollamaList.length ? ollamaList.join(', ') : 'none detected'}
          </p>
        </div>

        {/* ── HF Token ── */}
        <div className="panel" style={{ marginBottom:14 }}>
          <div className="panel-title"><KeyRound size={13} style={{ verticalAlign:-2, marginRight:6 }}/>HuggingFace token</div>
          <div className="field" style={{ margin:0 }}>
            <label>Token for gated model downloads (FLUX, Wan, etc.)</label>
            <input className="input" type="password" value={hf}
              onChange={(e)=>setHf(e.target.value)}
              placeholder={config?.hf_token ? '●●●●●●●● (saved)' : 'hf_…'}/>
          </div>
        </div>

        {/* ── CivitAI Token ── */}
        <div className="panel" style={{ marginBottom:14 }}>
          <div className="panel-title"><KeyRound size={13} style={{ verticalAlign:-2, marginRight:6 }}/>CivitAI API token</div>
          <div className="field" style={{ margin:0 }}>
            <label>Token for CivitAI model downloads (needed for some community models, e.g. Wan 2.2)</label>
            <input className="input" type="password" value={civitai}
              onChange={(e)=>setCivitai(e.target.value)}
              placeholder={config?.civitai_token ? '●●●● (saved)' : 'Paste CivitAI API key…'}/>
          </div>
          <p className="muted" style={{ fontSize:12, marginTop:8 }}>
            Get your key at <span className="kbd">civitai.com → Account → API Keys</span>
          </p>
        </div>

        {/* ── ComfyUI Connection ── */}
        <div className="panel" style={{ marginBottom:14 }}>
          <div className="panel-title"><Layers size={13} style={{ verticalAlign:-2, marginRight:6 }}/>ComfyUI connection</div>
          <p className="muted" style={{ fontSize:12.5, marginBottom:12 }}>
            Connect to a running ComfyUI instance to route generation through it.
            Default: <span className="kbd">http://localhost:8188</span>
          </p>
          <div className="field" style={{ marginBottom:10 }}>
            <label>ComfyUI API URL</label>
            <div className="row">
              <input className="input" value={comfyuiUrl}
                onChange={(e)=>setComfyuiUrl(e.target.value)}
                placeholder="http://localhost:8188"/>
              <button className="btn btn-sm" onClick={testComfyUI} disabled={testingComfy}>
                {testingComfy ? <span className="spinner"/> : 'Test'}
              </button>
            </div>
          </div>
          {comfyTestResult && (
            <div style={{ display:'flex', alignItems:'center', gap:8, fontSize:12.5 }}>
              {comfyTestResult.connected
                ? <><CheckCircle2 size={14} style={{ color:'var(--green)' }}/> Connected — v{comfyTestResult.version}</>
                : <><AlertCircle size={14} style={{ color:'var(--rose)' }}/> Not reachable — is ComfyUI running?</>}
            </div>
          )}
        </div>

        <button className="btn btn-primary" onClick={save} disabled={saving} style={{ marginBottom:22 }}>
          {saving ? <span className="spinner"/> : <Save size={15}/>} Save all settings
        </button>

        {/* ── AI Memory ── */}
        <div className="panel" style={{ marginBottom:14 }}>
          <div className="panel-title" style={{ display:'flex', justifyContent:'space-between', alignItems:'center' }}>
            <span><Brain size={13} style={{ verticalAlign:-2, marginRight:6 }}/>AI Memory</span>
            <button className="btn btn-sm" style={{ color:'var(--red)', fontSize:11 }} onClick={clearMem}>
              <Trash2 size={11}/> Clear all
            </button>
          </div>
          <p className="muted" style={{ fontSize:12.5, marginBottom:14 }}>
            Facts and preferences the AI remembers across all conversations.
            Auto-extracted from chat + manually added here.
          </p>

          {/* Facts */}
          <div style={{ marginBottom:16 }}>
            <div style={{ fontSize:12, fontWeight:600, color:'var(--text-muted)', marginBottom:8, textTransform:'uppercase', letterSpacing:'.06em' }}>
              Facts ({memory.facts.length})
            </div>
            {memory.facts.length === 0
              ? <p className="muted" style={{ fontSize:12 }}>No facts saved yet — the AI will learn them from chat.</p>
              : <div style={{ display:'flex', flexDirection:'column', gap:4, marginBottom:8 }}>
                  {memory.facts.map((f, i) => (
                    <div key={i} className="memory-row">
                      <span className="memory-text">{f}</span>
                      <button className="btn-ghost btn-icon" onClick={() => delFact(i)} title="Remove">
                        <X size={12}/>
                      </button>
                    </div>
                  ))}
                </div>}
            <div className="row" style={{ gap:6, marginTop:6 }}>
              <input className="input" style={{ flex:1 }} value={newFact}
                onChange={(e) => setNewFact(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && addFact()}
                placeholder="e.g. My name is Sachin, I live in India"/>
              <button className="btn btn-sm" onClick={addFact} disabled={!newFact.trim()}>
                <Plus size={13}/> Add
              </button>
            </div>
          </div>

          {/* Preferences */}
          <div>
            <div style={{ fontSize:12, fontWeight:600, color:'var(--text-muted)', marginBottom:8, textTransform:'uppercase', letterSpacing:'.06em' }}>
              Preferences ({memory.preferences.length})
            </div>
            {memory.preferences.length === 0
              ? <p className="muted" style={{ fontSize:12 }}>No preferences saved yet.</p>
              : <div style={{ display:'flex', flexDirection:'column', gap:4, marginBottom:8 }}>
                  {memory.preferences.map((p, i) => (
                    <div key={i} className="memory-row">
                      <span className="memory-text">{p}</span>
                      <button className="btn-ghost btn-icon" onClick={() => delPref(i)} title="Remove">
                        <X size={12}/>
                      </button>
                    </div>
                  ))}
                </div>}
            <div className="row" style={{ gap:6, marginTop:6 }}>
              <input className="input" style={{ flex:1 }} value={newPref}
                onChange={(e) => setNewPref(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && addPref()}
                placeholder="e.g. I prefer anime art style, dark themes"/>
              <button className="btn btn-sm" onClick={addPref} disabled={!newPref.trim()}>
                <Plus size={13}/> Add
              </button>
            </div>
          </div>

          {/* Summaries */}
          {memory.summaries?.length > 0 && (
            <div style={{ marginTop:16, borderTop:'1px solid var(--line)', paddingTop:14 }}>
              <div style={{ fontSize:12, fontWeight:600, color:'var(--text-muted)', marginBottom:8, textTransform:'uppercase', letterSpacing:'.06em' }}>
                Past conversation highlights
              </div>
              <div style={{ display:'flex', flexDirection:'column', gap:6 }}>
                {memory.summaries.slice(-5).reverse().map((s, i) => (
                  <div key={i} className="memory-row" style={{ alignItems:'flex-start', gap:10 }}>
                    <span style={{ fontSize:10, color:'var(--text-dim)', fontFamily:'var(--font-mono)', flexShrink:0, marginTop:2 }}>{s.date}</span>
                    <span className="memory-text" style={{ fontSize:12 }}>{s.summary}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* ── System info ── */}
        <div className="panel">
          <div className="panel-title"><Cpu size={13} style={{ verticalAlign:-2, marginRight:6 }}/>System info</div>
          <div className="info-grid">
            <InfoCell label="GPU"          value={status?.cuda ? status.gpu : 'CPU only'}/>
            <InfoCell label="VRAM"         value={status?.vram_gb ? `${status.vram_gb} GB` : '—'}/>
            <InfoCell label="Ollama"       value={status?.ollama ? '● connected' : '○ offline'}/>
            <InfoCell label="Engine"       value={status?.use_local_engine ? 'Built-in (local)' : 'Ollama'}/>
            <InfoCell label="Text model"   value={config?.ollama_text_model ?? '—'}/>
            <InfoCell label="Vision model" value={config?.ollama_vision_model ?? '—'}/>
          </div>
        </div>
      </div>
    </div>
  )
}

function InfoCell({ label, value }) {
  return (
    <div className="info-cell">
      <div className="info-label">{label}</div>
      <div className="info-val">{value}</div>
    </div>
  )
}
