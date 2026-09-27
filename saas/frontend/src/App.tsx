import { useCallback, useEffect, useState } from 'react'
import { api } from './api'
import type { AllowedPassword, Job, Me } from './api'
import { LandingPage } from './LandingPage'
import { Viewport3D } from './Viewport3D'
import { AnimationStudio } from './AnimationStudio'
import { OutlinerProperties } from './OutlinerProperties'
import { AIGenerationStudio } from './AIGenerationStudio'
import { AIConsoleBrowser } from './AIConsoleBrowser'
import { AssetBrowserView } from './AssetBrowserView'
import { AdminPortal } from './AdminPortal'
import {
  Wand2,
  Box,
  Activity,
  FolderOpen,
  ShieldCheck,
  LogOut,
  Cpu,
} from 'lucide-react'
import './theme.css'

export type StudioWorkspace = 'ai-studio' | 'viewport' | 'animator' | 'assets' | 'admin'

export function App() {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem('yeetgen_token') || localStorage.getItem('anilab_token'))
  const [me, setMe] = useState<Me | null>(null)
  const [workspace, setWorkspace] = useState<StudioWorkspace>('ai-studio')
  const [jobs, setJobs] = useState<Job[]>([])
  const [passwords, setPasswords] = useState<AllowedPassword[]>([])
  const [activeJobId, setActiveJobId] = useState<number | null>(null)
  const [meshStats, setMeshStats] = useState({
    tris: 0,
    verts: 0,
    bones: 0,
    dims: [0, 0, 0] as [number, number, number],
  })

  // GLB Blob Object URL
  const [glbUrl, setGlbUrl] = useState<string | null>(null)

  // DCC Interactive Viewport & Outliner State
  const [dccLocation, setDccLocation] = useState<[number, number, number]>([0, 0, 0])
  const [dccRotation, setDccRotation] = useState<[number, number, number]>([0, 0, 0])
  const [dccScale, setDccScale] = useState<[number, number, number]>([1, 1, 1])
  const [visibleMesh, setVisibleMesh] = useState(true)
  const [visibleArmature, setVisibleArmature] = useState(false)
  const [visibleLights, setVisibleLights] = useState(true)
  const [materialRoughness, setMaterialRoughness] = useState(0.4)
  const [materialMetalness, setMaterialMetalness] = useState(0.1)
  const [selectedOutlinerNode, setSelectedOutlinerNode] = useState('mesh')
  const [cameraTrigger, setCameraTrigger] = useState(0)
  const [textureInfo, setTextureInfo] = useState<{ width: number; height: number; format: string } | null>(null)

  const handleResetTransform = () => {
    setDccLocation([0, 0, 0])
    setDccRotation([0, 0, 0])
    setDccScale([1, 1, 1])
  }

  const isAdmin = me?.role === 'admin'

  const refresh = useCallback(async () => {
    if (!token) return
    try {
      const profile = await api.me()
      setMe(profile)
      const list = await api.listJobs()
      setJobs(list)

      if (profile.role === 'admin') {
        const passList = await api.listPasswords()
        setPasswords(passList)
      } else {
        setPasswords([])
      }
    } catch {
      localStorage.removeItem('yeetgen_token')
      localStorage.removeItem('anilab_token')
      setToken(null)
      setMe(null)
    }
  }, [token])

  useEffect(() => {
    if (!token) {
      setMe(null)
      setJobs([])
      setPasswords([])
      setGlbUrl(null)
      return
    }
    refresh()
  }, [token, refresh])

  // Periodic polling for active jobs
  useEffect(() => {
    if (!token) return
    const hasActive = jobs.some((j) => j.status === 'queued' || j.status === 'running')
    const id = window.setInterval(
      () => {
        refresh().catch(() => undefined)
      },
      hasActive ? 2000 : 6000,
    )
    return () => window.clearInterval(id)
  }, [token, refresh, jobs])

  // Auto-select latest completed job on boot if none selected
  useEffect(() => {
    if (activeJobId == null && jobs.length > 0) {
      const firstDone = jobs.find((j) => j.status === 'completed')
      if (firstDone) setActiveJobId(firstDone.id)
    }
  }, [jobs, activeJobId])

  // Load GLB Blob when activeJobId changes
  useEffect(() => {
    if (activeJobId == null) {
      setGlbUrl(null)
      return
    }

    let alive = true
    let blobUrl: string | null = null

    api
      .fetchGlbBlob(activeJobId)
      .then((blob) => {
        if (!alive) return
        blobUrl = URL.createObjectURL(blob)
        setGlbUrl(blobUrl)
      })
      .catch(() => {
        if (alive) setGlbUrl(null)
      })

    return () => {
      alive = false
      if (blobUrl) URL.revokeObjectURL(blobUrl)
    }
  }, [activeJobId])

  // Login handler
  async function handleLogin(password: string) {
    const res = await api.login(password)
    localStorage.setItem('yeetgen_token', res.access_token)
    setToken(res.access_token)
    // If admin logged in, land on AI Studio with Admin tab available
    setWorkspace(res.role === 'admin' ? 'admin' : 'ai-studio')
    await refresh()
  }

  function handleLogout() {
    localStorage.removeItem('yeetgen_token')
    localStorage.removeItem('anilab_token')
    setToken(null)
    setMe(null)
    setWorkspace('ai-studio')
  }

  async function handleDeleteJob(jobId: number) {
    await api.deleteJob(jobId)
    if (activeJobId === jobId) {
      setActiveJobId(null)
      setGlbUrl(null)
    }
    await refresh()
  }

  // If unauthenticated: Render 3D Hero Landing Page & Password Sign-In
  if (!token) {
    return <LandingPage onLogin={handleLogin} />
  }

  // Workspaces list
  const workspaceTabs: Array<{ id: StudioWorkspace; label: string; icon: React.ReactNode }> = [
    { id: 'ai-studio', label: 'AI Gen Studio', icon: <Wand2 size={13} /> },
    { id: 'viewport', label: '3D Viewport & Shading', icon: <Box size={13} /> },
    { id: 'animator', label: 'Motion & Rigging', icon: <Activity size={13} /> },
    { id: 'assets', label: 'Asset Browser', icon: <FolderOpen size={13} /> },
  ]

  // Completely hidden Admin tab unless authenticated with admin role
  if (isAdmin) {
    workspaceTabs.push({ id: 'admin', label: 'Admin & Cluster', icon: <ShieldCheck size={13} /> })
  }

  return (
    <div className="studio-shell">
      {/* Top Menu Bar */}
      <header className="dcc-topbar">
        <div className="dcc-topbar-left">
          <div className="dcc-brand">
            <div className="dcc-brand-icon">Y</div>
            <span>YeetGen Studio</span>
          </div>

          {/* Blender Workspace Switcher Tabs */}
          <nav className="dcc-workspace-tabs">
            {workspaceTabs.map((t) => (
              <button
                key={t.id}
                type="button"
                className={`dcc-workspace-tab ${workspace === t.id ? 'active' : ''}`}
                onClick={() => setWorkspace(t.id)}
              >
                {t.icon}
                <span>{t.label}</span>
              </button>
            ))}
          </nav>
        </div>

        <div className="dcc-topbar-right">
          {/* Dual GPU Status Telemetry */}
          <div className="dcc-gpu-pill">
            <div className="gpu-pulse-dot" />
            <Cpu size={12} />
            <span>Dual RTX 4000 Ada (2x 20GB) · Ready</span>
          </div>

          {/* User badge */}
          <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
            Role: <strong style={{ color: isAdmin ? 'var(--blender-orange-hover)' : 'var(--emerald-accent)' }}>
              {isAdmin ? 'Master Admin' : 'Creator'}
            </strong>
          </span>

          {/* Logout */}
          <button
            type="button"
            className="ghost"
            style={{ padding: '4px 8px', fontSize: '11px' }}
            onClick={handleLogout}
            title="Log Out of Studio"
          >
            <LogOut size={12} />
            <span>Log Out</span>
          </button>
        </div>
      </header>

      {/* Main DCC Workspace Layout */}
      {workspace === 'admin' && isAdmin ? (
        <AdminPortal passwords={passwords} onRefresh={refresh} />
      ) : workspace === 'animator' ? (
        <div style={{ display: 'flex', flexDirection: 'column', flex: 1, overflow: 'hidden' }}>
          <AnimationStudio src={glbUrl} jobId={activeJobId} />
        </div>
      ) : workspace === 'assets' ? (
        <div style={{ display: 'flex', flexDirection: 'column', flex: 1, overflow: 'hidden', padding: '12px' }}>
          <AssetBrowserView
            jobs={jobs}
            activeJobId={activeJobId}
            onSelectJob={(id) => {
              setActiveJobId(id)
              setWorkspace('viewport')
            }}
            onAnimateJob={(id) => {
              setActiveJobId(id)
              setWorkspace('animator')
            }}
            onDeleteJob={handleDeleteJob}
            onRefresh={refresh}
          />
        </div>
      ) : (
        <main
          className={`dcc-main-grid ${
            workspace === 'viewport' ? 'viewport-only' : ''
          }`}
        >
          {/* Left AI Studio Tool Shelf (Only in AI Studio mode) */}
          {workspace === 'ai-studio' && (
            <AIGenerationStudio onJobCreated={refresh} />
          )}

          {/* Central 3D Viewport */}
          <Viewport3D
            src={glbUrl}
            jobId={activeJobId}
            onDownloadGlb={() => {
              if (activeJobId != null) api.downloadGlb(activeJobId)
            }}
            onMeshStats={setMeshStats}
            location={dccLocation}
            rotation={dccRotation}
            scale={dccScale}
            visibleMesh={visibleMesh}
            visibleArmature={visibleArmature}
            visibleLights={visibleLights}
            roughness={materialRoughness}
            metalness={materialMetalness}
            cameraTrigger={cameraTrigger}
            onTextureDetails={setTextureInfo}
          />

          {/* Right Outliner & Properties Inspector */}
          <OutlinerProperties
            stats={meshStats}
            jobId={activeJobId}
            onDownloadGlb={() => {
              if (activeJobId != null) api.downloadGlb(activeJobId)
            }}
            onRefresh={refresh}
            location={dccLocation}
            onChangeLocation={setDccLocation}
            rotation={dccRotation}
            onChangeRotation={setDccRotation}
            scale={dccScale}
            onChangeScale={setDccScale}
            onResetTransform={handleResetTransform}
            visibleMesh={visibleMesh}
            onToggleMesh={() => setVisibleMesh((v) => !v)}
            visibleArmature={visibleArmature}
            onToggleArmature={() => setVisibleArmature((v) => !v)}
            visibleLights={visibleLights}
            onToggleLights={() => setVisibleLights((v) => !v)}
            onFocusCamera={() => setCameraTrigger((t) => t + 1)}
            selectedNode={selectedOutlinerNode}
            onSelectNode={setSelectedOutlinerNode}
            roughness={materialRoughness}
            onChangeRoughness={setMaterialRoughness}
            metalness={materialMetalness}
            onChangeMetalness={setMaterialMetalness}
            textureInfo={textureInfo}
          />
        </main>
      )}

      {/* Bottom Dock: Pipeline Stepper & Log Terminal / Asset Browser */}
      {workspace !== 'admin' && workspace !== 'animator' && workspace !== 'assets' && (
        <AIConsoleBrowser
          jobs={jobs}
          activeJobId={activeJobId}
          onSelectJob={(id) => {
            setActiveJobId(id)
            setWorkspace('viewport')
          }}
          onAnimateJob={(id) => {
            setActiveJobId(id)
            setWorkspace('animator')
          }}
          onDeleteJob={handleDeleteJob}
          onRefresh={refresh}
        />
      )}
    </div>
  )
}

export default App
