import { CheckCircle2, AlertTriangle, Info } from 'lucide-react'
import { useStore } from '../store'
const ICONS = { ok: CheckCircle2, err: AlertTriangle, info: Info }
export default function Toasts() {
  const toasts = useStore((s) => s.toasts)
  return (
    <div className="toast-wrap">
      {toasts.map((t) => {
        const Icon = ICONS[t.kind] ?? Info
        return (
          <div key={t.id} className={'toast ' + t.kind}>
            <Icon size={16} /> {t.message}
          </div>
        )
      })}
    </div>
  )
}
