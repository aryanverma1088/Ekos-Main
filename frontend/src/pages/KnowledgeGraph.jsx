import { useEffect, useRef, useState } from 'react'
import { forceSimulation, forceLink, forceManyBody, forceCenter, forceCollide } from 'd3-force'
import { api } from '../api'
import { Loading, ErrorState, EmptyState } from '../components/States'

const WIDTH = 760
const HEIGHT = 560

const TYPE_STYLE = {
  Department: { fill: 'var(--color-verified)', r: 9, shape: 'circle' },
  Team: { fill: 'var(--color-verified)', r: 7, shape: 'diamond' },
  Person: { fill: 'var(--color-info)', r: 7, shape: 'circle' },
  Group: { fill: 'var(--color-outdated)', r: 8, shape: 'circle' },
  Project: { fill: 'var(--color-info)', r: 7, shape: 'hexagon' },
  Concept: { fill: 'none', stroke: 'var(--color-paper-dim)', r: 7, shape: 'circle-outline' },
  Policy: { fill: 'var(--color-paper)', r: 6, shape: 'square' },
  Process: { fill: 'var(--color-paper)', r: 6, shape: 'square' },
  Documentation: { fill: 'var(--color-paper-dim)', r: 6, shape: 'square' },
  Document: { fill: 'var(--color-paper-dim)', r: 6, shape: 'square' },
}

const RELATION_COLOR = {
  supersedes: 'var(--color-outdated)',
  conflicts_with: 'var(--color-conflict)',
  duplicate_of: 'var(--color-conflict)',
  references: 'var(--color-info)',
  manages: 'var(--color-verified)',
  defines: 'var(--color-paper-dim)',
}
// conflicts_with/duplicate_of are the most important signal in the graph --
// literally where the organization's documented knowledge disagrees with
// itself -- so they render thicker and dashed rather than blending in with
// ordinary structural edges (owned_by, applies_to, etc).
const EMPHASIZED_RELATIONS = new Set(['conflicts_with', 'duplicate_of'])
const DEFAULT_EDGE_COLOR = 'var(--color-border)'

function polygonPoints(shape, r) {
  if (shape === 'diamond') {
    return `0,${-r} ${r},0 0,${r} ${-r},0`
  }
  if (shape === 'hexagon') {
    const pts = []
    for (let i = 0; i < 6; i++) {
      const angle = (Math.PI / 3) * i - Math.PI / 2
      pts.push(`${(r * Math.cos(angle)).toFixed(2)},${(r * Math.sin(angle)).toFixed(2)}`)
    }
    return pts.join(' ')
  }
  return ''
}

function layoutGraph(nodes, edges) {
  const simNodes = nodes.map((n) => ({ ...n }))
  const simLinks = edges.map((e) => ({ ...e, source: e.source, target: e.target }))

  const PADDING = 24

  const sim = forceSimulation(simNodes)
    .force('link', forceLink(simLinks).id((d) => d.id).distance(70).strength(0.4))
    .force('charge', forceManyBody().strength(-140))
    .force('center', forceCenter(WIDTH / 2, HEIGHT / 2))
    .force('collide', forceCollide().radius(26))
    .stop()

  for (let i = 0; i < 300; i++) {
    sim.tick()
    // forceCenter only pulls toward center on average -- it doesn't hard-bound
    // individual nodes, so a weakly-connected node (e.g. a Team with only one
    // relationship) can still drift past the canvas edge and render clipped
    // (invisible, per SVG's default overflow:hidden) with its edges pointing
    // off-canvas. Clamp every tick, not just at the end, so the collision
    // force still sees accurate positions for nodes sitting at the boundary.
    for (const node of simNodes) {
      node.x = Math.max(PADDING, Math.min(WIDTH - PADDING, node.x))
      node.y = Math.max(PADDING, Math.min(HEIGHT - PADDING, node.y))
    }
  }

  return { nodes: simNodes, links: simLinks }
}

