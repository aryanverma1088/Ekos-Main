import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { Loading, ErrorState, EmptyState } from '../components/States'
import Stamp from '../components/Stamp'
import AuthorityLadder from '../components/AuthorityLadder'

const METHODS = [
  { value: 'bm25', label: 'BM25', hint: 'Lexical (System A)' },
  { value: 'dense', label: 'Dense', hint: 'Semantic — LSA (System B)' },
  { value: 'hybrid', label: 'Hybrid', hint: 'RRF fusion (System C)' },
  { value: 'hybrid_rerank', label: 'Hybrid + Rerank', hint: 'Reranked (System D)' },
]

const SUGGESTIONS = [
  'What is the current remote work policy?',
  'How often must employees change their passwords?',
  'Who can approve production database access?',
]

const RELATION_LABEL = {
  conflicts_with: 'conflicts with',
  supersedes: 'supersedes',
  duplicate_of: 'duplicate of',
  owned_by: 'owned by',
  applies_to: 'applies to',
  references: 'references',
}

function ConfidenceMeter({ percent }) {
  return (
    <div className="flex items-center gap-2" title={`${percent}% of the top result's score for this query`}>
      <div className="w-14 h-1.5 rounded-full bg-surface-raised overflow-hidden">
        <div
          className="h-full rounded-full bg-verified"
          style={{ width: `${percent}%` }}
        />
      </div>
      <span className="font-mono text-[11px] text-muted">{percent}%</span>
    </div>
  )
}

function HighlightedSnippet({ text, query }) {
  const terms = query.trim().split(/\s+/).filter((term) => term.length > 2).slice(0, 6)
  if (!terms.length) return <>{text}</>
  const expression = new RegExp(`(${terms.map((term) => term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|')})`, 'gi')
  return text.split(expression).map((part, index) =>
    terms.some((term) => part.toLowerCase() === term.toLowerCase())
      ? <mark key={index}>{part}</mark>
      : <span key={index}>{part}</span>,
  )
}

function RelatedEntities({ entities }) {
  if (!entities || entities.length === 0) return null
  return (
    <div className="flex flex-wrap gap-1.5 mt-2">
      {entities.map((e, i) => (
        <span
          key={i}
          className="inline-flex items-center gap-1 text-[11px] font-mono px-2 py-0.5 rounded border"
          style={{
            borderColor: e.relation_type === 'conflicts_with' ? 'var(--color-conflict)' : 'var(--color-border-soft)',
            color: e.relation_type === 'conflicts_with' ? 'var(--color-conflict-paper)' : 'var(--color-muted)',
          }}
        >
          {RELATION_LABEL[e.relation_type] || e.relation_type} <span className="text-paper-dim">{e.name}</span>
        </span>
      ))}
    </div>
  )
}

function ResultCard({ result, query, onPreview }) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div className="result-card data-surface border border-border-soft rounded-xl p-5 hover:border-info/50">
      <div className="flex items-start justify-between gap-3 mb-2">
        <Link to={`/documents/${result.document_id}`} className="min-w-0 group">
          <p className="font-display text-base text-paper truncate group-hover:text-verified transition-colors">
            {result.title}
          </p>
          <p className="font-mono text-[11px] text-muted mt-0.5">
            {result.doc_key} · v{result.version} · {result.department}
          </p>
        </Link>
        <div className="flex items-center gap-2 shrink-0">
          {result.has_known_conflict && (
            <Stamp variant="high" title="This document has a detected integrity conflict">
              Conflict
            </Stamp>
          )}
          <Stamp variant={result.status}>{result.status}</Stamp>
          <button
            type="button"
            onClick={() => onPreview(result.document_id)}
            className="rounded-md border border-border-soft bg-surface px-2 py-1 text-[10px] font-mono text-muted hover:border-info/50 hover:text-info"
            aria-label={`Preview ${result.title}`}
          >
            Preview
          </button>
        </div>
      </div>

      <p className="text-[13px] text-paper-dim leading-relaxed line-clamp-2 mb-4"><HighlightedSnippet text={result.chunk_text} query={query} /></p>

      <div className="flex items-center justify-between flex-wrap gap-2 mb-1">
        <AuthorityLadder level={result.authority_level} label={result.authority_label} compact />
        <ConfidenceMeter percent={result.confidence_percent} />
      </div>

      <RelatedEntities entities={result.related_entities} />

      <button
        onClick={() => setExpanded((v) => !v)}
        aria-expanded={expanded}
        className="mt-3 text-[11px] font-mono text-muted hover:text-info flex items-center gap-1"
      >
        <span className={`transition-transform inline-block ${expanded ? 'rotate-90' : ''}`}>›</span>
        Why this ranked here
      </button>
      {expanded && (
        <p className="mt-2 text-[12px] text-paper-dim bg-surface-raised rounded-lg p-3 leading-relaxed animate-[content-rise_220ms_ease-out]">
          {result.ranking_explanation}
        </p>
      )}
    </div>
  )
}

