import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { Loading, ErrorState } from '../components/States'
import ConflictCard from '../components/ConflictCard'

function StatBlock({ label, value, accent }) {
  return (
    <div className="data-surface border border-border-soft rounded-lg px-4 py-3">
      <p className="text-[11px] font-mono uppercase tracking-wider text-muted">{label}</p>
      <p
        className="font-display text-3xl mt-1"
        style={{ color: accent || 'var(--color-paper)' }}
      >
        {value}
      </p>
    </div>
  )
}

function DepartmentBars({ byDepartment }) {
  const entries = Object.entries(byDepartment)
  const max = Math.max(...entries.map(([, v]) => v), 1)

  return (
    <div className="space-y-2.5">
      {entries.map(([dept, count]) => (
        <div key={dept} className="flex items-center gap-3">
          <span className="w-28 shrink-0 text-[13px] text-paper-dim truncate">{dept}</span>
          <div className="flex-1 h-2 bg-surface-raised rounded-full overflow-hidden">
            <div
              className="h-full bg-verified rounded-full"
              style={{ width: `${(count / max) * 100}%` }}
            />
          </div>
          <span className="w-6 text-right font-mono text-[12px] text-muted">{count}</span>
        </div>
      ))}
    </div>
  )
}

export default function Dashboard() {
  const [metrics, setMetrics] = useState(null)
  const [conflicts, setConflicts] = useState([])
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([api.getDashboardMetrics(), api.listConflicts()])
      .then(([m, c]) => {
        setMetrics(m)
        setConflicts(c.slice(0, 2))
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="p-8"><Loading label="Loading dashboard" /></div>
  if (error) return <div className="p-8"><ErrorState message="Could not load dashboard" hint={error} /></div>

  const scoreKnown = metrics.knowledge_integrity_score !== null

  return (
    <div className="px-4 sm:px-10 py-7 sm:py-10 max-w-6xl">
      <header className="mb-8">
        <p className="text-[11px] font-mono uppercase tracking-wider text-muted mb-2">
          Knowledge governance overview
        </p>
        <h1 className="page-heading font-display text-4xl text-paper">Dashboard</h1>
      </header>

      {/* Hero: integrity score */}
      <div className="data-surface border border-border-soft rounded-xl px-6 py-6 mb-8 flex items-center gap-6 flex-wrap">
        <div
          className="score-ring w-24 h-24 rounded-full flex items-center justify-center shrink-0"
          style={{ '--score': scoreKnown ? `${metrics.knowledge_integrity_score}%` : '0%' }}
        >
          <span className="relative z-10 font-display text-2xl text-paper">
            {scoreKnown ? `${metrics.knowledge_integrity_score}%` : '—'}
          </span>
        </div>
        <div>
          <p className="font-display text-lg text-paper">Knowledge Integrity Score</p>
          <p className="text-[13px] text-muted mt-1 max-w-md">
            {scoreKnown
              ? 'Share of checked concepts with no unresolved conflict, across everything the integrity engine has examined so far.'
              : 'Not yet computed — the integrity engine has not found or ruled out any conflicts yet. Run scripts/build_integrity_engine.py.'}
          </p>
        </div>
      </div>

      {/* Stat strip */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 mb-8">
        <StatBlock label="Documents" value={metrics.documents} />
        <StatBlock label="Entities" value={metrics.knowledge_entities} />
        <StatBlock label="Relationships" value={metrics.relationships} />
        <StatBlock label="Conflicts" value={metrics.conflicts} accent={metrics.conflicts > 0 ? 'var(--color-conflict)' : undefined} />
        <StatBlock label="Duplicate Clusters" value={metrics.duplicate_clusters} />
        <StatBlock label="Outdated Docs" value={metrics.potentially_outdated_documents} accent={metrics.potentially_outdated_documents > 0 ? 'var(--color-outdated)' : undefined} />
      </div>

      <div className="grid md:grid-cols-2 gap-8">
        <section>
          <h2 className="font-display text-lg text-paper mb-4">Documents by department</h2>
          <DepartmentBars byDepartment={metrics.documents_by_department} />
        </section>

        <section>
          <h2 className="font-display text-lg text-paper mb-4">Recent findings</h2>
          {conflicts.length === 0 ? (
            <p className="text-sm text-muted">No conflicts detected.</p>
          ) : (
            <div className="space-y-4">
              {conflicts.map((c) => (
                <ConflictCard key={c.id} conflict={c} />
              ))}
              <Link
                to="/integrity"
                className="inline-block text-[13px] font-mono text-verified hover:underline"
              >
                View all in Integrity Center →
              </Link>
            </div>
          )}
        </section>
      </div>

      <p className="text-[11px] text-muted-soft mt-10 max-w-2xl leading-relaxed border-t border-border-soft pt-4">
        {metrics.note}
      </p>
    </div>
  )
}
