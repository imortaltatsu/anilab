import { useEffect, useRef, useState, useMemo } from 'react'
import {
  Terminal,
  Grid,
  CheckCircle2,
  Clock,
  RotateCcw,
  Download,
  Play,
  Eye,
  Search,
  Trash2,
  Sparkles,
  ChevronDown,
  ChevronUp,
  AlertCircle,
  Activity,
  Cpu,
  X,
} from 'lucide-react'
import type { Job } from './api'
import { api } from './api'
import { JobImageThumbnail } from './JobImageThumbnail'

type Props = {
  jobs: Job[]
  activeJobId: number | null
  onSelectJob: (jobId: number) => void
  onAnimateJob: (jobId: number) => void
  onDeleteJob?: (jobId: number) => Promise<void>
  onRefresh: () => Promise<void>
}

type Tab = 'pipeline' | 'assets'

const STAGES = [
  { id: 'prep', label: '1. Reference Prep' },
  { id: 'shape', label: '2. Neural Shape (35k)' },
  { id: 'texture', label: '3. 4K UV Atlas' },
  { id: 'rig', label: '4. Skeletal Rig' },
]

export function AIConsoleBrowser({
  jobs,
  activeJobId,
  onSelectJob,
  onAnimateJob,
  onDeleteJob,
  onRefresh,
}: Props) {
  const [activeTab, setActiveTab] = useState<Tab>('pipeline')
  const [selectedJobId, setSelectedJobId] = useState<number | null>(null)
  const [showRawLogs, setShowRawLogs] = useState(false)
  const [logSearch, setLogSearch] = useState('')
  const [logs, setLogs] = useState<Record<number, string>>({})
  const [elapsedSeconds, setElapsedSeconds] = useState(0)
  const logPreRef = useRef<HTMLPreElement | null>(null)

  // Rebake Modal State
  const [rebakeModalJob, setRebakeModalJob] = useState<Job | null>(null)
  const [rebakeYaw, setRebakeYaw] = useState(0)
  const [rebakePitch, setRebakePitch] = useState(0)
  const [rebakeUvSize, setRebakeUvSize] = useState(2048)
  const [rebakeInpaintMode, setRebakeInpaintMode] = useState<'uv' | 'view'>('uv')
  const [rebakeSteps, setRebakeSteps] = useState(50)
  const [isRebaking, setIsRebaking] = useState(false)
  const [rebakeError, setRebakeError] = useState<string | null>(null)

  const activeJobs = useMemo(() => jobs.filter((j) => j.status === 'queued' || j.status === 'running'), [jobs])
  const completedJobs = useMemo(() => jobs.filter((j) => j.status === 'completed'), [jobs])
  const failedJobs = useMemo(() => jobs.filter((j) => j.status === 'failed'), [jobs])

  // Determine currently inspected job: user selection -> active running job -> activeJobId -> latest job
  const inspectedJob = useMemo(() => {
    if (selectedJobId != null) {
      const found = jobs.find((j) => j.id === selectedJobId)
      if (found) return found
    }
    if (activeJobs.length > 0) return activeJobs[0]
    if (activeJobId != null) {
      const found = jobs.find((j) => j.id === activeJobId)
      if (found) return found
    }
    return jobs[0] ?? null
  }, [selectedJobId, jobs, activeJobs, activeJobId])

  // Live timer for active running job
  useEffect(() => {
    if (inspectedJob?.status !== 'running') {
      setElapsedSeconds(0)
      return
    }
    const start = inspectedJob.started_at
      ? new Date(inspectedJob.started_at).getTime()
      : Date.now()

    const updateTimer = () => {
      const diff = Math.max(0, Math.floor((Date.now() - start) / 1000))
      setElapsedSeconds(diff)
    }
    updateTimer()
    const iv = window.setInterval(updateTimer, 1000)
    return () => window.clearInterval(iv)
  }, [inspectedJob?.id, inspectedJob?.status, inspectedJob?.started_at])

  // Stream logs for inspected job
  useEffect(() => {
    if (!inspectedJob) return
    let cancelled = false

    const fetchLog = async () => {
      try {
        const res = await api.getJobLogs(inspectedJob.id)
        if (!cancelled) {
          setLogs((prev) => ({ ...prev, [inspectedJob.id]: res.log }))
        }
      } catch {
        /* ignore */
      }
    }

    fetchLog()
    const interval = inspectedJob.status === 'running' ? 2000 : 8000
    const iv = window.setInterval(fetchLog, interval)
    return () => {
      cancelled = true
      window.clearInterval(iv)
    }
  }, [inspectedJob?.id, inspectedJob?.status])

  // Autoscroll terminal if open
  useEffect(() => {
    if (showRawLogs && logPreRef.current) {
      logPreRef.current.scrollTop = logPreRef.current.scrollHeight
    }
  }, [logs, inspectedJob?.id, showRawLogs])

  const currentLog = (inspectedJob ? logs[inspectedJob.id] : '') || ''
  const filteredLog = logSearch
    ? currentLog
        .split('\n')
        .filter((l) => l.toLowerCase().includes(logSearch.toLowerCase()))
        .join('\n')
    : currentLog

  async function handleDelete(jobId: number) {
    if (!window.confirm(`Permanently delete Asset #${jobId}? This removes all 3D mesh files.`)) {
      return
    }
    try {
      if (onDeleteJob) {
        await onDeleteJob(jobId)
      } else {
        await api.deleteJob(jobId)
        await onRefresh()
      }
    } catch (err) {
      alert(err instanceof Error ? err.message : String(err))
    }
  }

  // Active step in pipeline
  const activeStageIndex = useMemo(() => {
    if (!inspectedJob) return 0
    if (inspectedJob.status === 'completed') return 4
    if (inspectedJob.status === 'queued') return 0
    // If running, guess based on elapsed or logs
    if (currentLog.includes('unirig') || currentLog.includes('Rigging')) return 3
    if (currentLog.includes('texture') || currentLog.includes('paint') || currentLog.includes('uv')) return 2
    if (currentLog.includes('shape') || currentLog.includes('mesh')) return 1
    return 1
  }, [inspectedJob, currentLog])

  return (
    <footer className={`dcc-bottom-dock ${showRawLogs ? 'expanded' : ''}`}>
      {/* Header Dock Tabs */}
      <div className="dock-header">
        <div className="dock-tabs">
          <button
            type="button"
            className={`dock-tab ${activeTab === 'pipeline' ? 'active' : ''}`}
            onClick={() => setActiveTab('pipeline')}
          >
            <Activity size={13} />
            <span>AI Pipeline & Generation Jobs</span>
            {activeJobs.length > 0 && (
              <span className="landing-brand-badge" style={{ fontSize: '9px', padding: '1px 6px', background: 'var(--accent)', color: '#fff' }}>
                {activeJobs.length} Active
              </span>
            )}
          </button>
          <button
            type="button"
            className={`dock-tab ${activeTab === 'assets' ? 'active' : ''}`}
            onClick={() => setActiveTab('assets')}
          >
            <Grid size={13} />
            <span>Asset Browser ({completedJobs.length})</span>
          </button>
        </div>

        {/* Right Header Actions */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          {activeTab === 'pipeline' && inspectedJob && (
            <button
              type="button"
              className="ghost"
              style={{ fontSize: '11px', padding: '3px 8px', minHeight: '26px' }}
              onClick={() => setShowRawLogs(!showRawLogs)}
              title="Toggle raw GPU worker terminal output"
            >
              <Terminal size={11} />
              <span>{showRawLogs ? 'Hide Raw Log' : 'Show Terminal Log'}</span>
              {showRawLogs ? <ChevronDown size={11} /> : <ChevronUp size={11} />}
            </button>
          )}

          {failedJobs.length > 0 && (
            <button
              type="button"
              className="danger"
              style={{ padding: '3px 8px', fontSize: '10px', minHeight: '26px' }}
              onClick={async () => {
                if (confirm('Clear all failed jobs?')) {
                  await api.deleteFailedJobs()
                  await onRefresh()
                }
              }}
            >
              Clear {failedJobs.length} Failed
            </button>
          )}
        </div>
      </div>

      {/* Effortless Job Selector Strip */}
      {activeTab === 'pipeline' && jobs.length > 0 && (
        <div className="job-selector-strip">
          <span style={{ fontSize: '11px', color: 'var(--text-muted)', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '4px', marginRight: '4px' }}>
            <span>Jobs:</span>
          </span>

          {jobs.slice(0, 10).map((j) => {
            const isSelected = inspectedJob?.id === j.id
            return (
              <button
                key={j.id}
                type="button"
                className={`job-pill ${isSelected ? 'active' : ''}`}
                onClick={() => setSelectedJobId(j.id)}
                title={j.prompt || `Job #${j.id}`}
              >
                <span className={`job-pill-dot ${j.status}`} />
                <span>#{j.id}</span>
                <span className="job-pill-mode">
                  {j.mode === 'text' ? 'Text' : j.mode === 'image' ? 'Image' : 'Rig'}
                </span>
                {j.status === 'running' && (
                  <span style={{ fontSize: '9.5px', color: 'var(--accent)', fontWeight: 700 }}>
                    [Running]
                  </span>
                )}
              </button>
            )
          })}

          {jobs.length > 10 && (
            <select
              value={inspectedJob?.id ?? ''}
              onChange={(e) => setSelectedJobId(Number(e.target.value))}
              style={{
                fontSize: '11px',
                padding: '2px 8px',
                borderRadius: 'var(--radius-pill)',
                minHeight: '26px',
                boxShadow: 'var(--shadow-extruded-sm)',
                background: 'var(--bg-surface)',
                border: 'none',
              }}
            >
              {jobs.map((j) => (
                <option key={j.id} value={j.id}>
                  #{j.id} · {j.status.toUpperCase()} · {j.prompt?.slice(0, 24) || j.mode}
                </option>
              ))}
            </select>
          )}
        </div>
      )}

      {/* Dock Content */}
      {activeTab === 'pipeline' ? (
        <div style={{ display: 'flex', flexDirection: 'column', flex: 1, overflow: 'hidden' }}>
          {inspectedJob ? (
            <>
              {/* Pipeline 4-Stage Stepper Bar */}
              <div className="pipeline-stepper-row">
                <span style={{ fontWeight: 700, fontSize: '11px', color: 'var(--text-primary)', marginRight: '4px' }}>
                  Job #{inspectedJob.id} [{inspectedJob.mode.toUpperCase()}]:
                </span>

                {STAGES.map((s, idx) => {
                  const isDone = activeStageIndex > idx || inspectedJob.status === 'completed'
                  const isCurrent = inspectedJob.status === 'running' && activeStageIndex === idx
                  return (
                    <div
                      key={idx}
                      className={`pipeline-step-chip ${isDone ? 'done' : isCurrent ? 'active' : ''}`}
                    >
                      {isDone ? (
                        <CheckCircle2 size={11} />
                      ) : isCurrent ? (
                        <Sparkles size={11} className="spin" />
                      ) : (
                        <Clock size={11} />
                      )}
                      <span>{s.label}</span>
                    </div>
                  )
                })}

                <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <span style={{ fontSize: '11px', color: 'var(--text-dim)' }}>
                    Status:{' '}
                    <strong style={{ color: inspectedJob.status === 'completed' ? '#059669' : inspectedJob.status === 'running' ? 'var(--accent)' : 'var(--text-primary)' }}>
                      {inspectedJob.status.toUpperCase()}
                    </strong>
                  </span>
                </div>
              </div>

              {/* Main Visual Progress Loader Dashboard */}
              <div className="pipeline-loader-card">
                <div className="pipeline-loader-left">
                  {/* Visual Loader Animation */}
                  {inspectedJob.status === 'running' ? (
                    <div className="pipeline-spinner-ring">
                      <Sparkles size={20} style={{ color: 'var(--accent)' }} className="spin" />
                    </div>
                  ) : inspectedJob.status === 'queued' ? (
                    <div className="pipeline-spinner-ring" style={{ boxShadow: 'var(--shadow-inset-sm)' }}>
                      <Clock size={20} style={{ color: '#F59E0B' }} />
                    </div>
                  ) : inspectedJob.status === 'completed' ? (
                    <div className="pipeline-spinner-ring" style={{ background: 'rgba(16, 185, 129, 0.15)' }}>
                      <CheckCircle2 size={24} style={{ color: '#059669' }} />
                    </div>
                  ) : (
                    <div className="pipeline-spinner-ring" style={{ background: 'rgba(239, 68, 68, 0.15)' }}>
                      <AlertCircle size={24} style={{ color: 'var(--danger)' }} />
                    </div>
                  )}

                  {/* Status & Live Meta */}
                  <div className="pipeline-loader-meta">
                    <div className="pipeline-loader-status">
                      {inspectedJob.status === 'running' ? (
                        <span>Synthesizing 3D Character (~35k Faces)…</span>
                      ) : inspectedJob.status === 'queued' ? (
                        <span>Queued in GPU Worker Pool</span>
                      ) : inspectedJob.status === 'completed' ? (
                        <span style={{ color: '#059669' }}>3D Model Ready for Viewport & Animation!</span>
                      ) : (
                        <span style={{ color: 'var(--danger)' }}>Generation Interrupted</span>
                      )}
                    </div>

                    <div className="pipeline-loader-desc">
                      {inspectedJob.prompt || (inspectedJob.mode === 'rig' ? 'Static 3D Mesh Rigging' : 'Image Reference 3D Pipeline')}
                    </div>

                    <div className="pipeline-loader-specs">
                      {inspectedJob.status === 'running' && (
                        <span className="asset-meta-chip" style={{ color: 'var(--accent)', fontWeight: 700 }}>
                          <Clock size={10} style={{ display: 'inline', marginRight: '3px' }} />
                          Elapsed: {elapsedSeconds}s · Approx: ~60-90s
                        </span>
                      )}
                      <span className="asset-meta-chip">~35k Tris Mesh</span>
                      <span className="asset-meta-chip">4K UV Atlas</span>
                      <span className="asset-meta-chip">54 Humanoid Bones</span>
                      <span className="asset-meta-chip">
                        <Cpu size={10} style={{ display: 'inline', marginRight: '3px' }} />
                        Dual RTX 4000 Ada
                      </span>
                    </div>
                  </div>
                </div>

                {/* Source Concept Reference Preview */}
                {inspectedJob.preview_url && (
                  <div
                    className="pipeline-loader-preview"
                    title="Source concept reference image"
                    onClick={() => onSelectJob(inspectedJob.id)}
                  >
                    <JobImageThumbnail job={inspectedJob} style={{ width: '100%', height: '100%' }} />
                  </div>
                )}

                {/* Direct Action Buttons */}
                <div className="pipeline-loader-actions">
                  {inspectedJob.status === 'completed' && (
                    <div style={{ display: 'flex', gap: '6px' }}>
                      <button
                        type="button"
                        className="primary"
                        style={{ padding: '6px 12px', fontSize: '11px', minHeight: '32px' }}
                        onClick={() => onSelectJob(inspectedJob.id)}
                      >
                        <Eye size={12} />
                        <span>Load in Viewport</span>
                      </button>
                      <button
                        type="button"
                        className="ghost"
                        style={{ padding: '6px 10px', fontSize: '11px', minHeight: '32px' }}
                        onClick={() => onAnimateJob(inspectedJob.id)}
                      >
                        <Play size={12} />
                        <span>Motion</span>
                      </button>
                      <button
                        type="button"
                        className="ghost"
                        style={{ padding: '6px 10px', fontSize: '11px', minHeight: '32px' }}
                        onClick={() => api.downloadGlb(inspectedJob.id)}
                      >
                        <Download size={12} />
                      </button>
                      <button
                        type="button"
                        className="ghost"
                        style={{ padding: '6px 10px', fontSize: '11px', minHeight: '32px' }}
                        onClick={() => {
                          setRebakeModalJob(inspectedJob)
                          setRebakeYaw(0)
                          setRebakePitch(0)
                          setRebakeUvSize(2048)
                          setRebakeInpaintMode('uv')
                          setRebakeSteps(50)
                          setRebakeError(null)
                        }}
                        title="Rebake UV atlas & adjust projection heading/tilt"
                      >
                        <RotateCcw size={12} />
                        <span>Rebake UV</span>
                      </button>
                    </div>
                  )}

                  {inspectedJob.status === 'failed' && (
                    <button
                      type="button"
                      className="primary"
                      style={{ padding: '6px 12px', fontSize: '11px', minHeight: '32px' }}
                      onClick={async () => {
                        await api.retryJob(inspectedJob.id)
                        await onRefresh()
                      }}
                    >
                      <RotateCcw size={12} />
                      <span>Retry Job</span>
                    </button>
                  )}

                  {inspectedJob.status !== 'running' && (
                    <button
                      type="button"
                      className="danger"
                      style={{ padding: '5px 10px', fontSize: '10.5px', minHeight: '28px' }}
                      onClick={() => handleDelete(inspectedJob.id)}
                      title="Permanently delete asset and files"
                    >
                      <Trash2 size={11} />
                      <span>Delete Job</span>
                    </button>
                  )}
                </div>
              </div>

              {/* Optional Expandable Raw Terminal View */}
              {showRawLogs && (
                <div style={{ display: 'flex', flexDirection: 'column', flex: 1, overflow: 'hidden' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '0 16px 4px' }}>
                    <Search size={11} style={{ color: 'var(--text-dim)' }} />
                    <input
                      type="text"
                      placeholder="Filter raw logs…"
                      value={logSearch}
                      onChange={(e) => setLogSearch(e.target.value)}
                      style={{
                        border: 'none',
                        boxShadow: 'var(--shadow-inset-sm)',
                        padding: '2px 8px',
                        background: 'var(--bg-surface)',
                        fontSize: '11px',
                        width: '140px',
                        borderRadius: 'var(--radius-pill)',
                      }}
                    />
                  </div>
                  <pre ref={logPreRef} className="terminal-log-view">
                    {filteredLog || 'Waiting for GPU worker log output…'}
                  </pre>
                </div>
              )}
            </>
          ) : (
            <div style={{ flex: 1, display: 'grid', placeItems: 'center', color: 'var(--text-muted)', fontSize: '12px' }}>
              No jobs in queue. Start generating in the AI Gen Studio tab!
            </div>
          )}
        </div>
      ) : (
        /* Asset Browser Gallery in Dock */
        <div className="asset-gallery-grid">
          {completedJobs.map((job) => (
            <div
              key={job.id}
              className={`asset-thumb-card ${activeJobId === job.id ? 'active' : ''}`}
              onClick={() => onSelectJob(job.id)}
            >
              <div className="asset-thumb-img-wrap">
                <JobImageThumbnail job={job} style={{ width: '100%', height: '100%' }} />
              </div>
              <div className="asset-thumb-info">
                <div className="asset-thumb-title">
                  <span>#{job.id} · {job.mode.toUpperCase()}</span>
                </div>
                <div style={{ fontSize: '10.5px', color: 'var(--text-muted)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {job.prompt || (job.mode === 'rig' ? 'Rigged Static Mesh' : '3D Skinned Asset')}
                </div>
                <div style={{ display: 'flex', gap: '4px', marginTop: '6px' }}>
                  <button
                    type="button"
                    style={{ flex: 1, padding: '3px 0', fontSize: '10px' }}
                    onClick={(e) => {
                      e.stopPropagation()
                      onSelectJob(job.id)
                    }}
                  >
                    <Eye size={10} />
                    <span>View</span>
                  </button>
                  <button
                    type="button"
                    style={{ flex: 1, padding: '3px 0', fontSize: '10px' }}
                    onClick={(e) => {
                      e.stopPropagation()
                      onAnimateJob(job.id)
                    }}
                  >
                    <Play size={10} />
                    <span>Motion</span>
                  </button>
                  <button
                    type="button"
                    style={{ padding: '3px 6px', fontSize: '10px' }}
                    onClick={(e) => {
                      e.stopPropagation()
                      api.downloadGlb(job.id)
                    }}
                    title="Download .GLB"
                  >
                    <Download size={10} />
                  </button>
                  <button
                    type="button"
                    className="danger"
                    style={{ padding: '3px 6px', fontSize: '10px' }}
                    onClick={(e) => {
                      e.stopPropagation()
                      handleDelete(job.id)
                    }}
                    title="Delete Asset"
                  >
                    <Trash2 size={10} />
                  </button>
                </div>
              </div>
            </div>
          ))}
          {completedJobs.length === 0 && (
            <div style={{ gridColumn: '1 / -1', textAlign: 'center', padding: '30px', color: 'var(--text-dim)' }}>
              No completed 3D assets yet. Generate one in the AI Studio!
            </div>
          )}
        </div>
      )}

      {/* Rebake UV Projection Modal */}
      {rebakeModalJob && (
        <div className="modal-backdrop" onClick={() => !isRebaking && setRebakeModalJob(null)}>
          <div
            className="modal-box"
            style={{ width: 'min(500px, 95vw)', padding: '24px' }}
            onClick={(e) => e.stopPropagation()}
          >
            <button
              type="button"
              className="modal-close-btn"
              disabled={isRebaking}
              onClick={() => setRebakeModalJob(null)}
            >
              <X size={16} />
            </button>

            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
              <RotateCcw size={18} style={{ color: 'var(--blender-orange)' }} />
              <h3 className="modal-title" style={{ margin: 0 }}>
                UV Map Rebake & Projection Alignment
              </h3>
            </div>
            <p className="modal-subtitle" style={{ margin: '0 0 16px 0' }}>
              Re-project multi-view texture maps onto Asset #{rebakeModalJob.id} without re-meshing geometry.
            </p>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '14px', textAlign: 'left' }}>
              {/* Yaw */}
              <div className="dcc-field-group">
                <div className="dcc-field-label" style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span>Camera Yaw (Heading Offset)</span>
                  <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--cyan-accent)', fontWeight: 700 }}>
                    {rebakeYaw > 0 ? `+${rebakeYaw}` : rebakeYaw}°
                  </span>
                </div>
                <input
                  type="range"
                  min="-180"
                  max="180"
                  step="5"
                  value={rebakeYaw}
                  onChange={(e) => setRebakeYaw(parseInt(e.target.value, 10))}
                />
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '4px', marginTop: '4px' }}>
                  {[
                    { label: '0° Front', val: 0 },
                    { label: '+90° R', val: 90 },
                    { label: '180° Back', val: 180 },
                    { label: '-90° L', val: -90 },
                  ].map((p) => (
                    <button
                      key={p.label}
                      type="button"
                      style={{ fontSize: '10.5px', padding: '4px 0' }}
                      className={rebakeYaw === p.val ? 'active' : ''}
                      onClick={() => setRebakeYaw(p.val)}
                    >
                      {p.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Pitch */}
              <div className="dcc-field-group">
                <div className="dcc-field-label" style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span>Camera Pitch (Tilt Offset)</span>
                  <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--cyan-accent)', fontWeight: 700 }}>
                    {rebakePitch > 0 ? `+${rebakePitch}` : rebakePitch}°
                  </span>
                </div>
                <input
                  type="range"
                  min="-45"
                  max="45"
                  step="5"
                  value={rebakePitch}
                  onChange={(e) => setRebakePitch(parseInt(e.target.value, 10))}
                />
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '4px', marginTop: '4px' }}>
                  {[
                    { label: '-15° Low', val: -15 },
                    { label: '0° Level', val: 0 },
                    { label: '+15° High', val: 15 },
                  ].map((p) => (
                    <button
                      key={p.label}
                      type="button"
                      style={{ fontSize: '10.5px', padding: '4px 0' }}
                      className={rebakePitch === p.val ? 'active' : ''}
                      onClick={() => setRebakePitch(p.val)}
                    >
                      {p.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Resolution & Inpaint */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                <div className="dcc-field-group">
                  <span className="dcc-field-label">Atlas Resolution</span>
                  <div style={{ display: 'flex', gap: '4px' }}>
                    {[1024, 2048, 4096].map((res) => (
                      <button
                        key={res}
                        type="button"
                        style={{ flex: 1, fontSize: '10.5px', padding: '5px 0' }}
                        className={rebakeUvSize === res ? 'active' : ''}
                        onClick={() => setRebakeUvSize(res)}
                      >
                        {res === 1024 ? '1K' : res === 2048 ? '2K' : '4K'}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="dcc-field-group">
                  <span className="dcc-field-label">Seam Blend</span>
                  <div style={{ display: 'flex', gap: '4px' }}>
                    <button
                      type="button"
                      style={{ flex: 1, fontSize: '10.5px', padding: '5px 0' }}
                      className={rebakeInpaintMode === 'uv' ? 'active' : ''}
                      onClick={() => setRebakeInpaintMode('uv')}
                    >
                      Crisp
                    </button>
                    <button
                      type="button"
                      style={{ flex: 1, fontSize: '10.5px', padding: '5px 0' }}
                      className={rebakeInpaintMode === 'view' ? 'active' : ''}
                      onClick={() => setRebakeInpaintMode('view')}
                    >
                      Soft
                    </button>
                  </div>
                </div>
              </div>

              {rebakeError && (
                <div
                  style={{
                    fontSize: '11px',
                    color: 'var(--ruby-danger)',
                    background: 'rgba(239, 68, 68, 0.1)',
                    padding: '8px',
                    borderRadius: '4px',
                  }}
                >
                  {rebakeError}
                </div>
              )}

              <div style={{ display: 'flex', gap: '10px', marginTop: '8px' }}>
                <button
                  type="button"
                  className="ghost"
                  style={{ flex: 1 }}
                  disabled={isRebaking}
                  onClick={() => setRebakeModalJob(null)}
                >
                  Cancel
                </button>
                <button
                  type="button"
                  className="primary"
                  style={{ flex: 2 }}
                  disabled={isRebaking}
                  onClick={async () => {
                    setIsRebaking(true)
                    setRebakeError(null)
                    try {
                      await api.rebakeJob(rebakeModalJob.id, {
                        rotation_yaw: rebakeYaw,
                        rotation_pitch: rebakePitch,
                        uv_size: rebakeUvSize,
                        inpaint_mode: rebakeInpaintMode,
                        steps: rebakeSteps,
                      })
                      await onRefresh()
                      setRebakeModalJob(null)
                    } catch (err: any) {
                      setRebakeError(err?.message || 'Failed to trigger rebake')
                    } finally {
                      setIsRebaking(false)
                    }
                  }}
                >
                  {isRebaking ? 'Queuing Rebake…' : 'Start Rebake'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </footer>
  )
}
