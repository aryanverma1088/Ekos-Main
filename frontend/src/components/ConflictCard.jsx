import Stamp from './Stamp'
import AuthorityLadder from './AuthorityLadder'

function SourceColumn({ chunk, value, showValue, isAuthoritative }) {
  return (
    <div
      className="flex-1 min-w-0 rounded-md border p-4"
      style={{
        borderColor: isAuthoritative ? 'var(--color-verified)' : 'var(--color-border)',
        backgroundColor: isAuthoritative ? 'var(--color-verified-soft)' : 'var(--color-surface-raised)',
      }}
    >
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="min-w-0">
          <p className="font-display text-sm text-paper truncate">{chunk.title}</p>
          <p className="font-mono text-[11px] text-muted mt-0.5">{chunk.doc_key}</p>
        </div>
        {isAuthoritative && <Stamp variant="current">Authoritative</Stamp>}
      </div>
      <AuthorityLadder level={chunk.authority_level} label={chunk.authority_label} compact />
      {showValue && value && (
        <p className="font-mono text-lg text-paper mt-3 font-semibold">{value}</p>
      )}
      <p className="text-[13px] text-paper-dim mt-2 leading-snug line-clamp-3">
        {chunk.chunk_text}
      </p>
    </div>
  )
}

export default function ConflictCard({ conflict, caseId, detectionMethod }) {
  const aWins = conflict.resolved_doc_key === conflict.chunk_a.doc_key
  const bWins = conflict.resolved_doc_key === conflict.chunk_b.doc_key
  // Short numeric facts ("90 days", "$250") deserve the large mono callout;
  // full definition sentences don't -- they'd duplicate the chunk text below
  // in an oversized monospace block. Only show the callout for contradictions.
  const showValue = conflict.conflict_type === 'contradiction'

  return (
    <div className="data-surface rounded-xl border border-border p-5 shadow-sm">
      <div className="flex items-center justify-between mb-4 gap-3 flex-wrap">
        <div>
          <p className="text-[11px] font-mono uppercase tracking-wider text-muted mb-1">
            {caseId && <span className="text-paper-dim mr-2">{caseId}</span>}
            {conflict.conflict_type === 'definition' ? 'Definition conflict' : 'Contradiction'}
          </p>
          <h3 className="font-display text-xl text-paper">{conflict.concept}</h3>
        </div>
        <Stamp variant={conflict.severity}>{conflict.severity} severity</Stamp>
      </div>

      <div className="flex gap-3 flex-col sm:flex-row">
        <SourceColumn chunk={conflict.chunk_a} value={conflict.value_a} showValue={showValue} isAuthoritative={aWins} />
        <div className="flex items-center justify-center px-1 shrink-0">
          <span className="font-mono text-muted text-sm">vs</span>
        </div>
        <SourceColumn chunk={conflict.chunk_b} value={conflict.value_b} showValue={showValue} isAuthoritative={bWins} />
      </div>

      {conflict.resolved_doc_key ? (
        <p className="mt-4 text-[13px] text-verified-paper leading-relaxed">
          → {conflict.resolution_reason}
        </p>
      ) : (
        <p className="mt-4 text-[13px] text-muted leading-relaxed">
          → {conflict.resolution_reason}
        </p>
      )}

      {detectionMethod && (
        <p className="mt-3 pt-3 border-t border-border-soft text-[11px] font-mono text-muted-soft">
          Detected via: {detectionMethod}
        </p>
      )}
    </div>
  )
}
