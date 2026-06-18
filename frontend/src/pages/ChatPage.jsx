import { useEffect, useRef, useState, useCallback } from 'react'
import { Plus, Trash2, Send, Globe, ImagePlus, Sparkles, MessageSquare, X, ExternalLink, Pause, Play, Square, Copy, Download, Check } from 'lucide-react'
import { chatStream, api, fileToB64, fmtETA } from '../api'
import { useStore } from '../store'

const ANALYSIS_TASKS = ['describe','pose','style','prompt','character','translate']

const STARTERS = [
  "Create an image of a cozy cabin in the snow",
  "What's the weather in Gwalior today?",
  "What's trending online right now?",
  "Write a Python script to rename files",
  "What is the current Bitcoin price?",
]

// Split message text into {type:'text'|'code', text?, lang?, code?} segments
function parseSegments(text) {
  const parts = []
  const re = /```([^\n`]*)\n?([\s\S]*?)```/g
  let last = 0, m
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) parts.push({ type: 'text', text: text.slice(last, m.index) })
    parts.push({ type: 'code', lang: m[1].trim() || 'code', code: m[2].trimEnd() })
    last = m.index + m[0].length
  }
  if (last < text.length) parts.push({ type: 'text', text: text.slice(last) })
  return parts
}

// Markdown → HTML for non-code segments only (code blocks handled by CodeBlock)
function mdToHtml(raw) {
  let s = raw
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
  s = s.replace(/`([^`\n]+)`/g, '<code class="md-code">$1</code>')
  s = s.replace(/\*\*([^*\n]+)\*\*/g, '<strong>$1</strong>')
  s = s.replace(/\*([^*\n]+)\*/g, '<em>$1</em>')
  s = s.replace(/^### (.+)$/gm, '<div class="md-h3">$1</div>')
  s = s.replace(/^## (.+)$/gm,  '<div class="md-h2">$1</div>')
  s = s.replace(/^# (.+)$/gm,   '<div class="md-h1">$1</div>')
  s = s.replace(/^[-*+] (.+)$/gm, '<div class="md-li"><span class="md-bullet">•</span>$1</div>')
  s = s.replace(/^(\d+)\. (.+)$/gm, '<div class="md-li"><span class="md-bullet">$1.</span>$2</div>')
  s = s.replace(/^---+$/gm, '<hr class="md-hr">')
  s = s.replace(/\n/g, '<br>')
  return s
}

const EXT_MAP = { python:'py', javascript:'js', typescript:'ts', bash:'sh', shell:'sh', css:'css', html:'html', json:'json', sql:'sql', rust:'rs', go:'go', java:'java', cpp:'cpp', c:'c', jsx:'jsx', tsx:'tsx' }

function CodeBlock({ lang, code }) {
  const [copied, setCopied] = useState(false)

  const doCopy = () => {
    navigator.clipboard.writeText(code).catch(() => {
      const ta = document.createElement('textarea')
      ta.value = code; document.body.appendChild(ta); ta.select()
      document.execCommand('copy'); document.body.removeChild(ta)
    })
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const doDownload = () => {
    const ext = EXT_MAP[lang.toLowerCase()] || lang || 'txt'
    const blob = new Blob([code], { type: 'text/plain' })
    const url  = URL.createObjectURL(blob)
    const a    = document.createElement('a')
    a.href = url; a.download = `code.${ext}`; a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="code-block">
      <div className="code-header">
        <span className="code-lang">{lang}</span>
        <div className="code-btns">
          <button className="code-btn" onClick={doCopy}>
            {copied ? <Check size={12} /> : <Copy size={12} />}
            {copied ? 'Copied!' : 'Copy'}
          </button>
          <button className="code-btn" onClick={doDownload}>
            <Download size={12} /> Download
          </button>
        </div>
      </div>
      <pre className="md-pre code-pre"><code>{code}</code></pre>
    </div>
  )
}

function MsgText({ text, streaming }) {
  const segments = parseSegments(text)
  return (
    <div className="msg-text md-content">
      {segments.map((seg, i) => {
        if (seg.type === 'code') return <CodeBlock key={i} lang={seg.lang} code={seg.code} />
        const isLast = i === segments.length - 1
        return (
          <div key={i}
            dangerouslySetInnerHTML={{
              __html: mdToHtml(seg.text) + (streaming && isLast && seg.text ? '<span class="stream-cursor"></span>' : '')
            }}
          />
        )
      })}
      {streaming && segments.length === 0 && <span className="stream-cursor" />}
    </div>
  )
}

// Pull a generated /outputs media URL out of saved message text (reloaded sessions).
function extractMedia(text) {
  if (!text) return null
  const m = text.match(/\/outputs\/[^\s)"']+\.(png|jpg|jpeg|webp|mp4|webm|gif)/i)
  return m ? m[0] : null
}
function MediaOut({ url }) {
  const isVideo = /\.(mp4|webm)$/i.test(url)
  return (
    <div className="gen-box">
      {isVideo
        ? <video className="gen-out" src={url} controls loop muted />
        : <img className="gen-out" src={url} alt="generated" loading="lazy" />}
    </div>
  )
}

export default function ChatPage() {
  const { status, toast } = useStore()
  const [sessions, setSessions]     = useState([])
  const [activeId, setActiveId]     = useState(null)
  const [messages, setMessages]     = useState([])
  const [input, setInput]           = useState('')
  const [busy, setBusy]             = useState(false)
  const [isPaused, setIsPaused]     = useState(false)
  const [withSearch, setWithSearch] = useState(false)
  const [pendingImg, setPendingImg] = useState(null)
  const scrollRef  = useRef(null)
  const taRef      = useRef(null)
  const abortCtrl  = useRef(null)
  const pausedRef  = useRef(false)
  const pauseBuf   = useRef('')
  const streamBotId = useRef(null)
  const isAtBottom = useRef(true)

  const loadSessions = useCallback(async () => {
    try { setSessions((await api.sessions()).sessions ?? []) } catch {}
  }, [])

  const handleScroll = useCallback(() => {
    if (!scrollRef.current) return
    const { scrollTop, scrollHeight, clientHeight } = scrollRef.current
    isAtBottom.current = scrollHeight - scrollTop - clientHeight < 100
  }, [])

  useEffect(() => { loadSessions() }, [loadSessions])

  useEffect(() => {
    if (scrollRef.current && isAtBottom.current)
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
  }, [messages])

  const openSession = async (id) => {
    isAtBottom.current = true
    setActiveId(id)
    try { setMessages((await api.session(id)).messages ?? []) }
    catch { setMessages([]) }
  }

  const newChat = async () => {
    try {
      const { id } = await api.newSession()
      await loadSessions()
      setActiveId(id); setMessages([])
    } catch (e) { toast(e.message, 'err') }
  }

  const delSession = async (e, id) => {
    e.stopPropagation()
    try {
      await api.delSession(id)
      if (id === activeId) { setActiveId(null); setMessages([]) }
      loadSessions()
    } catch (e) { toast(e.message, 'err') }
  }

  const pickImg = async (e) => {
    const f = e.target.files?.[0]; if (!f) return
    setPendingImg(await fileToB64(f)); e.target.value = ''
  }

  const runAnalysis = async (task) => {
    if (!pendingImg) return
    setBusy(true)
    setMessages((m) => [...m, { role:'user', content:`[Image] ${task}` }])
    try {
      const { analysis } = await api.analyzeImage(pendingImg, task)
      setMessages((m) => [...m, { role:'assistant', content: analysis }])
    } catch (e) {
      setMessages((m) => [...m, { role:'assistant', content:'Vision error: ' + e.message }])
    } finally { setBusy(false); setPendingImg(null) }
  }

  const stopChat = () => {
    abortCtrl.current?.abort()
    pausedRef.current = false
    pauseBuf.current = ''
    setIsPaused(false)
    setBusy(false)
    setMessages((m) => m.map((msg) =>
      msg.streaming ? { ...msg, streaming: false } : msg
    ))
  }

  const pauseChat = () => {
    pausedRef.current = true
    setIsPaused(true)
  }

  const resumeChat = () => {
    const buf = pauseBuf.current
    pauseBuf.current = ''
    pausedRef.current = false
    setIsPaused(false)
    if (buf && streamBotId.current != null) {
      setMessages((m) => m.map((msg) =>
        msg._id === streamBotId.current ? { ...msg, content: msg.content + buf } : msg
      ))
    }
  }

  const send = async () => {
    const text = input.trim(); if (!text || busy) return
    let sid = activeId
    if (!sid) {
      try { sid = (await api.newSession()).id; setActiveId(sid) } catch {}
    }
    const history = messages.map((m) => ({ role: m.role, content: m.content }))
    setInput('')
    if (taRef.current) taRef.current.style.height = 'auto'
    pausedRef.current = false
    pauseBuf.current = ''
    setIsPaused(false)
    isAtBottom.current = true
    setBusy(true)

    abortCtrl.current = new AbortController()
    const botId = Date.now()
    streamBotId.current = botId
    setMessages((m) => [
      ...m,
      { role: 'user', content: text },
      { role: 'assistant', content: '', searched: false, sources: [], streaming: true, searching: false, _id: botId },
    ])

    await chatStream(
      { message: text, session_id: sid ?? '', history, with_search: withSearch, model: status?.text_model ?? '' },
      (delta) => {
        if (pausedRef.current) {
          pauseBuf.current += delta
          return
        }
        setMessages((m) => m.map((msg) =>
          msg._id === botId ? { ...msg, content: msg.content + delta } : msg
        ))
      },
      (meta) => setMessages((m) => m.map((msg) => {
        if (msg._id !== botId) return msg
        if (meta.type === 'gen_start')
          return { ...msg, searching: false, gen: { kind: meta.kind, pct: 0, eta: 0, log: 'Starting…', active: true } }
        if (meta.type === 'gen_progress')
          return { ...msg, gen: { ...(msg.gen || {}), pct: meta.pct, eta: meta.eta, log: meta.log, active: true } }
        if (meta.type === 'gen_done')
          return { ...msg, gen: { ...(msg.gen || {}), active: false, url: meta.url, kind: meta.kind } }
        return meta.searching
          ? { ...msg, searching: true }
          : { ...msg, searching: false, searched: meta.searched, sources: meta.sources || [] }
      })),
      () => {
        // flush any remaining buffered text on done
        const buf = pauseBuf.current
        pauseBuf.current = ''
        pausedRef.current = false
        setIsPaused(false)
        setMessages((m) => m.map((msg) =>
          msg._id === botId ? { ...msg, content: msg.content + buf, streaming: false } : msg
        ))
        setBusy(false)
        streamBotId.current = null
        loadSessions()
      },
      (err) => {
        pausedRef.current = false
        pauseBuf.current = ''
        setIsPaused(false)
        setMessages((m) => m.map((msg) =>
          msg._id === botId ? { ...msg, content: 'Error: ' + err, streaming: false } : msg
        ))
        setBusy(false)
        streamBotId.current = null
      },
      abortCtrl.current.signal
    )
  }

  const onKey = (e) => { if (e.key==='Enter' && !e.shiftKey) { e.preventDefault(); send() } }
  const grow  = (e) => {
    e.target.style.height = 'auto'
    e.target.style.height = Math.min(e.target.scrollHeight, 140) + 'px'
    setInput(e.target.value)
  }

  return (
    <div className="chat-wrap">
      {/* sessions rail */}
      <div className="sessions-rail">
        <div className="sessions-head">
          <button className="btn btn-primary btn-full" onClick={newChat}>
            <Plus size={15} /> New chat
          </button>
        </div>
        <div className="session-list">
          {sessions.length === 0 && (
            <div className="muted" style={{ padding: '12px', fontSize: 12 }}>No conversations yet.</div>
          )}
          {sessions.map((s) => (
            <div key={s.id}
              className={'session-item' + (s.id === activeId ? ' active' : '')}
              onClick={() => openSession(s.id)}>
              <MessageSquare size={13} style={{ flexShrink: 0 }} />
              <span className="session-title">{s.title}</span>
              <button className="session-del btn-ghost btn-icon"
                onClick={(e) => delSession(e, s.id)}>
                <Trash2 size={13} />
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* main */}
      <div className="chat-main">
        <div className="chat-scroll" ref={scrollRef} onScroll={handleScroll}>
          {messages.length === 0 ? (
            <div className="empty" style={{ height: '100%' }}>
              <div className="glyph">✦</div>
              <h3>Hi, I'm {(status?.ai_name || 'Nova').charAt(0).toUpperCase() + (status?.ai_name || 'Nova').slice(1)} 👋</h3>
              <p>Chat, <strong>generate images</strong>, write code, or ask about live info —
                 attach an image for vision, or toggle <Globe size={12} style={{ verticalAlign: -2 }} /> for web search.</p>
              <div className="starter-chips">
                {STARTERS.map((s) => (
                  <button key={s} className="starter-chip"
                    onClick={() => { setInput(s); taRef.current?.focus() }}>
                    {s}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="chat-thread">
              {messages.map((m, i) => (
                <div key={i} className={'msg ' + (m.role === 'user' ? 'user' : 'bot')}>
                  <div className="msg-av">{m.role === 'user' ? 'You' : '✦'}</div>
                  <div className="msg-body">
                    <div className="msg-name">
                      {m.role === 'user' ? 'You' : ((status?.ai_name || 'Nova').charAt(0).toUpperCase() + (status?.ai_name || 'Nova').slice(1))}
                    </div>
                    {m.role === 'user' ? (
                      <div className="msg-text" style={{ whiteSpace: 'pre-wrap' }}>{m.content}</div>
                    ) : m.gen ? (
                      <div className="gen-box">
                        {m.gen.active ? (
                          <div className="gen-progress">
                            <div className="gen-progress-head">
                              <span>{m.gen.kind === 'video' ? '🎬 Generating video…' : '🎨 Generating image…'}</span>
                              <span className="gen-pct">{m.gen.pct ?? 0}%</span>
                            </div>
                            <div className="gen-bar"><div className="gen-bar-fill" style={{ width: `${m.gen.pct ?? 0}%` }} /></div>
                            <div className="gen-meta">
                              <span>{m.gen.log || 'Working…'}</span>
                              <span>{m.gen.eta ? `~${fmtETA(m.gen.eta)} left` : ''}</span>
                            </div>
                          </div>
                        ) : m.gen.url ? (
                          m.gen.kind === 'video'
                            ? <video className="gen-out" src={m.gen.url} controls autoPlay loop muted />
                            : <img className="gen-out" src={m.gen.url} alt="generated" loading="lazy" />
                        ) : <MsgText text={m.content} streaming={false} />}
                      </div>
                    ) : extractMedia(m.content) ? (
                      <MediaOut url={extractMedia(m.content)} />
                    ) : m.searching ? (
                      <div className="typing-search">
                        <Globe size={13} style={{ color: 'var(--cyan-bright)', flexShrink: 0 }} />
                        <span>Searching the web…</span>
                      </div>
                    ) : m.streaming && m.content === '' ? (
                      <div className="typing"><span /><span /><span /></div>
                    ) : (
                      <MsgText text={m.content} streaming={m.streaming} />
                    )}
                    {m.searched && (
                      <div className="msg-searched-wrap">
                        <div className="msg-searched">
                          <Globe size={11} /> searched the web
                        </div>
                        {m.sources?.length > 0 && (
                          <div className="msg-sources">
                            {m.sources.map((s, si) => s.url && (
                              <a key={si} href={s.url} target="_blank" rel="noreferrer"
                                className="source-chip" title={s.title}>
                                <ExternalLink size={10} />
                                <span>{s.source}</span>
                                <span className="source-title">{s.title}</span>
                              </a>
                            ))}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="chat-input-bar">
          <div className="chat-input-inner">
            {/* image analysis bar */}
            {pendingImg && (
              <div className="analysis-bar">
                <div className="thumb-preview" style={{ width: 80 }}>
                  <img src={pendingImg} alt="" style={{ maxHeight: 80 }} />
                  <button className="thumb-rm" onClick={() => setPendingImg(null)}>
                    <X size={13} />
                  </button>
                </div>
                {ANALYSIS_TASKS.map((t) => (
                  <button key={t} className="btn btn-sm" disabled={busy}
                    onClick={() => runAnalysis(t)}>
                    <Sparkles size={12} /> {t}
                  </button>
                ))}
              </div>
            )}

            {busy && (
              <div className="stream-controls">
                {isPaused ? (
                  <button className="stream-btn resume" onClick={resumeChat} title="Resume">
                    <Play size={13} /> Resume
                  </button>
                ) : (
                  <button className="stream-btn pause" onClick={pauseChat} title="Pause">
                    <Pause size={13} /> Pause
                  </button>
                )}
                <button className="stream-btn stop" onClick={stopChat} title="Stop">
                  <Square size={13} /> Stop
                </button>
                {isPaused && <span className="stream-paused-label">Paused — buffering…</span>}
              </div>
            )}

            <div className="chat-box">
              <div className="chat-actions">
                <button className="chat-icon-btn" title="Attach image"
                  onClick={() => document.getElementById('_chat-img').click()}>
                  <ImagePlus size={18} />
                </button>
                <input id="_chat-img" type="file" accept="image/*" hidden onChange={pickImg} />
                <button
                  className={'chat-icon-btn' + (withSearch ? ' on' : '')}
                  title={withSearch ? 'Web search ON' : 'Web search OFF'}
                  onClick={() => setWithSearch((v) => !v)}>
                  <Globe size={18} />
                </button>
              </div>
              <textarea ref={taRef} value={input} onChange={grow} onKeyDown={onKey} rows={1}
                placeholder={`Message ${status?.ai_name ? (status.ai_name.charAt(0).toUpperCase() + status.ai_name.slice(1)) : 'the studio'}…  (Shift+Enter for newline)`} />
              <button className="send-btn" disabled={busy || !input.trim()} onClick={send}>
                {busy ? <span className="spinner" /> : <Send size={17} />}
              </button>
            </div>
            <div className="chat-hint">
              {withSearch ? '🌐 Web search enabled — replies include live results' : 'Enter to send · Shift+Enter for newline'}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
