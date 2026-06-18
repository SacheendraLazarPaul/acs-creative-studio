const j = async (url, opts = {}) => {
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  })
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      if (typeof body.detail === 'string') detail = body.detail
      else if (Array.isArray(body.detail)) detail = body.detail.map((d) => d.msg || JSON.stringify(d)).join('; ')
      else if (body.detail) detail = String(body.detail)
    } catch {}
    throw new Error(detail)
  }
  return res.json()
}

export const api = {
  status:        () => j('/api/status'),
  getConfig:     () => j('/api/config'),
  setConfig:     (body) => j('/api/config', { method: 'POST', body }),
  models:        () => j('/api/models'),
  ollamaModels:  () => j('/api/ollama/models'),
  ollamaPull:    (model_name) => j('/api/ollama/pull', { method: 'POST', body: { model_name } }),
  sessions:      () => j('/api/chat/sessions'),
  session:       (id) => j(`/api/chat/sessions/${id}`),
  newSession:    () => j('/api/chat/sessions', { method: 'POST' }),
  delSession:    (id) => j(`/api/chat/sessions/${id}`, { method: 'DELETE' }),
  clearSessions: () => j('/api/chat/sessions', { method: 'DELETE' }),
  chat:          (body) => j('/api/chat', { method: 'POST', body }),
  analyzeImage:  (image, task) => j('/api/analyze-image', { method: 'POST', body: { image, task } }),
  downloads:     () => j('/api/downloads'),
  dlStart:       (model_id) => j('/api/download/start',  { method: 'POST', body: { model_id } }),
  dlPause:       (model_id) => j('/api/download/pause',  { method: 'POST', body: { model_id } }),
  dlResume:      (model_id) => j('/api/download/resume', { method: 'POST', body: { model_id } }),
  dlCancel:      (model_id) => j('/api/download/cancel', { method: 'POST', body: { model_id } }),
  delModel:      (body) => j('/api/model/delete', { method: 'POST', body }),
  generate:      (body) => j('/api/generate', { method: 'POST', body }),
  enhance:       (body) => j('/api/enhance-prompt', { method: 'POST', body }),
  suggest:       (body) => j('/api/suggest-prompts', { method: 'POST', body }),
  outputs:       () => j('/api/outputs'),
  delOutput:     (filename) => j(`/api/outputs/${encodeURIComponent(filename)}`, { method: 'DELETE' }),
  browse:        (path, exts) => j('/api/browse?' + new URLSearchParams({path: path ?? '', exts: exts ?? ''})),
  scan:          () => j('/api/scan', { method: 'POST' }),
  findComfyUI:   () => j('/api/find-comfyui'),
  advisor:         (body) => j('/api/advisor', { method: 'POST', body }),
  youtubeSearch:   (q) => j(`/api/search/youtube?q=${encodeURIComponent(q)}`),
  civitaiSearch:   (q) => j(`/api/search/civitai?q=${encodeURIComponent(q)}`),
  searchWikipedia: (q) => j(`/api/search/wikipedia?q=${encodeURIComponent(q)}`),
  searchArxiv:     (q) => j(`/api/search/arxiv?q=${encodeURIComponent(q)}`),
  searchGithub:    (q) => j(`/api/search/github?q=${encodeURIComponent(q)}`),
  searchAnime:     (q) => j(`/api/search/anime?q=${encodeURIComponent(q)}`),
  searchCrypto:    (q) => j(`/api/search/crypto?q=${encodeURIComponent(q)}`),
  searchWeather:   (q) => j(`/api/search/weather?q=${encodeURIComponent(q)}`),
  searchBooks:     (q) => j(`/api/search/books?q=${encodeURIComponent(q)}`),
  searchMusic:     (q) => j(`/api/search/music?q=${encodeURIComponent(q)}`),
  searchCountry:   (q) => j(`/api/search/country?q=${encodeURIComponent(q)}`),
  searchReddit:    (q, sr = '') => j(`/api/search/reddit?q=${encodeURIComponent(q)}${sr?`&sr=${encodeURIComponent(sr)}`:''}`),
  searchTwitter:   (q) => j(`/api/search/twitter?q=${encodeURIComponent(q)}`),
  searchInstagram: (q) => j(`/api/search/instagram?q=${encodeURIComponent(q)}`),
  searchCoomer:      (q) => j(`/api/search/coomer?q=${encodeURIComponent(q)}`),
  searchSimpcity:    (q) => j(`/api/search/simpcity?q=${encodeURIComponent(q)}`),
  searchHuggingFace: (q) => j(`/api/search/huggingface?q=${encodeURIComponent(q)}`),
  searchPornHub:     (q) => j(`/api/search/pornhub?q=${encodeURIComponent(q)}`),
  searchFansly:      (q) => j(`/api/search/fansly?q=${encodeURIComponent(q)}`),
  searchHentai:      (q) => j(`/api/search/hentai?q=${encodeURIComponent(q)}`),
  searchRedGIFs:     (q) => j(`/api/search/redgifs?q=${encodeURIComponent(q)}`),
  browsePage:      (url, max_chars) => j(`/api/browse/page?url=${encodeURIComponent(url)}${max_chars?`&max_chars=${max_chars}`:''}`),
  getMemory:       () => j('/api/memory'),
  addMemoryFact:   (fact)       => j('/api/memory/fact',       { method: 'POST', body: { fact } }),
  addMemoryPref:   (preference) => j('/api/memory/preference', { method: 'POST', body: { preference } }),
  delMemoryFact:   (index)      => j(`/api/memory/fact/${index}`,       { method: 'DELETE' }),
  delMemoryPref:   (index)      => j(`/api/memory/preference/${index}`, { method: 'DELETE' }),
  clearMemory:     () => j('/api/memory/clear', { method: 'POST' }),
  removeBg:        (image) => j('/api/remove-bg',    { method: 'POST', body: { image } }),
  faceRestore:     (image) => j('/api/face-restore', { method: 'POST', body: { image } }),
  interrogate:     (image) => j('/api/interrogate',  { method: 'POST', body: { image } }),
  // Persona + local engine
  getPersona:      () => j('/api/persona'),
  setPersona:      (body) => j('/api/persona', { method: 'POST', body }),
  localModels:     () => j('/api/local-models'),
  civitaiBrowse:   (q, type, page) =>
    j(`/api/civitai/browse?q=${encodeURIComponent(q||'')}&type=${type||''}&page=${page||1}`),
  civitaiDownload: (body)  => j('/api/civitai/download', { method: 'POST', body }),
}

