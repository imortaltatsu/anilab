import { useState, useMemo } from 'react'
import {
  FolderOpen,
  Search,
  Eye,
  Play,
  Download,
  Trash2,
  RefreshCw,
  X,
  ZoomIn,
} from 'lucide-react'
import type { Job } from './api'
import { api } from './api'
import { JobImageThumbnail, invalidateJobImageCache } from './JobImageThumbnail'

type FilterStatus = 'all' | 'completed' | 'active' | 'failed'

type Props = {
  jobs: Job[]
  activeJobId: number | null
  onSelectJob: (jobId: number) => void
  onAnimateJob: (jobId: number) => void
  onDeleteJob: (jobId: number) => Promise<void>
  onRefresh: () => Promise<void>
}

export function AssetBrowserView({
  jobs,
  activeJobId,
  onSelectJob,
  onAnimateJob,
  onDeleteJob,
  onRefresh,
}: Props) {
  const [filter, setFilter] = useState<FilterStatus>('all')
  const [search, setSearch] = useState('')
  const [inspectModalJob, setInspectModalJob] = useState<Job | null>(null)
  const [deletingId, setDeletingId] = useState<number | null>(null)
  const [refreshing, setRefreshing] = useState(false)

  const counts = useMemo(() => {
    return {
      all: jobs.length,
      completed: jobs.filter((j) => j.status === 'completed').length,
      active: jobs.filter((j) => j.status === 'queued' || j.status === 'running').length,
      failed: jobs.filter((j) => j.status === 'failed').length,
    }
  }, [jobs])

  const filteredJobs = useMemo(() => {
    return jobs.filter((j) => {
      if (filter === 'completed' && j.status !== 'completed') return false
      if (filter === 'active' && j.status !== 'queued' && j.status !== 'running') return false
      if (filter === 'failed' && j.status !== 'failed') return false
      if (search.trim()) {
        const q = search.toLowerCase()
        const promptMatch = j.prompt?.toLowerCase().includes(q)
        const idMatch = String(j.id).includes(q)
        const modeMatch = j.mode.toLowerCase().includes(q)
        if (!promptMatch && !idMatch && !modeMatch) return false
      }
      return true
    })
  }, [jobs, filter, search])

  async function handleRefresh() {
    setRefreshing(true)
    try {
      await onRefresh()
    } finally {
      setRefreshing(false)
    }
  }

  async function handleDelete(e: React.MouseEvent, jobId: number) {
    e.stopPropagation()
    if (!window.confirm(`Are you sure you want to permanently delete Asset #${jobId}? This cannot be undone.`)) {
      return
    }
    setDeletingId(jobId)
    try {
      invalidateJobImageCache(jobId)
      await onDeleteJob(jobId)
    } catch (err) {
      alert(err instanceof Error ? err.message : String(err))
    } finally {
      setDeletingId(null)
    }
  }

  return (
    <div className="asset-browser-view">
      {/* Top Header Bar */}
      <div className="asset-browser-header">
        <div className="asset-browser-title">
          <h2>
            <FolderOpen size={20} style={{ color: 'var(--accent)' }} />
            <span>Asset Library</span>
          </h2>
          <p>
            Review generated 3D meshes, inspect 2D concept silhouettes, and manage your game-ready asset library.
          </p>
        </div>

        {/* Search, Filters, and Actions */}
        <div className="asset-browser-controls">
          {/* Status Tabs */}
          <div className="asset-browser-filter-tabs">
            <button
              type="button"
              className={`asset-browser-filter-tab ${filter === 'all' ? 'active' : ''}`}
              onClick={() => setFilter('all')}
            >
              All ({counts.all})
            </button>
            <button
              type="button"
              className={`asset-browser-filter-tab ${filter === 'completed' ? 'active' : ''}`}
              onClick={() => setFilter('completed')}
            >
              Ready ({counts.completed})
            </button>
            <button
              type="button"
              className={`asset-browser-filter-tab ${filter === 'active' ? 'active' : ''}`}
              onClick={() => setFilter('active')}
            >
              Generating ({counts.active})
            </button>
            {counts.failed > 0 && (
              <button
                type="button"
                className={`asset-browser-filter-tab ${filter === 'failed' ? 'active' : ''}`}
                onClick={() => setFilter('failed')}
              >
                Failed ({counts.failed})
              </button>
            )}
          </div>

          {/* Search Box */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', background: 'var(--bg-surface)', boxShadow: 'var(--shadow-inset-sm)', borderRadius: 'var(--radius-pill)', padding: '4px 12px' }}>
            <Search size={13} style={{ color: 'var(--text-dim)' }} />
            <input
              type="text"
              placeholder="Search assets…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              style={{
                border: 'none',
                boxShadow: 'none',
                padding: '2px',
                background: 'transparent',
                fontSize: '12px',
                width: '130px',
              }}
            />
          </div>

          {/* Refresh Button */}
          <button
            type="button"
            className="ghost"
            style={{ padding: '6px 12px', minHeight: '32px' }}
            onClick={handleRefresh}
            disabled={refreshing}
            title="Refresh library"
          >
            <RefreshCw size={12} className={refreshing ? 'spin' : ''} />
            <span>Refresh</span>
          </button>

          {/* Clear Failed */}
          {counts.failed > 0 && (
            <button
              type="button"
              className="danger"
              style={{ padding: '6px 12px', minHeight: '32px', fontSize: '11px' }}
              onClick={async () => {
                if (window.confirm('Delete all failed generation attempts?')) {
                  await api.deleteFailedJobs()
                  await onRefresh()
                }
              }}
            >
              <Trash2 size={11} />
              <span>Clear Failed ({counts.failed})</span>
            </button>
          )}
        </div>
      </div>

      {/* Grid of Asset Cards */}
      <div className="asset-browser-grid">
        {filteredJobs.map((job) => {
          const isActive = activeJobId === job.id
          const isDone = job.status === 'completed'
          const isDeleting = deletingId === job.id

          return (
            <div
              key={job.id}
              className={`asset-card ${isActive ? 'active' : ''}`}
              style={{ opacity: isDeleting ? 0.4 : 1 }}
            >
              {/* Media Container */}
              <div
                className="asset-card-media"
                onClick={() => setInspectModalJob(job)}
                title="Click to inspect concept reference image"
              >
                <JobImageThumbnail job={job} style={{ width: '100%', height: '100%' }} />

                {/* Status Badge */}
                <span className={`asset-card-status ${job.status}`}>
                  {job.status === 'completed'
                    ? 'Ready'
                    : job.status === 'running'
                      ? 'Synthesizing…'
                      : job.status === 'queued'
                        ? 'Queued'
                        : 'Failed'}
                </span>

                {/* Hover overlay */}
                <div className="approval-preview-overlay">
                  <ZoomIn size={14} />
                  <span>Inspect Image</span>
                </div>
              </div>

              {/* Info Details */}
              <div className="asset-card-info">
                <div className="asset-card-title-row">
                  <span className="asset-card-title">
                    Asset #{job.id}
                  </span>
                  <span className="asset-meta-chip">
                    {job.mode === 'text' ? 'Text → 3D' : job.mode === 'image' ? 'Image → 3D' : 'Auto-Rig'}
                  </span>
                </div>

                <div className="asset-card-prompt" title={job.prompt || undefined}>
                  {job.prompt || (job.mode === 'rig' ? 'Static 3D Mesh Auto-Rig' : 'Image Reference to 3D Mesh')}
                </div>

                <div className="asset-card-meta-chips">
                  <span className="asset-meta-chip">~35k Faces</span>
                  <span className="asset-meta-chip">4K UV Atlas</span>
                  {job.seed != null && <span className="asset-meta-chip">Seed {job.seed}</span>}
                </div>
              </div>

              {/* Actions Bar */}
              <div className="asset-card-actions">
                {isDone && (
                  <>
                    <button
                      type="button"
                      className="primary"
                      style={{ flex: 2, padding: '5px 8px', fontSize: '11px', minHeight: '32px' }}
                      onClick={() => onSelectJob(job.id)}
                      title="Load into 3D Viewport"
                    >
                      <Eye size={12} />
                      <span>View 3D</span>
                    </button>
                    <button
                      type="button"
                      className="ghost"
                      style={{ flex: 1, padding: '5px 8px', fontSize: '11px', minHeight: '32px' }}
                      onClick={() => onAnimateJob(job.id)}
                      title="Test motion & animations"
                    >
                      <Play size={11} />
                      <span>Motion</span>
                    </button>
                    <button
                      type="button"
                      className="ghost"
                      style={{ padding: '5px 8px', fontSize: '11px', minHeight: '32px' }}
                      onClick={() => api.downloadGlb(job.id)}
                      title="Download game-ready .GLB file"
                    >
                      <Download size={12} />
                    </button>
                  </>
                )}

                {/* Delete Button */}
                <button
                  type="button"
                  className="danger"
                  style={{
                    padding: '5px 8px',
                    fontSize: '11px',
                    minHeight: '32px',
                    marginLeft: isDone ? 'auto' : 0,
                    width: isDone ? 'auto' : '100%',
                  }}
                  disabled={isDeleting || job.status === 'running'}
                  onClick={(e) => handleDelete(e, job.id)}
                  title="Permanently delete asset from storage"
                >
                  <Trash2 size={12} />
                  {!isDone && <span>Delete Asset</span>}
                </button>
              </div>
            </div>
          )
        })}

        {filteredJobs.length === 0 && (
          <div
            style={{
              gridColumn: '1 / -1',
              textAlign: 'center',
              padding: '60px 20px',
              color: 'var(--text-muted)',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: '12px',
            }}
          >
            <FolderOpen size={40} style={{ color: 'var(--text-dim)', opacity: 0.6 }} />
            <div style={{ fontSize: '15px', fontWeight: 700, color: 'var(--text-primary)' }}>
              {search ? 'No matching assets found' : 'No assets in this category'}
            </div>
            <p style={{ fontSize: '12px', maxWidth: '360px', margin: '0 auto', lineHeight: 1.5 }}>
              {search
                ? `No assets matched "${search}". Try searching for a different prompt or ID.`
                : 'Generate a character using the AI Gen Studio tab to build your 3D asset library.'}
            </p>
          </div>
        )}
      </div>

      {/* Image Inspection Lightbox Modal */}
      {inspectModalJob && (
        <div className="modal-backdrop" onClick={() => setInspectModalJob(null)}>
          <div
            className="modal-box"
            style={{ width: 'min(640px, 95vw)', textAlign: 'center' }}
            onClick={(e) => e.stopPropagation()}
          >
            <button
              type="button"
              className="modal-close-btn"
              onClick={() => setInspectModalJob(null)}
              aria-label="Close Preview"
            >
              <X size={16} />
            </button>

            <h4 style={{ fontSize: '18px', fontWeight: 800, marginBottom: '4px' }}>
              Asset #{inspectModalJob.id} Reference Image
            </h4>
            <p style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '14px' }}>
              {inspectModalJob.prompt || (inspectModalJob.mode === 'rig' ? 'Static Mesh Auto-Rig' : 'Reference Image Input')}
            </p>

            <div
              style={{
                height: 'min(420px, 60vh)',
                width: '100%',
                borderRadius: 'var(--radius-sm)',
                overflow: 'hidden',
                boxShadow: 'var(--shadow-inset)',
                background: 'radial-gradient(circle, #252b36 0%, #151821 100%)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                padding: '12px',
                marginBottom: '18px',
              }}
            >
              <JobImageThumbnail
                job={inspectModalJob}
                style={{ width: '100%', height: '100%' }}
              />
            </div>

            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '10px' }}>
              {inspectModalJob.status === 'completed' && (
                <>
                  <button
                    type="button"
                    className="primary"
                    onClick={() => {
                      onSelectJob(inspectModalJob.id)
                      setInspectModalJob(null)
                    }}
                  >
                    <Eye size={13} />
                    <span>Open in 3D Viewport</span>
                  </button>
                  <button
                    type="button"
                    className="ghost"
                    onClick={() => api.downloadGlb(inspectModalJob.id)}
                  >
                    <Download size={13} />
                    <span>Download .GLB</span>
                  </button>
                </>
              )}
              <button
                type="button"
                className="danger"
                onClick={(e) => {
                  const id = inspectModalJob.id
                  setInspectModalJob(null)
                  handleDelete(e, id)
                }}
              >
                <Trash2 size={13} />
                <span>Delete Asset</span>
              </button>
              <button
                type="button"
                className="ghost"
                onClick={() => setInspectModalJob(null)}
              >
                <span>Close</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
