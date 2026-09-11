import { useEffect, useMemo, useState } from 'react'
import { api } from '../api'
import { Loading, ErrorState, EmptyState } from '../components/States'
import ConflictCard from '../components/ConflictCard'
import Stamp from '../components/Stamp'

const SEVERITY_RANK = { high: 3, medium: 2, low: 1 }

const TYPE_META = {
  contradiction: { label: 'Contradiction', method: 'Numeric-fact extraction (rule-based)' },
  definition: { label: 'Definition conflict', method: 'Definition-pattern regex + cross-department diff' },
  duplicate: { label: 'Near-duplicate', method: 'TF-IDF cosine similarity + clustering' },
  outdated: { label: 'Outdated document', method: 'Document metadata (supersedes chain)' },
}

function pad(n) {
  return String(n).padStart(3, '0')
}

function normalizeCases({ contradictions, definitions, duplicates, outdated }) {
  const cases = []

  contradictions.forEach((c) => cases.push({
    caseId: `CTR-${pad(c.id)}`, type: 'contradiction', severity: c.severity,
    title: c.concept, raw: c,
  }))
  definitions.forEach((c) => cases.push({
    caseId: `DEF-${pad(c.id)}`, type: 'definition', severity: c.severity,
    title: c.concept, raw: c,
  }))
  duplicates.forEach((d) => cases.push({
    caseId: `DUP-${pad(d.id)}`, type: 'duplicate',
    severity: d.similarity_score >= 0.85 ? 'medium' : 'low',
    title: `${d.chunk_a.title} ~ ${d.chunk_b.title}`, raw: d,
  }))
  outdated.forEach((o, i) => cases.push({
    caseId: `OUT-${pad(i + 1)}`, type: 'outdated', severity: 'medium',
    title: o.concept, raw: o,
  }))

  cases.sort((a, b) => SEVERITY_RANK[b.severity] - SEVERITY_RANK[a.severity])
  return cases
}

function DuplicateCase({ c }) {
  const dup = c.raw
  return (
    <div className="data-surface rounded-xl border border-border p-5 shadow-sm">
      <CaseHeader caseId={c.caseId} label={TYPE_META.duplicate.label} title={c.title} severity={c.severity} />
      <div className="flex items-center justify-between mb-3 text-[12px] font-mono text-muted">
        <span>similarity {dup.similarity_score.toFixed(3)}</span>
        <span>cluster #{dup.cluster_id}</span>
      </div>
      <div className="grid sm:grid-cols-2 gap-3">
        {[dup.chunk_a, dup.chunk_b].map((ch) => (
          <div key={ch.chunk_id} className="bg-surface-raised rounded p-3 border border-border-soft">
            <p className="font-display text-sm text-paper truncate">{ch.title}</p>
            <p className="font-mono text-[11px] text-muted mb-2">{ch.doc_key}</p>
            <p className="text-[13px] text-paper-dim leading-snug line-clamp-3">{ch.chunk_text}</p>
          </div>
        ))}
      </div>
      <CaseFooter method={TYPE_META.duplicate.method} />
    </div>
  )
}

function OutdatedCase({ c }) {
  const o = c.raw
  return (
    <div className="data-surface rounded-xl border border-border p-5 shadow-sm">
      <CaseHeader caseId={c.caseId} label={TYPE_META.outdated.label} title={c.title} severity={c.severity} />
      <div className="grid sm:grid-cols-2 gap-3 mb-4">
        <div className="rounded-md border p-4" style={{ borderColor: 'var(--color-outdated)', backgroundColor: 'var(--color-outdated-soft)' }}>
          <div className="flex items-center justify-between mb-2">
            <p className="font-display text-sm text-paper">{o.outdated_title}</p>
            <Stamp variant="superseded" />
          </div>
          <p className="font-mono text-[11px] text-muted mb-2">{o.outdated_doc_key} · v{o.outdated_version}</p>
          {o.outdated_effective_date && (
            <p className="text-[12px] text-paper-dim">Effective {o.outdated_effective_date}</p>
          )}
        </div>
        <div className="rounded-md border p-4" style={{ borderColor: 'var(--color-verified)', backgroundColor: 'var(--color-verified-soft)' }}>
          <div className="flex items-center justify-between mb-2">
            <p className="font-display text-sm text-paper">{o.current_title}</p>
            <Stamp variant="current" />
          </div>
          <p className="font-mono text-[11px] text-muted mb-2">{o.current_doc_key} · v{o.current_version}</p>
          {o.current_effective_date && (
            <p className="text-[12px] text-paper-dim">Effective {o.current_effective_date}</p>
          )}
        </div>
      </div>
      <p className="text-[13px] text-verified-paper leading-relaxed">→ {o.reason}</p>
      <CaseFooter method={TYPE_META.outdated.method} />
    </div>
  )
}

