const VARIANTS = {
  current: { color: 'var(--color-verified)', label: 'Current' },
  superseded: { color: 'var(--color-outdated)', label: 'Superseded' },
  draft: { color: 'var(--color-muted)', label: 'Draft' },
  high: { color: 'var(--color-conflict)', label: 'High' },
  medium: { color: 'var(--color-outdated)', label: 'Medium' },
  low: { color: 'var(--color-muted)', label: 'Low' },
  contradiction: { color: 'var(--color-conflict)', label: 'Contradiction' },
  definition: { color: 'var(--color-info)', label: 'Definition' },
}

export default function Stamp({ variant, children, title }) {
  const v = VARIANTS[variant] || { color: 'var(--color-muted)', label: variant }
  return (
    <span className="stamp" style={{ color: v.color }} title={title}>
      {children || v.label}
    </span>
  )
}
