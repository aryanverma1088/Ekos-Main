export function Loading({ label = 'Loading' }) {
  return (
    <div className="space-y-3 py-5" aria-live="polite" aria-label={label}>
      <div className="flex items-center gap-2 mb-5">
        <span className="inline-block w-2 h-2 rounded-full bg-info animate-pulse" />
        <span className="text-[11px] font-mono uppercase tracking-[0.16em] text-muted">{label}</span>
      </div>
      {[1, 2, 3].map((item) => (
        <div key={item} className="data-surface border border-border-soft rounded-xl p-5 space-y-3">
          <div className="skeleton-line h-4 rounded w-2/5" />
          <div className="skeleton-line h-3 rounded w-1/4" />
          <div className="skeleton-line h-3 rounded w-full" />
          <div className="skeleton-line h-3 rounded w-4/5" />
        </div>
      ))}
    </div>
  )
}

export function ErrorState({ message, hint }) {
  return (
    <div className="border border-conflict/40 bg-conflict-soft/40 rounded-md px-5 py-4 text-sm">
      <p className="text-conflict-paper font-medium">{message}</p>
      {hint && <p className="text-muted mt-1 text-[13px]">{hint}</p>}
    </div>
  )
}

export function EmptyState({ title, body }) {
  return (
    <div className="data-surface border border-dashed border-border rounded-xl px-6 py-12 text-center">
      <p className="font-display text-lg text-paper">{title}</p>
      {body && <p className="text-muted text-sm mt-2 max-w-md mx-auto">{body}</p>}
    </div>
  )
}
