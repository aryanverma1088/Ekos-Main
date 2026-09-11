const MAX_LEVEL = 6

// Mirrors backend/authority.py -- used only as a fallback when a caller
// hasn't yet passed the server-computed `label` (e.g. legacy call sites).
// Every current call site passes the real label from the API response, so
// the label is never silently re-derived out of sync with the backend.
const FALLBACK_LABELS = {
  1: 'Official Policy',
  2: 'Approved SOP',
  3: 'Official Documentation',
  4: 'Project Documentation',
  5: 'Meeting Notes',
  6: 'Informal Notes',
}

/**
 * Shows the authority level as a plain-English label (e.g. "Official
 * Policy") with a dot-ladder as secondary visual reinforcement -- never
 * just "L1" on its own. Authority is a trust signal; per the design
 * guidelines, important information belongs inline, not hidden behind a
 * hover tooltip.
 */
export default function AuthorityLadder({ level, label, compact = false }) {
  const filled = MAX_LEVEL - level + 1
  const resolvedLabel = label || FALLBACK_LABELS[level] || `Level ${level}`

  return (
    <span className="inline-flex items-center gap-1.5" title={`Authority level ${level} of ${MAX_LEVEL} (1 = highest)`}>
      <span className="authority-ladder" aria-hidden="true">
        {Array.from({ length: MAX_LEVEL }).map((_, i) => (
          <span
            key={i}
            className="authority-dot"
            style={{
              backgroundColor: i < filled ? 'var(--color-verified)' : 'var(--color-border)',
            }}
          />
        ))}
      </span>
      <span className={compact ? 'text-[11px] text-paper-dim' : 'text-[13px] text-paper-dim'}>
        {resolvedLabel}
      </span>
    </span>
  )
}
