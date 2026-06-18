import { useLocation } from 'react-router-dom'
import { useState } from 'react'
import { Calendar, Clock, Sun, Moon } from 'lucide-react'
import { useStore } from '../store'

const TITLES = {
  '/': 'Chat', '/generate': 'Generate', '/downloads': 'Model Library',
  '/gallery': 'Gallery', '/settings': 'Settings',
}

export default function Topbar() {
  const { pathname } = useLocation()
  const { status } = useStore()
  const [theme, setTheme] = useState(() => document.documentElement.dataset.theme || 'dark')

  const toggleTheme = () => {
    const next = theme === 'dark' ? 'light' : 'dark'
    setTheme(next)
    document.documentElement.dataset.theme = next
    localStorage.setItem('acs-theme', next)
  }

  return (
    <header className="topbar">
      <h2>{TITLES[pathname] ?? 'Creative Studio'}</h2>
      <div className="topbar-spacer" />
      {status?.date && <span className="chip"><Calendar size={13} />{status.date}</span>}
      {status?.time && <span className="chip"><Clock size={13} />{status.time}</span>}
      {status?.gpu  && <span className="chip cyan">{status.cuda ? status.gpu : 'CPU'}</span>}
      <button className="chip theme-toggle" onClick={toggleTheme}
        title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}>
        {theme === 'dark' ? <Sun size={14} /> : <Moon size={14} />}
        {theme === 'dark' ? 'Light' : 'Dark'}
      </button>
    </header>
  )
}