export default function KnowledgeGraph() {
  const [raw, setRaw] = useState(null)
  const [laid, setLaid] = useState(null)
  const [selected, setSelected] = useState(null)
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  function loadFullGraph() {
    setLoading(true)
    setError(null)
    api
      .getGraph()
      .then((g) => {
        setRaw(g)
        setLaid(layoutGraph(g.nodes, g.edges))
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(loadFullGraph, [])

  async function searchNeighborhood(e) {
    e.preventDefault()
    if (!query.trim()) return
    setLoading(true)
    setError(null)
    try {
      const g = await api.getGraph({ entity_name: query, depth: 1 })
      setRaw(g)
      setLaid(layoutGraph(g.nodes, g.edges))
      setSelected(null)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const selectedEdges = selected
    ? laid.links.filter((l) => l.source.id === selected.id || l.target.id === selected.id)
    : []

  return (
    <div className="px-4 sm:px-10 py-7 sm:py-10">
      <header className="mb-6">
        <p className="text-[11px] font-mono uppercase tracking-wider text-muted mb-2">
          Entity relationships
        </p>
        <h1 className="page-heading font-display text-4xl text-paper">Knowledge Graph</h1>
      </header>

      <div className="flex items-center gap-3 mb-6 flex-wrap">
        <form onSubmit={searchNeighborhood} className="flex gap-2">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="e.g. hr-remote-work-policy-v4"
            className="bg-surface border border-border rounded-lg px-3 py-2 text-[13px] text-paper placeholder:text-muted-soft font-mono outline-none focus:border-verified w-72 shadow-sm"
          />
          <button
            type="submit"
            className="px-3 py-2 rounded-lg border border-border bg-surface text-[13px] font-mono text-paper hover:border-verified shadow-sm"
          >
            Explore
          </button>
        </form>
        <button
          onClick={loadFullGraph}
          className="px-3 py-2 rounded-lg border border-border-soft bg-surface text-[13px] font-mono text-muted hover:text-paper shadow-sm"
        >
          Show full graph
        </button>
      </div>

      {loading && <Loading label="Loading graph" />}
      {error && <ErrorState message="Could not load graph" hint={error} />}

      {!loading && !error && laid && laid.nodes.length === 0 && (
        <EmptyState
          title="No graph data yet"
          body="Run scripts/build_knowledge_graph.py after ingesting documents to populate entities and relationships."
        />
      )}

      {!loading && !error && laid && laid.nodes.length > 0 && (
        <div className="flex gap-6 flex-wrap lg:flex-nowrap">
          <div className="data-surface border border-border-soft rounded-xl overflow-x-auto shrink-0 max-w-full shadow-sm">
            <svg width={WIDTH} height={HEIGHT}>
              <g>
                {laid.links.map((l, i) => {
                  const emphasized = EMPHASIZED_RELATIONS.has(l.relation_type)
                  return (
                    <line
                      key={i}
                      x1={l.source.x}
                      y1={l.source.y}
                      x2={l.target.x}
                      y2={l.target.y}
                      stroke={RELATION_COLOR[l.relation_type] || DEFAULT_EDGE_COLOR}
                      strokeWidth={emphasized ? 2.5 : 1}
                      strokeDasharray={emphasized ? '5,3' : undefined}
                      opacity={emphasized ? 0.9 : 0.55}
                    />
                  )
                })}
              </g>
              <g>
                {laid.nodes.map((n) => {
                  const style = TYPE_STYLE[n.entity_type] || TYPE_STYLE.Document
                  const isSelected = selected?.id === n.id
                  const r = isSelected ? style.r + 3 : style.r
                  const strokeColor = isSelected ? 'var(--color-verified)' : (style.stroke || 'none')
                  const strokeWidth = isSelected ? 2 : (style.stroke ? 1.5 : 0)

                  return (
                    <g
                      key={n.id}
                      transform={`translate(${n.x},${n.y})`}
                      onClick={() => setSelected(n)}
                      className="cursor-pointer"
                      role="button"
                      tabIndex={0}
                      aria-label={`${n.entity_type}: ${n.name}`}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setSelected(n) }
                      }}
                    >
                      {style.shape === 'circle' || style.shape === 'circle-outline' ? (
                        <circle r={r} fill={style.fill} stroke={strokeColor} strokeWidth={strokeWidth} />
                      ) : style.shape === 'diamond' || style.shape === 'hexagon' ? (
                        <polygon
                          points={polygonPoints(style.shape, r)}
                          fill={style.fill}
                          stroke={strokeColor}
                          strokeWidth={strokeWidth}
                        />
                      ) : (
                        <rect
                          x={-r} y={-r} width={r * 2} height={r * 2}
                          fill={style.fill}
                          stroke={strokeColor}
                          strokeWidth={strokeWidth}
                        />
                      )}
                    </g>
                  )
                })}
              </g>
            </svg>
          </div>

          <aside className="flex-1 min-w-64">
            {!selected ? (
              <div className="text-sm text-muted space-y-4">
                <p>Click a node to inspect it.</p>
                <div className="space-y-1.5 text-[12px] font-mono">
                  <p><span className="inline-block w-2.5 h-2.5 rounded-full bg-verified mr-2 align-middle" />Department</p>
                  <p><span className="inline-block w-2.5 h-2.5 bg-verified mr-2 align-middle" style={{ clipPath: 'polygon(50% 0%, 100% 50%, 50% 100%, 0% 50%)' }} />Team</p>
                  <p><span className="inline-block w-2.5 h-2.5 rounded-full mr-2 align-middle" style={{ background: 'var(--color-info)' }} />Person</p>
                  <p><span className="inline-block w-2.5 h-2.5 mr-2 align-middle" style={{ background: 'var(--color-info)', clipPath: 'polygon(25% 0%, 75% 0%, 100% 50%, 75% 100%, 25% 100%, 0% 50%)' }} />Project</p>
                  <p><span className="inline-block w-2.5 h-2.5 rounded-full mr-2 align-middle" style={{ background: 'var(--color-outdated)' }} />Group</p>
                  <p><span className="inline-block w-2.5 h-2.5 rounded-full mr-2 align-middle border" style={{ borderColor: 'var(--color-paper-dim)' }} />Concept</p>
                  <p><span className="inline-block w-2.5 h-2.5 mr-2 align-middle" style={{ background: 'var(--color-paper)' }} />Document</p>
                </div>
                <div className="pt-2 border-t border-border-soft space-y-1.5 text-[12px] font-mono">
                  <p className="text-paper-dim normal-case font-sans text-[11px] mb-2">Relationship emphasis</p>
                  <p className="flex items-center gap-2">
                    <svg width="20" height="8"><line x1="0" y1="4" x2="20" y2="4" stroke="var(--color-conflict)" strokeWidth="2.5" strokeDasharray="5,3" /></svg>
                    Conflicts / duplicates
                  </p>
                  <p className="flex items-center gap-2">
                    <svg width="20" height="8"><line x1="0" y1="4" x2="20" y2="4" stroke="var(--color-border)" strokeWidth="1" /></svg>
                    Structural (owns, applies to, etc.)
                  </p>
                </div>
              </div>
            ) : (
              <div>
                <p className="text-[11px] font-mono uppercase tracking-wider text-muted mb-1">
                  {selected.entity_type}
                </p>
                <h2 className="font-display text-xl text-paper mb-4">{selected.name}</h2>

                <p className="text-[12px] font-mono text-muted mb-2">
                  {selectedEdges.length} relationship{selectedEdges.length === 1 ? '' : 's'}
                </p>
                <div className="space-y-2">
                  {selectedEdges.map((e, i) => {
                    const isSource = e.source.id === selected.id
                    const other = isSource ? e.target : e.source
                    return (
                      <div key={i} className="text-[13px] border-b border-border-soft pb-2">
                        <span className="font-mono text-[11px]" style={{ color: RELATION_COLOR[e.relation_type] || 'var(--color-muted)' }}>
                          {isSource ? `→ ${e.relation_type}` : `← ${e.relation_type}`}
                        </span>
                        <p className="text-paper-dim mt-0.5">{other.name}</p>
                      </div>
                    )
                  })}
                </div>
              </div>
            )}
          </aside>
        </div>
      )}
    </div>
  )
}
