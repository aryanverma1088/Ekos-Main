import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { Loading, ErrorState, EmptyState } from '../components/States'
import Stamp from '../components/Stamp'
import AuthorityLadder from '../components/AuthorityLadder'

export default function Documents() {
  const [documents, setDocuments] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [department, setDepartment] = useState('')
  const [status, setStatus] = useState('')

  useEffect(() => {
    setLoading(true)
    api
      .listDocuments({ department, status })
      .then(setDocuments)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [department, status])

  const departments = ['HR', 'IT-Security', 'Finance', 'Engineering', 'Projects']

  return (
    <div className="px-4 sm:px-10 py-7 sm:py-10 max-w-5xl">
      <header className="mb-6">
        <p className="text-[11px] font-mono uppercase tracking-wider text-muted mb-2">
          Document library
        </p>
        <h1 className="page-heading font-display text-4xl text-paper">Documents</h1>
      </header>

      <div className="flex gap-3 mb-6 flex-wrap">
        <select
          value={department}
          onChange={(e) => setDepartment(e.target.value)}
          className="bg-surface border border-border rounded-lg px-3 py-2 text-[13px] text-paper font-mono outline-none focus:border-verified shadow-sm"
        >
          <option value="">All departments</option>
          {departments.map((d) => (
            <option key={d} value={d}>{d}</option>
          ))}
        </select>

        <select
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          className="bg-surface border border-border rounded-lg px-3 py-2 text-[13px] text-paper font-mono outline-none focus:border-verified shadow-sm"
        >
          <option value="">All statuses</option>
          <option value="current">Current</option>
          <option value="superseded">Superseded</option>
        </select>
      </div>

      {loading && <Loading label="Loading documents" />}
      {error && <ErrorState message="Could not load documents" hint={error} />}

      {!loading && !error && documents.length === 0 && (
        <EmptyState title="No documents match these filters" />
      )}

      {!loading && !error && documents.length > 0 && (
        <div className="data-surface border border-border-soft rounded-xl divide-y divide-border-soft overflow-hidden shadow-sm">
          {documents.map((doc) => (
            <Link
              key={doc.id}
              to={`/documents/${doc.id}`}
              className="flex items-center gap-4 px-4 py-3 hover:bg-surface transition-colors"
            >
              <div className="flex-1 min-w-0">
                <p className="font-display text-[15px] text-paper truncate">{doc.title}</p>
                <p className="font-mono text-[11px] text-muted mt-0.5">
                  {doc.doc_key} · {doc.department} · {doc.doc_type} · v{doc.version}
                </p>
              </div>
              <AuthorityLadder level={doc.authority_level} label={doc.authority_label} compact />
              <Stamp variant={doc.status}>{doc.status}</Stamp>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