export default function Search() {
  const [query, setQuery] = useState('')
  const [method, setMethod] = useState('hybrid_rerank')
  const [results, setResults] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const inputRef = useRef(null)
  const [preview, setPreview] = useState(null)
  const [previewLoading, setPreviewLoading] = useState(false)

  useEffect(() => {
    function handleShortcut(event) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        inputRef.current?.focus()
      }
    }
    window.addEventListener('keydown', handleShortcut)
    return () => window.removeEventListener('keydown', handleShortcut)
  }, [])

  async function runSearch(e) {
    e?.preventDefault()
    if (!query.trim()) return
    setLoading(true)
    setError(null)
    try {
      const res = await api.search(query, { method, topK: 10 })
      setResults(res)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  async function openPreview(documentId) {
    setPreviewLoading(true)
    try {
      setPreview(await api.getDocument(documentId))
    } catch (err) {
      setError(err.message)
    } finally {
      setPreviewLoading(false)
    }
  }

  return (
    <div className="px-4 sm:px-10 py-7 sm:py-10 max-w-4xl">
      <header className="mb-8">
        <p className="text-[11px] font-mono uppercase tracking-wider text-muted mb-2">
          Enterprise search
        </p>
        <div className="flex items-end justify-between gap-4">
          <h1 className="page-heading font-display text-4xl text-paper">Search</h1>
          <span className="hidden sm:inline-flex items-center gap-1.5 rounded-md border border-border-soft bg-surface/70 px-2 py-1 text-[10px] font-mono text-muted shadow-sm">
            <kbd className="text-paper">⌘</kbd><kbd className="text-paper">K</kbd> focus
          </span>
        </div>
      </header>

      <form onSubmit={runSearch} className="search-command mb-4 flex items-center gap-3 rounded-xl border border-border px-4 py-2">
        <label htmlFor="search-input" className="sr-only">Search the knowledge base</label>
        <svg className="h-5 w-5 shrink-0 text-info" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <circle cx="11" cy="11" r="6.5" stroke="currentColor" strokeWidth="1.8" />
          <path d="m16 16 4.5 4.5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
        </svg>
        <input
          ref={inputRef}
          id="search-input"
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="What is the current remote work policy?"
          autoComplete="off"
          className="min-w-0 flex-1 bg-transparent py-2 text-[14px] text-paper placeholder:text-muted-soft font-sans outline-none"
        />
        {query && <button type="button" onClick={() => setQuery('')} aria-label="Clear query" className="rounded-md p-1.5 text-muted hover:bg-ink-soft hover:text-paper">×</button>}
        <button type="submit" className="search-submit hidden sm:inline-flex items-center gap-2 rounded-lg px-3 py-2 text-[11px] font-semibold">Search <span className="text-white/60">↵</span></button>
      </form>

      {!results && !loading && !error && (
        <div className="mb-7 flex flex-wrap gap-2">
          {SUGGESTIONS.map((suggestion) => (
            <button key={suggestion} type="button" onClick={() => { setQuery(suggestion); inputRef.current?.focus() }} className="rounded-full border border-border-soft bg-surface/70 px-3 py-1.5 text-left text-[11px] text-muted shadow-sm transition hover:-translate-y-0.5 hover:border-info/50 hover:text-info">
              {suggestion}
            </button>
          ))}
        </div>
      )}

      <div className="flex gap-1 mb-6 border border-border-soft bg-surface rounded-lg p-1 w-fit flex-wrap shadow-sm" role="radiogroup" aria-label="Retrieval method">
        {METHODS.map((m) => (
          <button
            key={m.value}
            onClick={() => setMethod(m.value)}
            title={m.hint}
            role="radio"
            aria-checked={method === m.value}
            className={`px-3 py-1.5 rounded text-[13px] font-mono transition-colors ${
              method === m.value
                ? 'bg-verified-soft text-verified-paper'
                : 'text-muted hover:text-paper'
            }`}
          >
            {m.label}
          </button>
        ))}
      </div>

      {loading && <Loading label="Searching" />}
      {error && <ErrorState message="Search failed" hint={error} />}

      {results && !loading && (
        <>
          <p className="text-[13px] text-muted mb-4 font-mono">
            {results.results.length} result{results.results.length === 1 ? '' : 's'} · method: {results.method}
          </p>
          {results.results.length === 0 ? (
            <EmptyState title="No matches" body="Try a different query or retrieval method." />
          ) : (
            <div className="space-y-3">
              {results.results.map((r) => (
                <ResultCard key={r.chunk_id} result={r} query={query} onPreview={openPreview} />
              ))}
            </div>
          )}
        </>
      )}

      {!results && !loading && !error && (
        <EmptyState
          title="Search the knowledge base"
          body='Try "How often must employees change their passwords?" to see how EKOS surfaces conflicting sources rather than picking one silently.'
        />
      )}

      {previewLoading && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-paper/10 backdrop-blur-sm">
          <div className="rounded-xl border border-border-soft bg-surface px-5 py-4 text-[11px] font-mono text-muted shadow-xl">Loading document preview...</div>
        </div>
      )}

      {preview && (
        <div className="drawer-backdrop fixed inset-0 z-50 bg-paper/20 backdrop-blur-sm" onClick={() => setPreview(null)}>
          <aside
            className="document-drawer absolute right-0 top-0 h-full w-full max-w-xl overflow-y-auto border-l border-border-soft bg-ink px-6 py-7 shadow-2xl sm:px-8"
            onClick={(event) => event.stopPropagation()}
            role="dialog"
            aria-modal="true"
            aria-label="Document preview"
          >
            <div className="mb-8 flex items-start justify-between gap-4">
              <div>
                <p className="mb-2 text-[10px] font-mono uppercase tracking-[0.16em] text-info">Document preview</p>
                <h2 className="max-w-sm text-2xl font-semibold tracking-tight text-paper">{preview.title}</h2>
                <p className="mt-2 text-[11px] font-mono text-muted">{preview.doc_key} · v{preview.version}</p>
              </div>
              <button type="button" onClick={() => setPreview(null)} className="rounded-lg border border-border-soft bg-surface px-3 py-2 text-sm text-muted hover:text-paper" aria-label="Close preview">×</button>
            </div>
            <div className="mb-7 flex flex-wrap gap-2">
              <Stamp variant={preview.status}>{preview.status}</Stamp>
              <span className="rounded-full border border-border-soft bg-surface px-2.5 py-1 text-[10px] font-mono text-muted">{preview.department}</span>
              <span className="rounded-full border border-border-soft bg-surface px-2.5 py-1 text-[10px] font-mono text-muted">{preview.doc_type}</span>
            </div>
            <div className="space-y-5 text-[14px] leading-7 text-paper-dim">
              {preview.chunks?.map((chunk) => <p key={chunk.id}>{chunk.chunk_text}</p>)}
            </div>
            <Link to={`/documents/${preview.id}`} onClick={() => setPreview(null)} className="mt-8 inline-flex items-center rounded-lg bg-paper px-4 py-2.5 text-[12px] font-semibold text-white transition hover:bg-info">Open full document <span className="ml-2">↗</span></Link>
          </aside>
        </div>
      )}
    </div>
  )
}
