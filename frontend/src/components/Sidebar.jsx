import { NavLink } from 'react-router-dom'
import { MessageSquare, Sparkles, Download, Images, Settings, Cpu, Server, Layers } from 'lucide-react'
import { useStore } from '../store'

const NAV = [
  { to: '/',          icon: MessageSquare, label: 'Chat' },
  { to: '/generate',  icon: Sparkles,      label: 'Generate' },
  { to: '/downloads', icon: Download,      label: 'Models' },
  { to: '/gallery',   icon: Images,        label: 'Gallery' },
]
const NAV2 = [
  { to: '/settings', icon: Settings, label: 'Settings' },
]

export default function Sidebar() {
  const { status, statusError } = useStore()
  const gpu = status?.cuda
    ? `${status.vram_gb ?? '?'}GB GPU`
    : status ? 'CPU only' : '—'

  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-mark">✦</div>
        <div className="brand-text">
          <h1>Creative Studio</h1>
          <span>v3</span>
        </div>
      </div>

      <nav className="nav">
        <div className="nav-label">Workspace</div>
        {NAV.map(({ to, icon: Icon, label }) => (
          <NavLink key={to} to={to} end={to === '/'}
            className={({ isActive }) => 'nav-item' + (isActive ? ' active' : '')}>
            <Icon size={17} strokeWidth={2} /> {label}
          </NavLink>
        ))}
        <div className="nav-label">System</div>
        {NAV2.map(({ to, icon: Icon, label }) => (
          <NavLink key={to} to={to}
            className={({ isActive }) => 'nav-item' + (isActive ? ' active' : '')}>
            <Icon size={17} strokeWidth={2} /> {label}
          </NavLink>
        ))}
      </nav>

      <div className="sidebar-foot">
        <div className="status-pill">
          <span className={'dot ' + (statusError ? 'off' : status?.ollama ? 'on' : 'warn')} />
          <Server size={12} />
          Ollama {statusError ? 'offline' : status?.ollama ? 'ready' : 'connecting…'}
        </div>
        <div className="status-pill">
          <span className={'dot ' + (status?.cuda ? 'on' : 'warn')} />
          <Cpu size={12} /> {gpu}
        </div>
      </div>
    </aside>
  )
}
