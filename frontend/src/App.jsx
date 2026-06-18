import { useEffect } from 'react'
import { Routes, Route } from 'react-router-dom'
import Sidebar from './components/Sidebar'
import Topbar from './components/Topbar'
import Toasts from './components/Toasts'
import ChatPage from './pages/ChatPage'
import GeneratePage from './pages/GeneratePage'
import DownloadsPage from './pages/DownloadsPage'
import { GalleryPage, SettingsPage } from './pages/OtherPages'
import { useStore } from './store'

export default function App() {
  const startPolling = useStore((s) => s.startPolling)
  const loadConfig = useStore((s) => s.loadConfig)

  useEffect(() => { startPolling(); loadConfig() }, [startPolling, loadConfig])

  return (
    <div className="app">
      <Sidebar />
      <div className="main-col">
        <Topbar />
        <Routes>
          <Route path="/" element={<ChatPage />} />
          <Route path="/generate" element={<GeneratePage />} />
          <Route path="/downloads" element={<DownloadsPage />} />
          <Route path="/gallery" element={<GalleryPage />} />
          <Route path="/settings"  element={<SettingsPage />} />
        </Routes>
      </div>
      <Toasts />
    </div>
  )
}
