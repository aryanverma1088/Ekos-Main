import { Link } from 'react-router-dom'

export default function NotFound() {
  return (
    <div className="px-4 sm:px-8 py-6 sm:py-8">
      <p className="text-[11px] font-mono uppercase tracking-wider text-muted mb-2">404</p>
      <h1 className="font-display text-3xl text-paper mb-3">Page not found</h1>
      <p className="text-sm text-muted mb-6">
        There's nothing at this address.
      </p>
      <Link to="/" className="text-[13px] font-mono text-verified hover:underline">
        ← Back to Dashboard
      </Link>
    </div>
  )
}
