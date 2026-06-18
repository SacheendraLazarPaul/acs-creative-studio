import { useEffect, useState, useCallback, useRef, useMemo } from 'react'
import {
  Wand2, Sparkles, Dice5, Download as DlIcon, ImagePlus, X,
  Lightbulb, LayoutGrid, FolderOpen, Brain, Layers, ChevronDown, ChevronUp,
  Image, Repeat, PenTool, Film, Clapperboard, SlidersHorizontal, Cpu, Shuffle,
  Bookmark, Trash2, Eraser, ArrowRight, Scissors,
  Zap, ListOrdered, Save, ScanSearch, Star, ArrowUpDown, Clock,
  Search, Sliders,
} from 'lucide-react'
import { api, fileToB64 } from '../api'
import { useStore } from '../store'
import FileBrowser from '../components/FileBrowser'

/* ─── constants ─── */
const MODES = [
  { id:'t2i',    label:'Text → Image',   short:'T2I',  Icon:Image },
  { id:'i2i',    label:'Image → Image',  short:'I2I',  Icon:Repeat },
  { id:'inpaint',label:'Inpaint',        short:'Paint',Icon:PenTool },
  { id:'t2v',    label:'Text → Video',   short:'T2V',  Icon:Film },
  { id:'i2v',    label:'Image → Video',  short:'I2V',  Icon:Clapperboard },
  { id:'outpaint',label:'Outpaint',       short:'Expand',Icon:ScanSearch },
  { id:'upscale',label:'Upscale',        short:'4×↑',  Icon:Sparkles },
]
const RATIOS = [
  { label:'Square',    sub:'1:1',  w:512,  h:512,  shape:[1,1]  },
  { label:'Portrait',  sub:'2:3',  w:512,  h:768,  shape:[2,3]  },
  { label:'Landscape', sub:'3:2',  w:768,  h:512,  shape:[3,2]  },
  { label:'Wide',      sub:'16:9', w:896,  h:504,  shape:[16,9] },
]
const CONSISTENCY = [
  { id:'none',      label:'None' },
  { id:'face',      label:'Face (IP-Adapter)' },
  { id:'character', label:'Style / Character' },
]
const MODEL_EXTS = '.safetensors,.ckpt,.pt,.bin,.pth'
const LORA_EXTS  = '.safetensors,.pt,.bin'

/* ─── inpaint brush ─── */
function InpaintBrush({ image, onMask }) {
  const canvasRef = useRef(null)
  const drawing   = useRef(false)
  const [brushSize, setBrushSize] = useState(24)
  const [brushMode, setBrushMode] = useState('paint') // 'paint' | 'erase'

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    ctx.fillStyle = 'black'
    ctx.fillRect(0, 0, canvas.width, canvas.height)
  }, [])

  const getPos = (e) => {
    const canvas = canvasRef.current
    const rect   = canvas.getBoundingClientRect()
    const scaleX = canvas.width  / rect.width
    const scaleY = canvas.height / rect.height
    const src    = e.touches ? e.touches[0] : e
    return [(src.clientX - rect.left) * scaleX, (src.clientY - rect.top) * scaleY]
  }

  const drawDot = (e) => {
    if (!drawing.current) return
    const canvas = canvasRef.current
    const ctx    = canvas.getContext('2d')
    const [x, y] = getPos(e)
    ctx.fillStyle = brushMode === 'paint' ? 'white' : 'black'
    ctx.beginPath()
    ctx.arc(x, y, brushSize, 0, Math.PI * 2)
    ctx.fill()
  }

  const start = (e) => { e.preventDefault(); drawing.current = true; drawDot(e) }
  const move  = (e) => { e.preventDefault(); drawDot(e) }
  const stop  = () => {
    if (!drawing.current) return
    drawing.current = false
    onMask(canvasRef.current.toDataURL('image/png'))
  }

  return (
    <div className="inpaint-wrap">
      <div style={{ position:'relative' }}>
        <img src={image} className="inpaint-bg" alt="ref"/>
        <canvas ref={canvasRef} width={512} height={512} className="inpaint-canvas"
          onMouseDown={start} onMouseMove={move} onMouseUp={stop} onMouseLeave={stop}
          onTouchStart={start} onTouchMove={move} onTouchEnd={stop}/>
      </div>
      <div className="inpaint-toolbar">
        <button className={'batch-btn' + (brushMode === 'paint' ? ' active' : '')} onClick={() => setBrushMode('paint')}>
          <PenTool size={11}/> Paint
        </button>
        <button className={'batch-btn' + (brushMode === 'erase' ? ' active' : '')} onClick={() => setBrushMode('erase')}>
          <Eraser size={11}/> Erase
        </button>
        <span style={{ marginLeft:'auto', fontSize:11, opacity:.6 }}>Brush</span>
        <input type="range" min="4" max="64" value={brushSize} className="range"
          style={{ width:70 }} onChange={(e) => setBrushSize(+e.target.value)}/>
        <span style={{ fontSize:11, minWidth:20 }}>{brushSize}</span>
      </div>
    </div>
  )
}

/* ─── before/after compare slider ─── */
function BeforeAfterSlider({ before, after }) {
  const [pos, setPos] = useState(50)
  const dragging = useRef(false)
  const wrapRef  = useRef(null)

  const calcPos = (clientX) => {
    const rect = wrapRef.current?.getBoundingClientRect()
    if (!rect) return
    setPos(Math.max(2, Math.min(98, ((clientX - rect.left) / rect.width) * 100)))
  }

  return (
    <div ref={wrapRef} className="compare-wrap"
      onMouseMove={(e) => { if (dragging.current) calcPos(e.clientX) }}
      onMouseUp={() => { dragging.current = false }}
      onMouseLeave={() => { dragging.current = false }}>
      <img src={before} className="compare-img" alt="before"/>
      <div className="compare-after" style={{ clipPath:`inset(0 ${100-pos}% 0 0)` }}>
        <img src={after} className="compare-img" alt="after"/>
      </div>
      <div className="compare-handle" style={{ left:`${pos}%` }}
        onMouseDown={(e) => { e.preventDefault(); dragging.current = true }}/>
      <span className="compare-lbl compare-lbl-l">Before</span>
      <span className="compare-lbl compare-lbl-r">After</span>
    </div>
  )
}

/* ─── CivitAI browser modal ─── */
const CIVITAI_TYPES = ['','Checkpoint','LORA','LoCon','TextualInversion','VAE','Upscaler']