export const chatStream = async (body, onDelta, onMeta, onDone, onError, signal) => {
  let res
  try {
    res = await fetch('/api/chat/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal,
    })
  } catch (e) {
    if (e.name === 'AbortError') return
    onError(e.message); return
  }
  if (!res.ok) {
    let msg = res.statusText
    try { msg = (await res.json()).detail || msg } catch {}
    onError(msg); return
  }
  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buf = ''
  while (true) {
    if (signal?.aborted) { reader.cancel(); break }
    const { done, value } = await reader.read()
    if (done) break
    buf += decoder.decode(value, { stream: true })
    const lines = buf.split('\n')
    buf = lines.pop()
    for (const line of lines) {
      if (!line.startsWith('data: ')) continue
      try {
        const evt = JSON.parse(line.slice(6))
        if (evt.type === 'meta') onMeta(evt)
        else if (evt.type === 'delta') onDelta(evt.content)
        else if (evt.type === 'done') onDone()
        else if (evt.type === 'error') onError(evt.message)
        else if (evt.type === 'searching') onMeta({ searching: true, searched: false, sources: [] })
        else if (evt.type === 'gen_start' || evt.type === 'gen_progress' || evt.type === 'gen_done') onMeta(evt)
      } catch {}
    }
  }
}

export const fmtBytes = (b) => {
  if (!b) return '0 B'
  const u = ['B','KB','MB','GB']; let i = 0; let n = b
  while (n >= 1024 && i < u.length - 1) { n /= 1024; i++ }
  return `${n.toFixed(n < 10 && i > 0 ? 1 : 0)} ${u[i]}`
}
export const fmtETA = (s) => {
  if (!s || s < 0) return '—'
  if (s < 60) return `${s|0}s`
  if (s < 3600) return `${(s/60)|0}m ${(s%60)|0}s`
  return `${(s/3600)|0}h ${((s%3600)/60)|0}m`
}
export const fileToB64 = (file) => new Promise((resolve, reject) => {
  const r = new FileReader()
  r.onload = () => resolve(r.result)
  r.onerror = reject
  r.readAsDataURL(file)
})
