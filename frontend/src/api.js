const BASE = '/api'

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail || `Request failed: ${res.status}`)
  }
  return res.json()
}

function qs(params) {
  const entries = Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== '')
  if (!entries.length) return ''
  return '?' + new URLSearchParams(entries).toString()
}

export const api = {
  // documents
  listDocuments: (filters = {}) => request(`/documents${qs(filters)}`),
  getDocument: (id) => request(`/documents/${id}`),
  uploadDocument: (file) => {
    const form = new FormData()
    form.append('file', file)
    return fetch(`${BASE}/documents/upload`, { method: 'POST', body: form }).then((r) => r.json())
  },

  // dashboard
  getDashboardMetrics: () => request('/dashboard/metrics'),

  // search
  search: (q, { topK = 10, method = 'hybrid_rerank' } = {}) =>
    request(`/search${qs({ q, top_k: topK, method })}`),

  // knowledge graph
  listEntities: (filters = {}) => request(`/knowledge/entities${qs(filters)}`),
  getEntity: (id) => request(`/knowledge/entities/${id}`),
  getGraph: (params = {}) => request(`/knowledge/graph${qs(params)}`),

  // integrity
  listConflicts: (filters = {}) => request(`/integrity/conflicts${qs(filters)}`),
  listDuplicates: () => request('/integrity/duplicates'),
  listOutdated: () => request('/integrity/outdated'),
  listDefinitions: () => request('/integrity/definitions'),
}
