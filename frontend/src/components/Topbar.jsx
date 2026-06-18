import { useLocation } from 'react-router-dom'
import { Calendar, Clock } from 'lucide-react'
import { useStore } from '../store'

const TITLES = {
  '/': 'Chat', '/generate': 'Generate', '/downloads': 'Model Library',
  '/gallery': 'Gallery', '/settings': 'Settings',
}

export default function Topbar() {
  const { pathname } = useLocation()
  const { status } = useStore()

  return (
    <header className="topbar">
      <h2>{TITLES[pathname] ?? 'Creative Studio'}</h2>
      <div className="topbar-spacer" />
      {status?.date && <span className="chip"><Calendar size={13} />{status.date}</span>}
      {status?.time && <span className="chip"><Clock size={13} />{status.time}</span>}
      {status?.gpu  && <span className="chip cyan">{status.cuda ? status.gpu : 'CPU'}</span>}
    </header>
  )
}
