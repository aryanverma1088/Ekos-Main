import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { api } from '../api'
import { Loading, ErrorState } from '../components/States'
import Stamp from '../components/Stamp'
import AuthorityLadder from '../components/AuthorityLadder'

function MetaRow({ label, value }) {
  if (!value) return null
  return (
    <div className="flex justify-between py-1.5 border-b border-border-soft last:border-0">
      <span className="text-[12px] text-muted font-mono">{label}</span>
      <span className="text-[13px] text-paper-dim text-right">{value}</span>
    </div>
  )
}

export default function DocumentDetail() {
  const { id } = useParams()
  const [doc, setDoc] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    setLoading(true)
    api
      .getDocument(id)
      .then(setDoc)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [id])

  if (loading) return <div className="px-4 sm:px-8 py-6 sm:py-8"><Loading label="Loading document" /></div>
  if (error) return (
    <div className="px-4 sm:px-8 py-6 sm:py-8">
      <Link to="/documents" className="text-[13px] font-mono text-muted hover:text-paper">
        ← Documents
      </Link>
      <div className="mt-4">
        <ErrorState message="Could not load document" hint={error} />
      </div>
    </div>
  )

  return (
    <div className="px-4 sm:px-10 py-7 sm:py-10 max-w-5xl">
      <Link to="/documents" className="text-[13px] font-mono text-muted hover:text-paper">
        ← Documents
      </Link>

      <header className="mt-4 mb-8 flex items-start justify-between gap-4 flex-wrap">
        <div>
          <p className="text-[11px] font-mono uppercase tracking-wider text-muted mb-2">
            {doc.department} · {doc.doc_type}
          </p>
          <h1 className="page-heading font-display text-4xl text-paper">{doc.title}</h1>
          <p className="font-mono text-[12px] text-muted mt-2">{doc.doc_key}</p>
        </div>
        <div className="flex items-center gap-3">
          <AuthorityLadder level={doc.authority_level} label={doc.authority_label} />
          <Stamp variant={doc.status}>{doc.status}</Stamp>
        </div>
      </header>

      <div className="grid md:grid-cols-3 gap-8">
        <div className="md:col-span-2">
          <h2 className="font-display text-lg text-paper mb-3">Content</h2>
          <div className="data-surface border border-border-soft rounded-xl p-5 space-y-4 shadow-sm">
            {doc.chunks.map((c) => (
              <p key={c.id} className="text-[14px] text-paper-dim leading-relaxed whitespace-pre-wrap">
                {c.chunk_text}
              </p>
            ))}
          </div>
        </div>

        <aside>
          <h2 className="font-display text-lg text-paper mb-3">Metadata</h2>
          <div className="data-surface border border-border-soft rounded-xl px-4 py-2 shadow-sm">
            <MetaRow label="Version" value={doc.version} />
            <MetaRow label="Owner" value={doc.owner} />
            <MetaRow label="Author" value={doc.author} />
            <MetaRow label="Created" value={doc.created_date} />
            <MetaRow label="Effective" value={doc.effective_date} />
            <MetaRow label="Updated" value={doc.updated_date} />
            <MetaRow label="Tags" value={doc.tags} />
            {doc.supersedes_doc_key && (
              <MetaRow label="Supersedes" value={doc.supersedes_doc_key} />
            )}
          </div>
        </aside>
      </div>
    </div>
  )
}