function CaseHeader({ caseId, label, title, severity }) {
  return (
    <div className="flex items-center justify-between mb-4 gap-3 flex-wrap">
      <div>
        <p className="text-[11px] font-mono uppercase tracking-wider text-muted mb-1">
          <span className="text-paper-dim mr-2">{caseId}</span>{label}
        </p>
        <h3 className="font-display text-xl text-paper">{title}</h3>
      </div>
      <Stamp variant={severity}>{severity} severity</Stamp>
    </div>
  )
}

function CaseFooter({ method }) {
  return (
    <p className="mt-3 pt-3 border-t border-border-soft text-[11px] font-mono text-muted-soft">
      Detected via: {method}
    </p>
  )
}

function StatBlock({ label, value, accent }) {
  return (
    <div className="border border-border-soft rounded-md px-4 py-3 flex-1 min-w-[140px]">
      <p className="text-[11px] font-mono uppercase tracking-wider text-muted">{label}</p>
      <p className="font-display text-2xl mt-1" style={{ color: accent || 'var(--color-paper)' }}>{value}</p>
    </div>
  )
}

const FILTER_TYPES = ['contradiction', 'definition', 'duplicate', 'outdated']
const FILTER_SEVERITIES = ['high', 'medium', 'low']

export default function IntegrityCenter() {
  const [raw, setRaw] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [typeFilter, setTypeFilter] = useState(new Set())
  const [severityFilter, setSeverityFilter] = useState(new Set())

  useEffect(() => {
    setLoading(true)
    Promise.all([
      api.listConflicts({ conflict_type: 'contradiction' }),
      api.listDefinitions(),
      api.listDuplicates(),
      api.listOutdated(),
    ])
      .then(([contradictions, definitions, duplicates, outdated]) => {
        setRaw({ contradictions, definitions, duplicates, outdated })
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  const cases = useMemo(() => (raw ? normalizeCases(raw) : []), [raw])

  const filtered = cases.filter((c) => {
    if (typeFilter.size > 0 && !typeFilter.has(c.type)) return false
    if (severityFilter.size > 0 && !severityFilter.has(c.severity)) return false
    return true
  })

  function toggle(setFn, current, value) {
    const next = new Set(current)
    next.has(value) ? next.delete(value) : next.add(value)
    setFn(next)
  }

  const highCount = cases.filter((c) => c.severity === 'high').length
  const resolvedCount = cases.filter((c) => c.raw.resolved_doc_key).length
  const unresolvedCount = cases.filter((c) => c.type === 'definition' && !c.raw.resolved_doc_key).length

  return (
    <div className="px-4 sm:px-10 py-7 sm:py-10 max-w-5xl">
      <header className="mb-6">
        <p className="text-[11px] font-mono uppercase tracking-wider text-muted mb-2">
          Knowledge integrity engine
        </p>
        <h1 className="page-heading font-display text-4xl text-paper mb-2">Integrity Center</h1>
        <p className="text-[14px] text-muted max-w-2xl">
          Every open case below is a real, detected disagreement in the organization's
          documented knowledge — not a simulated example. Each case shows its evidence,
          how it was found, and (where applicable) which source is authoritative and why.
        </p>
      </header>

      {loading && <Loading label="Loading integrity case queue" />}
      {error && <ErrorState message="Could not load integrity data" hint={error} />}

      {!loading && !error && (
        <>
          <div className="flex gap-3 mb-6 flex-wrap">
            <StatBlock label="Open Cases" value={cases.length} />
            <StatBlock label="High Severity" value={highCount} accent={highCount > 0 ? 'var(--color-conflict)' : undefined} />
            <StatBlock label="Resolved by Authority" value={resolvedCount} accent="var(--color-verified)" />
            <StatBlock label="Unresolved (context-dependent)" value={unresolvedCount} accent="var(--color-outdated)" />
          </div>

          <div className="flex flex-wrap items-center gap-2 mb-6 pb-6 border-b border-border-soft">
            <span className="text-[11px] font-mono uppercase tracking-wider text-muted mr-1">Filter:</span>
            {FILTER_TYPES.map((t) => (
              <button
                key={t}
                onClick={() => toggle(setTypeFilter, typeFilter, t)}
                aria-pressed={typeFilter.has(t)}
                className={`px-2.5 py-1 rounded text-[12px] font-mono border transition-colors ${
                  typeFilter.has(t)
                    ? 'bg-verified-soft border-verified text-verified-paper'
                    : 'border-border-soft text-muted hover:text-paper'
                }`}
              >
                {TYPE_META[t].label}
              </button>
            ))}
            <span className="w-px h-4 bg-border-soft mx-1" />
            {FILTER_SEVERITIES.map((s) => (
              <button
                key={s}
                onClick={() => toggle(setSeverityFilter, severityFilter, s)}
                aria-pressed={severityFilter.has(s)}
                className={`px-2.5 py-1 rounded text-[12px] font-mono border capitalize transition-colors ${
                  severityFilter.has(s)
                    ? 'bg-verified-soft border-verified text-verified-paper'
                    : 'border-border-soft text-muted hover:text-paper'
                }`}
              >
                {s}
              </button>
            ))}
            {(typeFilter.size > 0 || severityFilter.size > 0) && (
              <button
                onClick={() => { setTypeFilter(new Set()); setSeverityFilter(new Set()) }}
                className="text-[12px] font-mono text-muted hover:text-paper underline ml-1"
              >
                Clear
              </button>
            )}
          </div>

          {filtered.length === 0 ? (
            cases.length === 0 ? (
              <EmptyState title="No integrity issues detected" body="Run scripts/build_integrity_engine.py to populate the case queue." />
            ) : (
              <EmptyState title="No cases match these filters" body="Try clearing a filter above." />
            )
          ) : (
            <div className="space-y-4">
              {filtered.map((c) => {
                if (c.type === 'contradiction' || c.type === 'definition') {
                  return (
                    <ConflictCard
                      key={c.caseId}
                      conflict={c.raw}
                      caseId={c.caseId}
                      detectionMethod={TYPE_META[c.type].method}
                    />
                  )
                }
                if (c.type === 'duplicate') return <DuplicateCase key={c.caseId} c={c} />
                return <OutdatedCase key={c.caseId} c={c} />
              })}
            </div>
          )}

          {raw.duplicates.length === 0 && (!typeFilter.size || typeFilter.has('duplicate')) && (
            <div className="mt-6 border border-dashed border-border rounded-md p-4">
              <p className="text-[13px] text-paper-dim">
                <span className="font-mono text-[11px] uppercase tracking-wider text-muted block mb-1">
                  Why no duplicate cases appear
                </span>
                Validated finding, not a bug: the fallback lexical detector (TF-IDF cosine
                similarity) can't reliably separate this corpus's paraphrased duplicate
                cases from unrelated same-topic chunks. See{' '}
                <span className="font-mono">integrity/FINDINGS.md</span> for the full
                investigation, including the actual similarity scores checked.
              </p>
            </div>
          )}
        </>
      )}
    </div>
  )
}