function CivitaiBrowser({ onClose, onDownloadStart, toast }) {
  const [query, setQuery]       = useState('')
  const [typeF, setTypeF]       = useState('')
  const [models, setModels]     = useState([])
  const [loading, setLoading]   = useState(false)
  const [page, setPage]         = useState(1)
  const [total, setTotal]       = useState(0)
  const [downloading, setDl]    = useState({})
  const [expanded, setExpanded] = useState(null)
  const [imgErr, setImgErr]     = useState({})

  const search = async (p = 1) => {
    setLoading(true); setPage(p); if (p === 1) setModels([])
    try {
      const r = await api.civitaiBrowse(query, typeF, p)
      if (r.error) { toast(r.error, 'err'); return }
      setModels(p === 1 ? (r.models || []) : (prev => [...prev, ...(r.models || [])]))
      setTotal(r.total || 0)
    } catch (e) { toast(e.message, 'err') }
    finally { setLoading(false) }
  }

  const download = async (m) => {
    setDl(d => ({ ...d, [m.version_id]: 'queued' }))
    try {
      const r = await api.civitaiDownload({
        version_id:   m.version_id,
        name:         m.name,
        filename:     m.filename,
        download_url: m.download_url,
        type:         m.type,
        size_mb:      m.size_mb,
        save_dir:     m.save_dir,
      })
      if (r.ok) {
        setDl(d => ({ ...d, [m.version_id]: 'downloading' }))
        onDownloadStart(r.model_id)
        toast(`Downloading ${m.name}… check Downloads tab`, 'ok')
      } else {
        toast(r.error || 'Download failed', 'err')
        setDl(d => ({ ...d, [m.version_id]: null }))
      }
    } catch (e) {
      toast(e.message, 'err')
      setDl(d => ({ ...d, [m.version_id]: null }))
    }
  }

  useEffect(() => { search(1) }, []) // eslint-disable-line

  const TYPE_COLOR = {
    Checkpoint:'var(--amber-bright)', LORA:'var(--cyan)', LoCon:'var(--cyan)',
    TextualInversion:'var(--violet)', VAE:'var(--green)', Upscaler:'var(--rose)',
  }

  return (
    <div className="civitai-overlay" onClick={onClose}>
      <div className="civitai-modal" onClick={e => e.stopPropagation()}>
        {/* header */}
        <div className="civitai-header">
          <span style={{ fontWeight:700, fontSize:16 }}>🌐 CivitAI Browser</span>
          <span style={{ fontSize:12, color:'var(--text-faint)', marginLeft:8 }}>
            {total > 0 ? `${total.toLocaleString()} models` : ''}
          </span>
          <button className="btn-ghost btn-icon" style={{ marginLeft:'auto' }} onClick={onClose}><X size={16}/></button>
        </div>

        {/* search bar */}
        <div className="civitai-search-bar">
          <input className="input" style={{ flex:1 }} placeholder="Search models, LoRAs, VAEs…"
            value={query} onChange={e => setQuery(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && search(1)}/>
          <select className="select" style={{ width:140 }} value={typeF} onChange={e => setTypeF(e.target.value)}>
            {CIVITAI_TYPES.map(t => <option key={t} value={t}>{t || 'All types'}</option>)}
          </select>
          <button className="btn btn-primary" onClick={() => search(1)} disabled={loading}>
            {loading ? <span className="spinner"/> : <Search size={14}/>} Search
          </button>
        </div>

        {/* grid */}
        <div className="civitai-grid">
          {models.length === 0 && !loading && (
            <div className="empty" style={{ gridColumn:'1/-1' }}>
              <p>Search for any model — checkpoints, LoRAs, VAEs…</p>
            </div>
          )}
          {models.map(m => (
            <div key={m.version_id} className={'civitai-card' + (expanded === m.version_id ? ' expanded' : '')}>
              <div className="civitai-preview-wrap" onClick={() => setExpanded(expanded === m.version_id ? null : m.version_id)}>
                {m.preview && !imgErr[m.version_id]
                  ? <img src={m.preview} className="civitai-preview" alt={m.name}
                      onError={() => setImgErr(e => ({...e, [m.version_id]: true}))}/>
                  : <div className="civitai-no-preview">No preview</div>}
                <span className="civitai-type-badge" style={{ background: TYPE_COLOR[m.type] || 'var(--ink-700)' }}>
                  {m.type}
                </span>
              </div>
              <div className="civitai-card-body">
                <div className="civitai-name" title={m.name}>{m.name}</div>
                <div className="civitai-meta">
                  <span style={{ color:'var(--text-faint)', fontSize:11 }}>by {m.creator || '?'}</span>
                  <span style={{ fontSize:11 }}>{m.size_mb > 0 ? `${m.size_mb} MB` : ''}</span>
                </div>
                {m.stats?.downloadCount > 0 && (
                  <div className="civitai-stats">
                    <span>↓ {(m.stats.downloadCount/1000).toFixed(1)}k</span>
                    {m.stats.rating > 0 && <span>★ {m.stats.rating.toFixed(1)}</span>}
                  </div>
                )}
                {m.tags?.length > 0 && (
                  <div className="civitai-tags">
                    {m.tags.slice(0,3).map(t => <span key={t} className="civitai-tag">{t}</span>)}
                  </div>
                )}
                <button
                  className={'btn btn-sm btn-full' + (downloading[m.version_id] ? ' btn-primary' : '')}
                  disabled={!!downloading[m.version_id]}
                  onClick={() => download(m)}>
                  {downloading[m.version_id] === 'downloading'
                    ? <><span className="spinner"/> Downloading…</>
                    : downloading[m.version_id] === 'queued'
                      ? <><span className="spinner"/> Queued…</>
                      : <><DlIcon size={12}/> Download {m.version_name}</>}
                </button>
              </div>
            </div>
          ))}
          {loading && <div className="civitai-loading"><span className="spinner lg"/></div>}
        </div>

        {/* load more */}
        {models.length > 0 && models.length < total && !loading && (
          <div style={{ textAlign:'center', padding:'12px 0' }}>
            <button className="btn" onClick={() => search(page + 1)}>Load more</button>
          </div>
        )}
      </div>
    </div>
  )
}

/* ─── color grade + crop ─── */
function PostProcess({ imageB64, onUpdate }) {
  const [bright, setBright]   = useState(0)
  const [contrast, setContrast] = useState(0)
  const [sat, setSat]         = useState(0)
  const [hue, setHue]         = useState(0)
  const [cropMode, setCropMode] = useState(false)
  const [crop, setCrop]       = useState(null)
  const [dragging, setDragging] = useState(false)
  const [startPt, setStartPt] = useState(null)
  const imgRef  = useRef(null)
  const cropRef = useRef(null)

  const filter = `brightness(${1 + bright/100}) contrast(${1 + contrast/100}) saturate(${1 + sat/100}) hue-rotate(${hue}deg)`

  const applyGrading = () => {
    const img = new window.Image()
    img.onload = () => {
      const c = document.createElement('canvas')
      c.width = img.naturalWidth; c.height = img.naturalHeight
      const ctx = c.getContext('2d')
      ctx.filter = filter
      ctx.drawImage(img, 0, 0)
      onUpdate(c.toDataURL('image/png').split(',')[1])
    }
    img.src = `data:image/png;base64,${imageB64}`
  }

  const getImgCoords = (e) => {
    const rect = imgRef.current.getBoundingClientRect()
    const nw   = imgRef.current.naturalWidth
    const nh   = imgRef.current.naturalHeight
    return {
      x: Math.max(0, Math.min(nw, ((e.clientX - rect.left) / rect.width)  * nw)),
      y: Math.max(0, Math.min(nh, ((e.clientY - rect.top)  / rect.height) * nh)),
    }
  }

  const startCrop = (e) => {
    if (!cropMode) return
    const pt = getImgCoords(e)
    setStartPt(pt); setDragging(true); setCrop({ ...pt, w:0, h:0 })
  }

  const moveCrop = (e) => {
    if (!dragging || !startPt) return
    const pt = getImgCoords(e)
    setCrop({
      x: Math.min(startPt.x, pt.x), y: Math.min(startPt.y, pt.y),
      w: Math.abs(pt.x - startPt.x), h: Math.abs(pt.y - startPt.y),
    })
  }

  const applyCrop = () => {
    if (!crop || crop.w < 4 || crop.h < 4) return
    const img = new window.Image()
    img.onload = () => {
      const c = document.createElement('canvas')
      c.width = crop.w; c.height = crop.h
      c.getContext('2d').drawImage(img, crop.x, crop.y, crop.w, crop.h, 0, 0, crop.w, crop.h)
      onUpdate(c.toDataURL('image/png').split(',')[1])
      setCrop(null); setCropMode(false)
    }
    img.src = `data:image/png;base64,${imageB64}`
  }

  const reset = () => { setBright(0); setContrast(0); setSat(0); setHue(0) }

  const rectStyle = crop && cropMode ? {
    position:'absolute',
    left: `${(crop.x / imgRef.current?.naturalWidth) * 100}%`,
    top:  `${(crop.y / imgRef.current?.naturalHeight) * 100}%`,
    width: `${(crop.w / imgRef.current?.naturalWidth) * 100}%`,
    height:`${(crop.h / imgRef.current?.naturalHeight) * 100}%`,
    border:'2px dashed var(--cyan)', pointerEvents:'none',
  } : null

  return (
    <div className="postprocess-panel">
      <div className="postprocess-preview" style={{ position:'relative', cursor: cropMode ? 'crosshair' : 'default' }}
        onMouseDown={startCrop} onMouseMove={moveCrop} onMouseUp={() => setDragging(false)}>
        <img ref={imgRef} src={`data:image/png;base64,${imageB64}`}
          style={{ width:'100%', display:'block', filter, borderRadius:'var(--r-md)' }} alt="result"/>
        {rectStyle && <div style={rectStyle}/>}
      </div>

      {/* grade sliders */}
      <div className="pp-sliders">
        {[
          ['☀ Bright', bright, setBright, -100, 100],
          ['◑ Contrast', contrast, setContrast, -100, 100],
          ['⬡ Sat', sat, setSat, -100, 100],
          ['🎨 Hue', hue, setHue, -180, 180],
        ].map(([label, val, set, min, max]) => (
          <div key={label} className="pp-row">
            <span className="pp-label">{label}</span>
            <input type="range" className="range" min={min} max={max} value={val}
              style={{ flex:1 }} onChange={e => set(+e.target.value)}/>
            <span className="range-val" style={{ minWidth:32 }}>{val > 0 ? '+':''}{val}</span>
          </div>
        ))}
      </div>

      <div className="pp-actions">
        <button className="btn btn-sm" onClick={reset}>Reset</button>
        <button className={'btn btn-sm' + (cropMode ? ' btn-primary' : '')}
          onClick={() => { setCropMode(v => !v); setCrop(null) }}>
          ✂ {cropMode ? 'Cancel crop' : 'Crop'}
        </button>
        {cropMode && crop?.w > 4 && (
          <button className="btn btn-sm btn-cyan" onClick={applyCrop}>Apply crop</button>
        )}
        {!cropMode && (bright || contrast || sat || hue) ? (
          <button className="btn btn-sm btn-primary" onClick={applyGrading}>Apply grading</button>
        ) : null}
      </div>
    </div>
  )
}

const SCHEDULERS = [
  { value: '',                label: 'Default (model built-in)' },
  { value: 'euler_a',         label: 'Euler Ancestral' },
  { value: 'euler',           label: 'Euler' },
  { value: 'dpm++_2m',        label: 'DPM++ 2M' },
  { value: 'dpm++_2m_karras', label: 'DPM++ 2M Karras ✦' },
  { value: 'dpm++_sde',       label: 'DPM++ SDE' },
  { value: 'dpm++_sde_karras',label: 'DPM++ SDE Karras ✦' },
  { value: 'ddim',            label: 'DDIM' },
  { value: 'pndm',            label: 'PNDM' },
  { value: 'heun',            label: 'Heun' },
  { value: 'unipc',           label: 'UniPC' },
  { value: 'lcm',             label: 'LCM (4–8 steps)' },
  { value: 'lms',             label: 'LMS' },
  { value: 'deis',            label: 'DEIS' },
  { value: 'kdpm2_a',         label: 'KDPM2 Ancestral' },
  { value: 'kdpm2',           label: 'KDPM2' },
]

const NEG_PRESETS = [
  'blurry, low quality', 'deformed, ugly', 'extra limbs', 'text, watermark',
  'nsfw', 'cropped', 'oversaturated', 'bad anatomy',
]

/* ─── main page ─── */
const _loadSettings = () => { try { return JSON.parse(localStorage.getItem('acs_settings') || '{}') } catch { return {} } }

export default function GeneratePage() {
  const { status, toast, comfyuiStatus, pendingRef, clearPendingRef } = useStore()
  const _s = useRef(_loadSettings()).current

  const [mode, setMode]         = useState(_s.mode      || 't2i')
  const [prompt, setPrompt]     = useState(_s.prompt     || '')
  const [negative, setNeg]      = useState(_s.negative   || 'bad quality, blurry, deformed, ugly, watermark, low resolution')
  const [w, setW]               = useState(_s.w          ?? 512)
  const [h, setH]               = useState(_s.h          ?? 512)
  const [steps, setSteps]       = useState(_s.steps      ?? 15)
  const [cfg, setCfg]           = useState(_s.cfg        ?? 7.0)
  const [strength, setStrength] = useState(_s.strength   ?? 0.75)
  const [seed, setSeed]         = useState(_s.seed       ?? -1)
  const [frames, setFrames]     = useState(_s.frames     ?? 25)
  const [fps, setFps]           = useState(_s.fps        ?? 8)
  const [consistency, setConsistency] = useState(_s.consistency || 'none')

  const [scannedCheckpoints, setScannedCheckpoints] = useState([])
  const [scannedVideoModels, setScannedVideoModels] = useState([])
  const [scannedControlnets, setScannedControlnets] = useState([])
  const [checkpoint, setCheckpoint] = useState(_s.checkpoint      || '')
  const [videoModel, setVideoModel] = useState(_s.videoModel      || '')
  const [manualCheckpoint, setManualCheckpoint] = useState(_s.manualCheckpoint || '')
  const [scannedLoras, setScannedLoras]     = useState({})
  const [activeLoras, setActiveLoras]       = useState(_s.activeLoras  ?? [])
  const [controlnet, setControlnet]         = useState(_s.controlnet   || '')
  const [cnImage, setCnImage]               = useState(null)
  const [cnStrength, setCnStrength]         = useState(_s.cnStrength   ?? 1.0)
  const [wanComponents, setWanComponents]   = useState(null)

  const [refImage, setRefImage]   = useState(null)
  const [maskImage, setMaskImage] = useState(null)
  const [result, setResult]       = useState(null)
  const [busy, setBusy]           = useState(false)

  const [elapsed, setElapsed]   = useState(0)
  const timerRef                = useRef(null)

  useEffect(() => {
    const working = busy || status?.gen_status === 'generating'
    if (working) {
      setElapsed(0)
      timerRef.current = setInterval(() => setElapsed((s) => s + 1), 1000)
      return () => { clearInterval(timerRef.current); timerRef.current = null }
    } else {
      clearInterval(timerRef.current)
      timerRef.current = null
    }
  }, [busy, status?.gen_status])

  const [batchSize, setBatchSize]       = useState(_s.batchSize ?? 1)
  const [batchResults, setBatchResults] = useState([])
  const [templates, setTemplates]       = useState(() => {
    try { return JSON.parse(localStorage.getItem('acs_templates') || '[]') } catch { return [] }
  })
  const [showTemplates, setShowTemplates] = useState(false)
  const [removingBg, setRemovingBg]     = useState(false)

  const [tips, setTips]               = useState([])
  const [enhancing, setEnhancing]     = useState(false)
  const [suggestions, setSuggestions] = useState([])
  const [suggesting, setSuggesting]   = useState(false)
  const [theme, setTheme]             = useState('')
  const [browser, setBrowser]         = useState(null)
  const [advancedOpen, setAdvancedOpen] = useState(false)
  const [advisorOpen, setAdvisorOpen]   = useState(false)
  const [advisorGoal, setAdvisorGoal]   = useState('')
  const [advisorResult, setAdvisorResult] = useState(null)
  const [advisorBusy, setAdvisorBusy]   = useState(false)
  const [useComfyUI, setUseComfyUI]     = useState(_s.useComfyUI   ?? false)

  const [upscaleFactor, setUpscaleFactor] = useState(_s.upscaleFactor ?? 4)

  // hires fix
  const [hiresFix, setHiresFix]         = useState(_s.hiresFix      ?? false)
  const [hiresScale, setHiresScale]     = useState(_s.hiresScale     ?? 1.5)
  const [hiresStrength, setHiresStrength] = useState(_s.hiresStrength ?? 0.5)

  // compare mode
  const [compareMode, setCompareMode]   = useState(false)

  // scheduler / vae / clip skip / seamless / outpaint
  const [scheduler, setScheduler]         = useState(_s.scheduler   || '')
  const [vaePath, setVaePath]             = useState(_s.vaePath     || '')
  const [clipSkip, setClipSkip]           = useState(_s.clipSkip    ?? 1)
  const [seamless, setSeamless]           = useState(_s.seamless    ?? false)
  const [outpaintPx, setOutpaintPx]       = useState(_s.outpaintPx  ?? 64)
  const [scannedVAEs, setScannedVAEs]     = useState([])
  // model comparison
  const [compareModel, setCompareModel]   = useState('')
  const [compareResult, setCompareResult] = useState(null)
  const [comparing, setComparing]         = useState(false)

  // queue
  const [queue, setQueue]               = useState([])
  const [queueOpen, setQueueOpen]       = useState(false)
  const queueRunning                    = useRef(false)

  // preset slots (A–E)
  const [presets, setPresets]           = useState(() => {
    try { return JSON.parse(localStorage.getItem('acs_presets') || '{}') } catch { return {} }
  })
  const [presetsOpen, setPresetsOpen]   = useState(false)

  // prompt history
  const [promptHistory, setPromptHistory] = useState(() => {
    try { return JSON.parse(localStorage.getItem('acs_prompt_hist') || '[]') } catch { return [] }
  })
  const [histIdx, setHistIdx]           = useState(-1)

  // post-process
  const [restoringFace, setRestoringFace]   = useState(false)
  const [interrogating, setInterrogating]   = useState(false)
  const [ppOpen, setPpOpen]                 = useState(false)

  // civitai browser
  const [civitaiOpen, setCivitaiOpen]       = useState(false)

  // LoRA tester
  const [loraTestOpen, setLoraTestOpen]     = useState(false)
  const [loraTestBusy, setLoraTestBusy]     = useState(false)
  const [loraTestResults, setLoraTestResults] = useState([])

  // latest run ref for keyboard shortcut
  const latestRun = useRef(null)

  // auto-save settings to localStorage (debounced 600ms)
  useEffect(() => {
    const t = setTimeout(() => {
      try {
        localStorage.setItem('acs_settings', JSON.stringify({
          mode, prompt, negative, w, h, steps, cfg, strength, seed,
          frames, fps, consistency, checkpoint, videoModel, manualCheckpoint,
          activeLoras, controlnet, cnStrength, upscaleFactor,
          hiresFix, hiresScale, hiresStrength, batchSize, useComfyUI,
          scheduler, vaePath, clipSkip, seamless, outpaintPx,
        }))
      } catch {}
    }, 600)
    return () => clearTimeout(t)
  }, [mode, prompt, negative, w, h, steps, cfg, strength, seed,
      frames, fps, consistency, checkpoint, videoModel, manualCheckpoint,
      activeLoras, controlnet, cnStrength, upscaleFactor,
      hiresFix, hiresScale, hiresStrength, batchSize, useComfyUI,
      scheduler, vaePath, clipSkip, seamless, outpaintPx])

  const isVideo    = mode === 't2v' || mode === 'i2v'
  const isUpscale  = mode === 'upscale'
  const isOutpaint = mode === 'outpaint'
  const needsRef   = mode === 'i2i' || mode === 'i2v' || mode === 'inpaint' || mode === 'upscale' || mode === 'outpaint'

  const tokenCount = useMemo(() => {
    const words = prompt.trim().split(/[\s,().:|;!\[\]{}]+/).filter(Boolean)
    return Math.min(Math.round(words.length * 1.3), 999)
  }, [prompt])

  const compareRun = async () => {
    if (!compareModel || !prompt.trim()) return toast('Need a prompt and second model', 'info')
    setComparing(true); setCompareResult(null)
    const base = {
      prompt, negative, mode: 't2i', width: w, height: h,
      steps, cfg: parseFloat(cfg), seed: parseInt(seed),
      loras: activeLoras, scheduler, vae_path: vaePath,
      clip_skip: clipSkip, seamless,
    }
    try {
      const r1 = await api.generate({ ...base, model: effectiveCheckpoint })
      if (r1.error) throw new Error(r1.error)
      const r2 = await api.generate({ ...base, model: compareModel })
      if (r2.error) throw new Error(r2.error)
      setCompareResult({
        a: r1.image, b: r2.image,
        labelA: effectiveCheckpoint.split(/[\\/]/).pop(),
        labelB: compareModel.split(/[\\/]/).pop(),
        seed: r1.seed,
      })
      toast('Comparison done ✓', 'ok')
    } catch (e) { toast(e.message, 'err') }
    setComparing(false)
  }
  const gen      = status?.gen_status === 'generating'
  const working  = busy || gen

  const loadModels = useCallback(async () => {
    try {
      const m = await api.models()
      const cps = m.checkpoints ?? []
      setScannedCheckpoints(cps)
      setScannedVideoModels(m.video ?? [])
      setScannedControlnets(m.controlnet ?? [])
      setScannedVAEs(m.vae ?? [])
      setScannedLoras(m.loras ?? {})
      if (cps.length > 0) setCheckpoint((prev) => prev || cps[0].path)
      const vids = m.video ?? []
      if (vids.length > 0) setVideoModel((prev) => prev || vids[0].path)
      const te  = (m.text_encoders ?? []).find((x) => /wan|umt5/i.test(x.name))
      const vae = (m.vae ?? []).find((x) => /wan/i.test(x.name))
      if (te || vae) setWanComponents({ te: te?.name ?? null, vae: vae?.name ?? null })
    } catch {}
  }, [])

  useEffect(() => { loadModels() }, [loadModels])

  useEffect(() => {
    if (!pendingRef) return
    setRefImage(pendingRef.image)
    setMode(pendingRef.mode)
    clearPendingRef()
  }, [pendingRef, clearPendingRef])

  // keep ref to run() so keyboard handler always has fresh closure
  useEffect(() => { latestRun.current = run })

  // keyboard shortcuts
  useEffect(() => {
    const onKey = (e) => {
      const inField = ['INPUT','TEXTAREA','SELECT'].includes(e.target.tagName)
      if (e.ctrlKey && e.key === 'Enter') { e.preventDefault(); latestRun.current?.(); return }
      if (inField) return
      if (e.key === 'r') setSeed(Math.floor(Math.random() * 2 ** 31))
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, []) // eslint-disable-line

  // paste image from clipboard
  useEffect(() => {
    const onPaste = (e) => {
      const item = [...(e.clipboardData?.items ?? [])].find((i) => i.type.startsWith('image/'))
      if (!item) return
      const file = item.getAsFile()
      if (!file) return
      fileToB64(file).then((b64) => {
        setRefImage(b64)
        if (mode === 't2i') setMode('i2i')
        toast('Image pasted from clipboard', 'ok')
      })
    }
    window.addEventListener('paste', onPaste)
    return () => window.removeEventListener('paste', onPaste)
  }, [mode, toast])

  const effectiveCheckpoint = manualCheckpoint.trim() || checkpoint

  const upload = (setter) => async (e) => {
    const f = e.target.files?.[0]; if (!f) return
    setter(await fileToB64(f)); e.target.value = ''
  }

  const enhance = async () => {
    if (!prompt.trim()) return toast('Write a prompt first', 'info')
    setEnhancing(true); setTips([])
    try {
      const r = await api.enhance({ prompt, style:'detailed', mode })
      if (r.positive) setPrompt(r.positive)
      if (r.negative) setNeg(r.negative)
      if (Array.isArray(r.tips)) setTips(r.tips)
      toast('Prompt enhanced ✓', 'ok')
    } catch (e) { toast(e.message, 'err') }
    finally { setEnhancing(false) }
  }

  const getSuggestions = async () => {
    if (!theme.trim()) return toast('Enter a theme first', 'info')
    setSuggesting(true); setSuggestions([])
    try {
      const r = await api.suggest({ theme, count:6, mode })
      setSuggestions(r.prompts ?? [])
    } catch (e) { toast(e.message, 'err') }
    finally { setSuggesting(false) }
  }

  const askAdvisor = async () => {
    if (!advisorGoal.trim()) return toast('Describe what you want to create first', 'info')
    setAdvisorBusy(true); setAdvisorResult(null)
    try {
      const r = await api.advisor({ goal: advisorGoal, mode })
      setAdvisorResult(r)
    } catch (e) { toast(e.message, 'err') }
    finally { setAdvisorBusy(false) }
  }

  const applyAdvisorSettings = () => {
    if (!advisorResult) return
    if (advisorResult.suggested_mode) setMode(advisorResult.suggested_mode)
    const s = advisorResult.settings ?? {}
    if (s.steps)    setSteps(s.steps)
    if (s.cfg)      setCfg(s.cfg)
    if (s.width)    setW(s.width)
    if (s.height)   setH(s.height)
    if (s.negative) setNeg(s.negative)
    if (advisorResult.suggested_model) setManualCheckpoint(advisorResult.suggested_model)
    toast('Settings applied ✓', 'ok')
  }

  const uploadCn = async (e) => {
    const f = e.target.files?.[0]; if (!f) return
    setCnImage(await fileToB64(f)); e.target.value = ''
  }

  const addLoraFromBrowse = (item) => {
    if (!activeLoras.find((l) => l.path === item.path))
      setActiveLoras((a) => [...a, { path: item.path, name: item.name, scale: 0.8 }])
    setBrowser(null)
  }

  const removeLora   = (path) => setActiveLoras((a) => a.filter((l) => l.path !== path))
  const setLoraScale = (path, v) =>
    setActiveLoras((a) => a.map((l) => l.path === path ? { ...l, scale: parseFloat(v) } : l))

  const addLoraFromDropdown = (e) => {
    const v = e.target.value; if (!v) return
    const [path, name] = v.split('||')
    if (!activeLoras.find((l) => l.path === path))
      setActiveLoras((a) => [...a, { path, name, scale: 0.8 }])
    e.target.value = ''
  }

  const saveTemplate = () => {
    if (!prompt.trim()) return toast('Write a prompt first', 'info')
    const t = { id: Date.now(), prompt: prompt.trim(), negative: negative.trim(), label: prompt.slice(0, 50) }
    const next = [t, ...templates].slice(0, 30)
    setTemplates(next)
    localStorage.setItem('acs_templates', JSON.stringify(next))
    toast('Template saved', 'ok')
  }

  const loadTemplate = (t) => {
    setPrompt(t.prompt)
    if (t.negative) setNeg(t.negative)
    setShowTemplates(false)
    toast('Template loaded', 'ok')
  }

  const delTemplate = (id) => {
    const next = templates.filter((t) => t.id !== id)
    setTemplates(next)
    localStorage.setItem('acs_templates', JSON.stringify(next))
  }

  const useResultAsRef = () => {
    if (!result?.image) return
    setRefImage(`data:image/png;base64,${result.image}`)
    if (mode === 't2i') setMode('i2i')
    toast('Result set as reference', 'ok')
  }

  const removeBg = async () => {
    if (!result?.image) return
    setRemovingBg(true)
    try {
      const r = await api.removeBg(result.image)
      if (r.error) { toast(r.error, 'err'); return }
      setResult((prev) => ({ ...prev, image: r.image }))
      toast('Background removed ✓', 'ok')
    } catch (e) { toast(e.message, 'err') }
    finally { setRemovingBg(false) }
  }

  const faceRestore = async () => {
    if (!result?.image) return
    setRestoringFace(true)
    try {
      const r = await api.faceRestore(result.image)
      if (r.error) { toast(r.error, 'err'); return }
      setResult((prev) => ({ ...prev, image: r.image }))
      toast('Face restored ✓', 'ok')
    } catch (e) { toast(e.message, 'err') }
    finally { setRestoringFace(false) }
  }

  const interrogate = async () => {
    if (!refImage) return toast('Upload a reference image first', 'info')
    setInterrogating(true)
    try {
      const r = await api.interrogate(refImage)
      if (r.error) { toast(r.error, 'err'); return }
      if (r.prompt) { setPrompt(r.prompt); toast('Prompt extracted ✓', 'ok') }
    } catch (e) { toast(e.message, 'err') }
    finally { setInterrogating(false) }
  }

  const pushHistory = (p) => {
    if (!p.trim()) return
    const next = [p, ...promptHistory.filter((x) => x !== p)].slice(0, 25)
    setPromptHistory(next)
    localStorage.setItem('acs_prompt_hist', JSON.stringify(next))
  }

  const savePreset = (slot) => {
    const data = {
      label: prompt.slice(0, 40) || `Preset ${slot}`,
      prompt, negative, mode, checkpoint, videoModel, manualCheckpoint,
      activeLoras, w, h, steps, cfg: parseFloat(cfg),
      strength: parseFloat(strength), seed: parseInt(seed),
      batchSize, hiresFix, hiresScale, hiresStrength,
    }
    const next = { ...presets, [slot]: data }
    setPresets(next)
    localStorage.setItem('acs_presets', JSON.stringify(next))
    toast(`Saved to slot ${slot}`, 'ok')
  }

  const loadPreset = (slot) => {
    const p = presets[slot]; if (!p) return toast('Empty slot', 'info')
    setPrompt(p.prompt ?? '')
    setNeg(p.negative ?? '')
    if (p.mode) setMode(p.mode)
    if (p.checkpoint) setCheckpoint(p.checkpoint)
    if (p.videoModel) setVideoModel(p.videoModel)
    if (p.manualCheckpoint) setManualCheckpoint(p.manualCheckpoint)
    if (Array.isArray(p.activeLoras)) setActiveLoras(p.activeLoras)
    if (p.w) setW(p.w); if (p.h) setH(p.h)
    if (p.steps) setSteps(p.steps)
    if (p.cfg) setCfg(p.cfg)
    if (p.batchSize) setBatchSize(p.batchSize)
    if (p.hiresFix != null) setHiresFix(p.hiresFix)
    toast(`Loaded slot ${slot}`, 'ok')
  }

  const addToQueue = () => {
    if (!prompt.trim()) return toast('Write a prompt first', 'info')
    const job = {
      id: Date.now(), label: prompt.slice(0, 50),
      prompt, negative, mode, model: isVideo ? '' : effectiveCheckpoint,
      video_model: isVideo ? videoModel : null,
      width: w, height: h, steps, cfg: parseFloat(cfg),
      strength: parseFloat(strength), seed: parseInt(seed),
      ref_image: refImage, mask_image: maskImage, loras: activeLoras,
      controlnet: controlnet || null, controlnet_image: cnImage || null,
      controlnet_strength: parseFloat(cnStrength), upscale_factor: upscaleFactor,
      hires_fix: hiresFix, hires_scale: hiresScale, hires_strength: hiresStrength,
      status: 'pending', result: null,
    }
    setQueue((q) => [...q, job])
    setQueueOpen(true)
    toast('Added to queue', 'ok')
  }

  const runQueue = async () => {
    if (queueRunning.current) return
    queueRunning.current = true
    const pending = queue.filter((j) => j.status === 'pending')
    for (const job of pending) {
      setQueue((q) => q.map((j) => j.id === job.id ? { ...j, status: 'running' } : j))
      try {
        const r = await api.generate(job)
        if (r.error) throw new Error(r.error)
        setQueue((q) => q.map((j) => j.id === job.id ? { ...j, status: 'done', result: r } : j))
        setResult(r)
      } catch (e) {
        setQueue((q) => q.map((j) => j.id === job.id ? { ...j, status: 'error', error: e.message } : j))
      }
    }
    queueRunning.current = false
    toast('Queue finished', 'ok')
  }

  const runLoraTest = async () => {
    if (!prompt.trim()) return toast('Write a prompt first', 'info')
    if (activeLoras.length === 0) return toast('Add a LoRA first', 'info')
    setLoraTestBusy(true); setLoraTestResults([]); setLoraTestOpen(true)
    const testSeed = parseInt(seed) >= 0 ? parseInt(seed) : Math.floor(Math.random() * 2**31)
    const testScales = [0.2, 0.5, 0.8, 1.0]
    const results = []
    for (const scale of testScales) {
      const testLoras = activeLoras.map((l, i) => i === 0 ? { ...l, scale } : l)
      try {
        const r = await api.generate({
          prompt, negative, mode: 't2i',
          model: effectiveCheckpoint, width: w, height: h,
          steps, cfg: parseFloat(cfg), seed: testSeed,
          loras: testLoras, consistency_mode: 'none',
        })
        results.push({ scale, result: r.error ? null : r, error: r.error || null })
      } catch (e) {
        results.push({ scale, result: null, error: e.message })
      }
      setLoraTestResults([...results])
    }
    setLoraTestBusy(false)
  }

  const run = async () => {
    if (!prompt.trim()) return toast('Write a prompt first', 'info')
    if (needsRef && !refImage) return toast('This mode needs a reference image', 'info')
    if (mode === 'inpaint' && !maskImage) return toast('Paint a mask on the image first', 'info')
    setBusy(true); setResult(null); setBatchResults([]); setCompareMode(false)
    pushHistory(prompt)

    if (useComfyUI) {
      if (!effectiveCheckpoint) return (setBusy(false), toast('Select a checkpoint for ComfyUI generation', 'info'))
      try {
        const r = await api.comfyuiGenerate({
          prompt, negative, model: effectiveCheckpoint,
          width: w, height: h, steps, cfg: parseFloat(cfg), seed: parseInt(seed),
        })
        if (r.error) { toast(r.error, 'err'); return }
        setResult(r); toast('ComfyUI done ✓', 'ok')
      } catch (e) { toast(e.message, 'err') }
      finally { setBusy(false) }
      return
    }

    try {
      const payload = {
        prompt, negative, mode,
        model: isVideo ? '' : effectiveCheckpoint,
        video_model: isVideo ? videoModel : null,
        width: w, height: h, steps,
        cfg: parseFloat(cfg), strength: parseFloat(strength), seed: parseInt(seed),
        consistency_mode: consistency, num_frames: frames, fps,
        ref_image: refImage, mask_image: maskImage, loras: activeLoras,
        controlnet: controlnet || null, controlnet_image: cnImage || null,
        controlnet_strength: parseFloat(cnStrength),
        upscale_factor: upscaleFactor,
        hires_fix: hiresFix, hires_scale: hiresScale, hires_strength: hiresStrength,
        scheduler, vae_path: vaePath, clip_skip: clipSkip,
        seamless, outpaint_px: outpaintPx,
      }
      if (batchSize > 1) {
        const results = []
        for (let i = 0; i < batchSize; i++) {
          const s = parseInt(seed) === -1 ? -1 : parseInt(seed) + i
          const r = await api.generate({ ...payload, seed: s })
          if (r.error) { toast(r.error, 'err'); break }
          results.push(r)
          setBatchResults([...results])
          if (i === 0) setResult(r)
        }
        toast(`Batch done: ${results.length}/${batchSize} ✓`, 'ok')
      } else {
        const r = await api.generate(payload)
        if (r.error) { toast(r.error, 'err'); return }
        setResult(r); toast('Done ✓', 'ok')
      }
    } catch (e) { toast(e.message, 'err') }
    finally { setBusy(false) }
  }

  const resultUrl = result?.image
    ? `data:image/png;base64,${result.image}`
    : result?.video ? `data:video/mp4;base64,${result.video}` : null

  const loraGroups = Object.entries(scannedLoras)
  const pct = Math.max(status?.gen_progress ?? 0, busy ? 2 : 0)
  const timerFmt = `${Math.floor(elapsed/60).toString().padStart(2,'0')}:${(elapsed%60).toString().padStart(2,'0')}`

  return (
    <div className="page">
      {browser === 'checkpoint' && (
        <FileBrowser title="Select Checkpoint" exts={MODEL_EXTS}
          onSelect={(item) => { setManualCheckpoint(item.path); setBrowser(null); toast(`Checkpoint: ${item.name}`, 'ok') }}
          onClose={() => setBrowser(null)}/>
      )}
      {browser === 'lora' && (
        <FileBrowser title="Select LoRA" exts={LORA_EXTS}
          onSelect={addLoraFromBrowse} onClose={() => setBrowser(null)}/>
      )}
      {civitaiOpen && (
        <CivitaiBrowser
          toast={toast}
          onClose={() => setCivitaiOpen(false)}
          onDownloadStart={() => { setCivitaiOpen(false) }}
        />
      )}

      <div className="page-narrow">

        {/* ── mode selector ── */}
        <div className="gen-modes">
          {MODES.map(({ id, label, short, Icon }) => (
            <button key={id}
              className={'gen-mode-btn' + (mode === id ? ' active' : '')}
              onClick={() => { setMode(id); setResult(null) }}>
              <Icon size={15}/>
              <span className="gen-mode-label">{label}</span>
              <span className="gen-mode-short">{short}</span>
            </button>
          ))}
        </div>

        <div className="gen-layout">

          {/* ── canvas (right column via CSS order:2) ── */}
          <div className="canvas-wrap">
            <div className={'canvas-stage' + (working ? ' working' : '')}>
              {working ? (
                <div className="gen-progress-overlay">
                  <div className="gen-progress-ring">
                    <svg viewBox="0 0 80 80">
                      <circle cx="40" cy="40" r="34" className="ring-bg"/>
                      <circle cx="40" cy="40" r="34" className="ring-fill"
                        style={{ strokeDashoffset: 214 - (214 * pct) / 100 }}/>
                    </svg>
                    <span className="ring-pct">{pct}%</span>
                  </div>
                  <div className="gen-progress-log">{status?.gen_log ?? 'Generating…'}</div>
                  <div className="gen-progress-timer">⏱ {timerFmt}</div>
                </div>
              ) : resultUrl ? (
                compareMode && refImage && result?.image
                  ? <BeforeAfterSlider before={refImage} after={resultUrl}/>
                  : result?.video
                    ? <video src={resultUrl} controls autoPlay loop/>
                    : <img src={resultUrl} alt="result"/>
              ) : (
                <div className="canvas-empty">
                  <span className="big-icon">✦</span>
                  <div className="canvas-empty-label">Your creation appears here</div>
                </div>
              )}
            </div>

            {working && (
              <div className="progress-bar">
                <div className="progress-fill" style={{ width:`${Math.max(pct, 4)}%` }}/>
              </div>
            )}

            {result && !working && (
              <div className="result-actions">
                <a className="btn btn-primary" href={resultUrl} download={result.filename}>
                  <DlIcon size={14}/> Save
                </a>
                {result?.image && (
                  <button className="btn" onClick={useResultAsRef} title="Use as reference for I2I">
                    <ArrowRight size={13}/> Use as ref
                  </button>
                )}
                {result?.image && refImage && (
                  <button className={'btn' + (compareMode ? ' btn-primary' : '')}
                    onClick={() => setCompareMode((v) => !v)} title="Before/after compare">
                    <ArrowUpDown size={13}/> Compare
                  </button>
                )}
                {result?.image && (
                  <button className="btn" onClick={faceRestore} disabled={restoringFace} title="Restore faces (GFPGAN)">
                    {restoringFace ? <span className="spinner"/> : <Star size={13}/>} Fix faces
                  </button>
                )}
                {result?.image && (
                  <button className="btn" onClick={removeBg} disabled={removingBg} title="Remove background (rembg)">
                    {removingBg ? <span className="spinner"/> : <Scissors size={13}/>} Remove BG
                  </button>
                )}
                <span className="chip amber">seed {result.seed}</span>
                <span className="chip">{result.mode?.toUpperCase()}</span>
              </div>
            )}

            {/* batch grid */}
            {batchResults.length > 1 && !working && (
              <div className="batch-grid">
                {batchResults.map((r, i) => (
                  <div key={i} className={'batch-thumb' + (result === r ? ' active' : '')}
                    onClick={() => setResult(r)}>
                    <img src={`data:image/png;base64,${r.image}`} alt={`batch ${i+1}`}/>
                    <span className="batch-num">#{i+1}</span>
                  </div>
                ))}
              </div>
            )}

            {/* Model compare result */}
            {compareResult && (
              <div className="panel">
                <div className="panel-title" style={{ display:'flex', alignItems:'center', justifyContent:'space-between' }}>
                  <span><ArrowUpDown size={11}/> Model comparison · seed {compareResult.seed}</span>
                  <button className="btn-ghost btn-icon" onClick={() => setCompareResult(null)}><X size={12}/></button>
                </div>
                <div className="compare-result-grid">
                  <div className="compare-result-col">
                    <img src={`data:image/png;base64,${compareResult.a}`} alt="Model A"/>
                    <div className="compare-label" title={compareResult.labelA}>{compareResult.labelA}</div>
                  </div>
                  <div className="compare-result-col">
                    <img src={`data:image/png;base64,${compareResult.b}`} alt="Model B"/>
                    <div className="compare-label" title={compareResult.labelB}>{compareResult.labelB}</div>
                  </div>
                </div>
              </div>
            )}

            {tips.length > 0 && (
              <div className="panel">
                <div className="panel-title">Enhancement tips</div>
                {tips.map((t, i) => (
                  <div key={i} className="tip-row"><Lightbulb className="tip-ic" size={13}/>{t}</div>
                ))}
              </div>
            )}

            {/* Post-process panel */}
            {result?.image && !working && (
              <div className="panel">
                <button className="gen-advisor-hd" onClick={() => setPpOpen(v => !v)}>
                  <Sliders size={13} style={{ color:'var(--violet)' }}/>
                  <span>Post-process</span>
                  {ppOpen ? <ChevronUp size={12}/> : <ChevronDown size={12}/>}
                </button>
                {ppOpen && (
                  <PostProcess
                    imageB64={result.image}
                    onUpdate={(b64) => setResult(prev => ({ ...prev, image: b64 }))}
                  />
                )}
              </div>
            )}

            {/* LoRA tester grid */}
            {loraTestOpen && (
              <div className="panel">
                <div className="panel-header-row">
                  <div className="panel-title" style={{margin:0}}>LoRA strength test</div>
                  <button className="btn-ghost btn-icon" onClick={() => setLoraTestOpen(false)}><X size={13}/></button>
                </div>
                <div className="lora-test-grid">
                  {[0.2, 0.5, 0.8, 1.0].map((scale, i) => {
                    const entry = loraTestResults[i]
                    return (
                      <div key={scale} className={'lora-test-cell' + (entry?.result ? ' clickable' : '')}
                        onClick={() => { if (entry?.result) { setResult(entry.result); setLoraScale(activeLoras[0].path, scale) }}}>
                        {entry?.result?.image
                          ? <img src={`data:image/png;base64,${entry.result.image}`} alt={`${scale}`}/>
                          : entry?.error
                            ? <div className="lora-test-err">Error</div>
                            : <div className="lora-test-placeholder">
                                {loraTestBusy && i === loraTestResults.length ? <span className="spinner"/> : null}
                              </div>}
                        <span className="lora-test-label">{scale.toFixed(1)}</span>
                      </div>
                    )
                  })}
                </div>
                {!loraTestBusy && loraTestResults.length === 4 && (
                  <div className="gen-hint" style={{marginTop:6}}>Click any to use that strength + set as result</div>
                )}
              </div>
            )}
          </div>

          {/* ── controls (left column via CSS order:1) ── */}
          <div className="gen-controls">

            {/* upscale panel — replaces prompt for upscale mode */}
            {isUpscale && (
              <div className="panel">
                <div className="panel-title">Upscale settings</div>
                <div className="params-grid">
                  {[2,4,6,8].map((f) => (
                    <button key={f}
                      className={'ratio-btn' + (upscaleFactor === f ? ' active' : '')}
                      onClick={() => setUpscaleFactor(f)}>
                      <span style={{ fontSize:18, fontWeight:700 }}>{f}×</span>
                      <span style={{ fontSize:10 }}>{f}× size</span>
                    </button>
                  ))}
                </div>
                <div className="gen-hint" style={{ marginTop:10 }}>
                  Uses Real-ESRGAN if installed, otherwise high-quality resize.
                  Drop your image in the Reference panel below.
                </div>
              </div>
            )}

            {/* prompt */}
            {!isUpscale && <div className="panel">
              <div className="panel-header-row">
                <div className="panel-title" style={{margin:0}}>Prompt</div>
                <div style={{display:'flex',gap:4}}>
                  <button className="btn-ghost btn-icon" title="Save as template" onClick={saveTemplate}>
                    <Bookmark size={13}/>
                  </button>
                  {templates.length > 0 && (
                    <button className="btn-ghost btn-icon" title="Load template"
                      onClick={() => setShowTemplates((v) => !v)}>
                      <LayoutGrid size={13}/>
                    </button>
                  )}
                </div>
              </div>
              {showTemplates && templates.length > 0 && (
                <div className="templates-list">
                  {templates.map((t) => (
                    <div key={t.id} className="template-item">
                      <button className="template-text" onClick={() => loadTemplate(t)}>{t.label}</button>
                      <button className="btn-ghost btn-icon" onClick={() => delTemplate(t.id)}><X size={11}/></button>
                    </div>
                  ))}
                </div>
              )}
              <textarea className="textarea gen-textarea" value={prompt}
                onChange={(e) => { setPrompt(e.target.value); setHistIdx(-1) }}
                placeholder="Describe what you want to create… (↑/↓ for history)"
                onKeyDown={(e) => {
                  if (e.key === 'ArrowUp' && !e.shiftKey && prompt === '') {
                    e.preventDefault()
                    const idx = Math.min(histIdx + 1, promptHistory.length - 1)
                    setHistIdx(idx); setPrompt(promptHistory[idx] || '')
                  }
                  if (e.key === 'ArrowDown' && histIdx >= 0) {
                    e.preventDefault()
                    const idx = histIdx - 1
                    setHistIdx(idx); setPrompt(idx >= 0 ? promptHistory[idx] : '')
                  }
                }}/>
              <div className={`token-counter ${tokenCount > 77 ? 'tok-red' : tokenCount > 60 ? 'tok-yellow' : 'tok-green'}`}>
                ~{tokenCount} / 77 tokens
              </div>
              <div className="gen-neg-row">
                <textarea className="textarea gen-neg" value={negative}
                  onChange={(e) => setNeg(e.target.value)}
                  placeholder="Negative: bad quality, deformed…"/>
                <div className="neg-presets">
                  {NEG_PRESETS.map((p) => (
                    <button key={p} className="neg-preset-chip"
                      onClick={() => setNeg((n) => n ? `${n}, ${p}` : p)}>{p}</button>
                  ))}
                </div>
              </div>
              <div className="gen-btn-row">
                <button className="gen-action-btn cyan" onClick={enhance} disabled={enhancing}>
                  {enhancing ? <span className="spinner"/> : <Wand2 size={13}/>} Enhance
                </button>
                <button className="gen-action-btn" onClick={() => { if(!theme.trim()) toast('Enter a theme below first','info'); else getSuggestions() }} disabled={suggesting}>
                  {suggesting ? <span className="spinner"/> : <LayoutGrid size={13}/>} Ideas
                </button>
              </div>
              <div className="gen-theme-row">
                <input className="input" placeholder="Theme for ideas (e.g. fantasy portrait)…"
                  value={theme} onChange={(e) => setTheme(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && getSuggestions()}/>
              </div>
              {suggestions.length > 0 && (
                <div className="suggestions">
                  {suggestions.map((s, i) => (
                    <button key={i} className="suggestion-item" onClick={() => setPrompt(s)}>{s}</button>
                  ))}
                </div>
              )}
            </div>}

            {/* model */}
            {!isUpscale && <div className="panel">
              {isVideo ? (
                <>
                  <div className="panel-title"><Film size={11}/> Video model</div>
                  {scannedVideoModels.length > 0 ? (
                    <select className="select" value={videoModel} onChange={(e) => setVideoModel(e.target.value)}>
                      <option value="">— pick Wan / LTX model —</option>
                      {scannedVideoModels.map((m) => (
                        <option key={m.path} value={m.path}>
                          {m.name} ({m.size_gb ?? '?'}GB){m.name.endsWith('.gguf') ? ' [GGUF]' : ''}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <div className="gen-hint">No video models in <kbd>models/video/</kbd></div>
                  )}
                  {wanComponents && videoModel && !videoModel.endsWith('.gguf') && (
                    <div className="gen-hint" style={{ marginTop:6 }}>
                      Encoder: {wanComponents.te ?? 'auto'} · VAE: {wanComponents.vae ?? 'auto'}
                    </div>
                  )}
                </>
              ) : (
                <>
                  <div className="panel-title"><Cpu size={11}/> Checkpoint</div>
                  <div className="gen-model-row">
                    <select className="select" value={checkpoint}
                      onChange={(e) => { setCheckpoint(e.target.value); setManualCheckpoint('') }}>
                      <option value="">— scanned checkpoints —</option>
                      {scannedCheckpoints.map((c) => (
                        <option key={c.path} value={c.path}>{c.name} ({c.size_gb ?? '?'}GB)</option>
                      ))}
                    </select>
                    <button className="btn btn-icon" title="Browse local files" onClick={() => setBrowser('checkpoint')}>
                      <FolderOpen size={14}/>
                    </button>
                    <button className="btn btn-icon" title="Browse CivitAI" onClick={() => setCivitaiOpen(true)}
                      style={{ color:'var(--amber-bright)' }}>
                      <Search size={14}/>
                    </button>
                  </div>
                  {manualCheckpoint && (
                    <div className="gen-hint">↳ {manualCheckpoint}</div>
                  )}

                  {/* Model comparison */}
                  {!isVideo && (
                    <div className="compare-picker" style={{ marginTop:8 }}>
                      <div className="panel-title" style={{ marginBottom:4 }}>
                        <ArrowUpDown size={11}/> Compare with…
                      </div>
                      <div className="gen-model-row">
                        <select className="select" value={compareModel}
                          onChange={(e) => setCompareModel(e.target.value)} style={{ flex:1 }}>
                          <option value="">— second model —</option>
                          {scannedCheckpoints.map((c) => (
                            <option key={c.path} value={c.path}>{c.name}</option>
                          ))}
                        </select>
                        <button className="btn" onClick={compareRun}
                          disabled={comparing || !compareModel || !prompt.trim()}
                          style={{ whiteSpace:'nowrap', fontSize:12, padding:'0 10px' }}>
                          {comparing ? <span className="spinner"/> : <ArrowUpDown size={11}/>}
                          {comparing ? ' Running…' : ' Compare'}
                        </button>
                      </div>
                    </div>
                  )}
                </>
              )}

              {!isVideo && (
                <>
                  <div className="gen-divider"/>
                  <div className="panel-title">LoRA adapters</div>
                  <div className="gen-model-row">
                    {loraGroups.length > 0 && (
                      <select className="select" onChange={addLoraFromDropdown} style={{ flex:1 }}>
                        <option value="">+ Add LoRA</option>
                        {loraGroups.map(([grp, items]) => (
                          <optgroup key={grp} label={grp}>
                            {items.map((l) => (
                              <option key={l.path} value={`${l.path}||${l.name}`}>
                                {l.name} ({l.size_mb}MB)
                              </option>
                            ))}
                          </optgroup>
                        ))}
                      </select>
                    )}
                    <button className="btn btn-icon" onClick={() => setBrowser('lora')} title="Browse local LoRAs">
                      <FolderOpen size={14}/>
                    </button>
                    <button className="btn btn-icon" title="Browse CivitAI LoRAs"
                      style={{ color:'var(--amber-bright)' }}
                      onClick={() => setCivitaiOpen(true)}>
                      <Search size={14}/>
                    </button>
                  </div>
                  {activeLoras.map((l) => (
                    <div key={l.path} className="lora-item">
                      <span className="lora-name" title={l.path}>{l.name}</span>
                      <div className="lora-strength">
                        <input className="range" type="range" min="0" max="2" step="0.05"
                          value={l.scale} onChange={(e) => setLoraScale(l.path, e.target.value)}/>
                        <span className="range-val lora-scale-val">{parseFloat(l.scale).toFixed(2)}</span>
                      </div>
                      <button className="btn-ghost btn-icon" onClick={() => removeLora(l.path)}><X size={12}/></button>
                    </div>
                  ))}
                  {activeLoras.length > 0 && prompt.trim() && (
                    <button className="btn btn-sm btn-full" style={{ marginTop:6 }}
                      onClick={runLoraTest} disabled={loraTestBusy || working}>
                      {loraTestBusy
                        ? <><span className="spinner"/> Testing strengths…</>
                        : <><Sliders size={12}/> Test LoRA strengths (0.2 / 0.5 / 0.8 / 1.0)</>}
                    </button>
                  )}
                </>
              )}
            </div>}

            {/* ControlNet */}
            {!isVideo && !isUpscale && scannedControlnets.length > 0 && (
              <div className="panel">
                <div className="panel-title">ControlNet</div>
                <select className="select" value={controlnet}
                  onChange={(e) => { setControlnet(e.target.value); setCnImage(null) }}>
                  <option value="">— none —</option>
                  {scannedControlnets.map((c) => (
                    <option key={c.path} value={c.path}>{c.name}</option>
                  ))}
                </select>
                {controlnet && (
                  <>
                    {cnImage ? (
                      <div className="thumb-preview" style={{ marginTop:8 }}>
                        <img src={cnImage} alt="cn"/>
                        <button className="thumb-rm" onClick={() => setCnImage(null)}><X size={13}/></button>
                      </div>
                    ) : (
                      <div className="upload-zone" style={{ marginTop:8 }}
                        onClick={() => document.getElementById('_cn').click()}>
                        <ImagePlus size={15}/> Upload guidance image
                      </div>
                    )}
                    <input id="_cn" type="file" accept="image/*" hidden onChange={uploadCn}/>
                    <div className="range-row" style={{ marginTop:8 }}>
                      <label style={{ margin:0 }}>Strength</label>
                      <span className="range-val">{cnStrength}</span>
                    </div>
                    <input className="range" type="range" min="0" max="2" step="0.05"
                      value={cnStrength} onChange={(e) => setCnStrength(e.target.value)}/>
                  </>
                )}
              </div>
            )}

            {/* reference image */}
            {needsRef && (
              <div className="panel">
                <div className="panel-header-row">
                  <div className="panel-title" style={{margin:0}}>{isUpscale ? 'Image to upscale' : 'Reference image'}</div>
                  {refImage && mode !== 'upscale' && (
                    <button className="btn-ghost btn-icon" onClick={interrogate} disabled={interrogating}
                      title="Extract prompt from this image (Ollama vision)">
                      {interrogating ? <span className="spinner"/> : <ScanSearch size={13}/>}
                    </button>
                  )}
                </div>
                {refImage ? (
                  <div className="thumb-preview"
                    onDragOver={(e) => e.preventDefault()}
                    onDrop={(e) => { e.preventDefault(); const f = e.dataTransfer.files[0]; f && fileToB64(f).then(setRefImage) }}>
                    <img src={refImage} alt="ref"/>
                    <button className="thumb-rm" onClick={() => setRefImage(null)}><X size={13}/></button>
                  </div>
                ) : (
                  <div className="upload-zone"
                    onClick={() => document.getElementById('_ref').click()}
                    onDragOver={(e) => e.preventDefault()}
                    onDrop={(e) => { e.preventDefault(); const f = e.dataTransfer.files[0]; f && fileToB64(f).then(setRefImage) }}>
                    <ImagePlus size={16}/> Click or drop image · Ctrl+V to paste
                  </div>
                )}
                <input id="_ref" type="file" accept="image/*" hidden onChange={upload(setRefImage)}/>
                {isOutpaint && (
                  <div style={{ marginTop:10 }}>
                    <div className="range-row">
                      <label style={{ margin:0 }}>Expand by</label>
                      <span className="range-val">{outpaintPx}px</span>
                    </div>
                    <input className="range" type="range" min="32" max="256" step="32"
                      value={outpaintPx} onChange={(e) => setOutpaintPx(parseInt(e.target.value))}/>
                    <div style={{ fontSize:11, opacity:.6, marginTop:4 }}>
                      Each edge will be extended by this many pixels using outpainting.
                    </div>
                  </div>
                )}
                {mode === 'inpaint' && refImage && (
                  <>
                    <div className="gen-divider"/>
                    <div className="panel-title" style={{display:'flex',alignItems:'center',justifyContent:'space-between'}}>
                      <span>Paint mask <span style={{fontWeight:400,opacity:.6,fontSize:11}}>(white = repaint)</span></span>
                      {maskImage && (
                        <button className="btn-ghost" style={{fontSize:11,padding:'2px 6px'}}
                          onClick={() => setMaskImage(null)}>
                          <Eraser size={11}/> Clear
                        </button>
                      )}
                    </div>
                    <InpaintBrush image={refImage} onMask={setMaskImage}/>
                  </>
                )}
              </div>
            )}

            {/* parameters */}
            <div className="panel">
              {!isVideo && (
                <>
                  <div className="panel-title">Aspect ratio</div>
                  <div className="ratio-grid">
                    {RATIOS.map((r) => (
                      <button key={r.label}
                        className={'ratio-btn' + (w === r.w && h === r.h ? ' active' : '')}
                        onClick={() => { setW(r.w); setH(r.h) }}
                        title={`${r.w}×${r.h}`}>
                        <div className="ratio-shape"
                          style={{
                            width: Math.round(22 * r.shape[0] / Math.max(...r.shape)),
                            height: Math.round(22 * r.shape[1] / Math.max(...r.shape))
                          }}/>
                        <span>{r.sub}</span>
                        <span className="ratio-lbl">{r.label}</span>
                      </button>
                    ))}
                  </div>
                  <div className="gen-divider"/>
                </>
              )}

              <div className="panel-title">Parameters</div>
              <div className="params-grid">
                <div className="param-item">
                  <div className="range-row">
                    <label>Steps</label><span className="range-val">{steps}</span>
                  </div>
                  <input className="range" type="range" min="1" max="50" value={steps}
                    onChange={(e) => setSteps(+e.target.value)}/>
                </div>
                <div className="param-item">
                  <div className="range-row">
                    <label>CFG</label><span className="range-val">{cfg}</span>
                  </div>
                  <input className="range" type="range" min="1" max="20" step="0.5" value={cfg}
                    onChange={(e) => setCfg(e.target.value)}/>
                </div>
              </div>

              <button className="gen-advanced-toggle" onClick={() => setAdvancedOpen((v) => !v)}>
                <SlidersHorizontal size={11}/>
                Advanced
                {advancedOpen ? <ChevronUp size={11}/> : <ChevronDown size={11}/>}
              </button>

              {advancedOpen && (
                <div className="params-grid" style={{ marginTop:8 }}>
                  {mode === 'i2i' && (
                    <div className="param-item" style={{ gridColumn:'1/-1' }}>
                      <div className="range-row"><label>Strength</label><span className="range-val">{strength}</span></div>
                      <input className="range" type="range" min="0.1" max="1" step="0.05" value={strength}
                        onChange={(e) => setStrength(e.target.value)}/>
                    </div>
                  )}
                  {isVideo && (
                    <>
                      <div className="param-item">
                        <div className="range-row"><label>Frames</label><span className="range-val">{frames}</span></div>
                        <input className="range" type="range" min="9" max="65" value={frames}
                          onChange={(e) => setFrames(+e.target.value)}/>
                      </div>
                      <div className="param-item">
                        <div className="range-row"><label>FPS</label><span className="range-val">{fps}</span></div>
                        <input className="range" type="range" min="4" max="30" value={fps}
                          onChange={(e) => setFps(+e.target.value)}/>
                      </div>
                    </>
                  )}
                  <div className="param-item" style={{ gridColumn:'1/-1' }}>
                    <div className="range-row">
                      <label>Seed</label>
                      <span className="range-val">{seed === -1 ? 'random' : seed}</span>
                    </div>
                    <div style={{ display:'flex', gap:6 }}>
                      <input className="range" type="range" min="-1" max="999999999" value={seed}
                        style={{ flex:1 }} onChange={(e) => setSeed(+e.target.value)}/>
                      <button className="btn btn-icon btn-sm" title="Randomise (R)"
                        onClick={() => setSeed(-1)}><Shuffle size={13}/></button>
                    </div>
                  </div>

                  {/* Scheduler */}
                  {!isVideo && !isUpscale && (
                    <div className="param-item" style={{ gridColumn:'1/-1' }}>
                      <label>Scheduler</label>
                      <select className="select" value={scheduler} onChange={(e) => setScheduler(e.target.value)}>
                        {SCHEDULERS.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
                      </select>
                    </div>
                  )}

                  {/* VAE */}
                  {!isVideo && !isUpscale && (
                    <div className="param-item" style={{ gridColumn:'1/-1' }}>
                      <label>VAE override</label>
                      <select className="select" value={vaePath} onChange={(e) => setVaePath(e.target.value)}>
                        <option value="">— model default —</option>
                        {scannedVAEs.map((v) => <option key={v.path} value={v.path}>{v.name}</option>)}
                      </select>
                    </div>
                  )}

                  {/* CLIP Skip */}
                  {!isVideo && !isUpscale && (
                    <div className="param-item">
                      <div className="range-row"><label>CLIP skip</label><span className="range-val">{clipSkip}</span></div>
                      <input className="range" type="range" min="1" max="4" step="1"
                        value={clipSkip} onChange={(e) => setClipSkip(parseInt(e.target.value))}/>
                    </div>
                  )}

                  {/* Seamless / tile */}
                  {!isVideo && !isUpscale && (
                    <div className="param-item">
                      <div className="range-row">
                        <label>Seamless tile</label>
                        <label style={{ cursor:'pointer', display:'flex', alignItems:'center', gap:6 }}>
                          <input type="checkbox" checked={seamless} onChange={(e) => setSeamless(e.target.checked)}/>
                          <span style={{ fontSize:12 }}>{seamless ? 'on' : 'off'}</span>
                        </label>
                      </div>
                    </div>
                  )}

                  {/* Hires fix */}
                  {!isVideo && !isUpscale && (
                    <div className="param-item" style={{ gridColumn:'1/-1' }}>
                      <div className="range-row">
                        <label>Hires fix</label>
                        <label style={{ cursor:'pointer', display:'flex', alignItems:'center', gap:6 }}>
                          <input type="checkbox" checked={hiresFix} onChange={(e) => setHiresFix(e.target.checked)}/>
                          <span style={{ fontSize:12 }}>{hiresFix ? `${hiresScale}× @ str ${hiresStrength}` : 'off'}</span>
                        </label>
                      </div>
                      {hiresFix && (
                        <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:8, marginTop:4 }}>
                          <div>
                            <div className="range-row"><label style={{fontSize:11}}>Scale</label><span className="range-val">{hiresScale}×</span></div>
                            <input className="range" type="range" min="1.1" max="3" step="0.1" value={hiresScale}
                              onChange={(e) => setHiresScale(parseFloat(e.target.value))}/>
                          </div>
                          <div>
                            <div className="range-row"><label style={{fontSize:11}}>Strength</label><span className="range-val">{hiresStrength}</span></div>
                            <input className="range" type="range" min="0.1" max="0.9" step="0.05" value={hiresStrength}
                              onChange={(e) => setHiresStrength(parseFloat(e.target.value))}/>
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Preset slots */}
            <div className="panel">
              <button className="gen-advisor-hd" onClick={() => setPresetsOpen((v) => !v)}>
                <Save size={13} style={{ color:'var(--cyan)' }}/>
                <span>Preset slots</span>
                {presetsOpen ? <ChevronUp size={12}/> : <ChevronDown size={12}/>}
              </button>
              {presetsOpen && (
                <div className="presets-grid">
                  {['A','B','C','D','E'].map((slot) => (
                    <div key={slot} className="preset-slot">
                      <div className="preset-slot-label">{slot}</div>
                      {presets[slot]
                        ? <button className="preset-load" onClick={() => loadPreset(slot)} title={presets[slot].label}>
                            {presets[slot].label}
                          </button>
                        : <span className="preset-empty">empty</span>}
                      <div className="preset-actions">
                        <button className="btn-ghost btn-icon" title="Save current settings to slot" onClick={() => savePreset(slot)}>
                          <Save size={10}/>
                        </button>
                        {presets[slot] && (
                          <button className="btn-ghost btn-icon" title="Clear slot"
                            onClick={() => { const n={...presets}; delete n[slot]; setPresets(n); localStorage.setItem('acs_presets',JSON.stringify(n)) }}>
                            <X size={10}/>
                          </button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Generation queue */}
            <div className="panel">
              <button className="gen-advisor-hd" onClick={() => setQueueOpen((v) => !v)}>
                <ListOrdered size={13} style={{ color:'var(--violet)' }}/>
                <span>Queue {queue.length > 0 ? `(${queue.filter(j=>j.status==='pending').length} pending)` : ''}</span>
                {queueOpen ? <ChevronUp size={12}/> : <ChevronDown size={12}/>}
              </button>
              {queueOpen && (
                <div style={{ marginTop:8 }}>
                  <div style={{ display:'flex', gap:6, marginBottom:8 }}>
                    <button className="btn btn-sm btn-cyan" style={{ flex:1 }} onClick={addToQueue}>
                      <ListOrdered size={12}/> Add current
                    </button>
                    <button className="btn btn-sm btn-primary" style={{ flex:1 }}
                      onClick={runQueue} disabled={!queue.some(j=>j.status==='pending')}>
                      <Zap size={12}/> Run queue
                    </button>
                    <button className="btn btn-sm" onClick={() => setQueue([])}>Clear</button>
                  </div>
                  {queue.length === 0
                    ? <div className="gen-hint">No jobs queued. Add the current settings as a job.</div>
                    : queue.map((job) => (
                      <div key={job.id} className={'queue-item queue-' + job.status}>
                        <span className="queue-dot"/>
                        <span className="queue-label">{job.label}</span>
                        <span className="queue-status">{job.status}</span>
                        {job.result?.image && (
                          <img src={`data:image/png;base64,${job.result.image}`}
                            className="queue-thumb" onClick={() => setResult(job.result)} alt=""/>
                        )}
                        <button className="btn-ghost btn-icon"
                          onClick={() => setQueue(q => q.filter(j => j.id !== job.id))}><X size={10}/></button>
                      </div>
                    ))
                  }
                </div>
              )}
            </div>

            {/* AI Advisor */}
            <div className="panel gen-advisor">
              <button className="gen-advisor-hd" onClick={() => setAdvisorOpen((o) => !o)}>
                <Brain size={14} style={{ color:'var(--amber-bright)' }}/>
                <span>AI Advisor</span>
                {advisorOpen ? <ChevronUp size={12}/> : <ChevronDown size={12}/>}
              </button>
              {advisorOpen && (
                <div className="gen-advisor-body">
                  <input className="input" value={advisorGoal}
                    onChange={(e) => setAdvisorGoal(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && askAdvisor()}
                    placeholder="Describe your goal (e.g. anime warrior portrait)…"/>
                  <button className="btn btn-sm btn-primary" onClick={askAdvisor} disabled={advisorBusy}>
                    {advisorBusy ? <span className="spinner"/> : <Brain size={12}/>} Ask
                  </button>
                  {advisorResult && (
                    <div className="gen-advisor-result">
                      <p>{advisorResult.recommendation}</p>
                      {advisorResult.suggested_model && (
                        <div className="gen-hint">Model: <strong>{advisorResult.suggested_model}</strong></div>
                      )}
                      <button className="btn btn-sm btn-cyan" onClick={applyAdvisorSettings}>
                        <Sparkles size={12}/> Apply settings
                      </button>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* ComfyUI + generate button */}
            <div className="gen-bottom">
              <div className="gen-comfyui">
                <Layers size={13} style={{ color: comfyuiStatus?.connected ? 'var(--green)' : 'var(--text-faint)' }}/>
                <span>ComfyUI {comfyuiStatus?.connected ? `v${comfyuiStatus.version}` : '— offline'}</span>
                <label style={{ marginLeft:'auto', cursor: comfyuiStatus?.connected ? 'pointer' : 'not-allowed' }}>
                  <input type="checkbox" checked={useComfyUI} disabled={!comfyuiStatus?.connected}
                    onChange={(e) => setUseComfyUI(e.target.checked)} style={{ display:'none' }}/>
                  <div className={'toggle-track' + (useComfyUI ? ' on' : '')}><div className="toggle-knob"/></div>
                </label>
              </div>
              <div className="batch-row">
                <span className="batch-label">Batch</span>
                {[1,2,4,8].map((n) => (
                  <button key={n} className={'batch-btn' + (batchSize === n ? ' active' : '')}
                    onClick={() => setBatchSize(n)}>{n}×</button>
                ))}
              </div>
              <button className="btn btn-primary btn-full gen-run-btn" onClick={run} disabled={working}>
                {working
                  ? <><span className="spinner"/> Generating…</>
                  : useComfyUI
                    ? <><Layers size={15}/> Generate via ComfyUI</>
                    : batchSize > 1
                      ? <><Sparkles size={15}/> Generate {batchSize}×</>
                      : <><Sparkles size={15}/> Generate</>}
              </button>
            </div>

          </div>
        </div>
      </div>
    </div>
  )
}
