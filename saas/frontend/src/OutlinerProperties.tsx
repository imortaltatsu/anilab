import { useState } from 'react'
import {
  Folder,
  Box,
  Bone,
  Eye,
  EyeOff,
  Sun,
  Camera,
  Layers,
  Download,
  RotateCcw,
  Sliders,
  Compass,
  RefreshCw,
} from 'lucide-react'
import { api } from './api'

type Props = {
  stats: { tris: number; verts: number; bones: number; dims: [number, number, number] }
  jobId?: number | null
  onDownloadGlb?: () => void
  onRefresh?: () => void

  // Live DCC Transform
  location: [number, number, number]
  onChangeLocation: (loc: [number, number, number]) => void
  rotation: [number, number, number]
  onChangeRotation: (rot: [number, number, number]) => void
  scale: [number, number, number]
  onChangeScale: (scale: [number, number, number]) => void
  onResetTransform: () => void

  // Live Outliner Visibility & Selection
  visibleMesh: boolean
  onToggleMesh: () => void
  visibleArmature: boolean
  onToggleArmature: () => void
  visibleLights: boolean
  onToggleLights: () => void
  onFocusCamera: () => void

  selectedNode: string
  onSelectNode: (node: string) => void

  // Live Material Properties
  roughness: number
  onChangeRoughness: (r: number) => void
  metalness: number
  onChangeMetalness: (m: number) => void
  textureInfo: { width: number; height: number; format: string } | null
}

type TabMode = 'transform' | 'mesh' | 'material' | 'uv_rebake' | 'export'

export function OutlinerProperties({
  stats,
  jobId,
  onDownloadGlb,
  onRefresh,
  location,
  onChangeLocation,
  rotation,
  onChangeRotation,
  scale,
  onChangeScale,
  onResetTransform,
  visibleMesh,
  onToggleMesh,
  visibleArmature,
  onToggleArmature,
  visibleLights,
  onToggleLights,
  onFocusCamera,
  selectedNode,
  onSelectNode,
  roughness,
  onChangeRoughness,
  metalness,
  onChangeMetalness,
  textureInfo,
}: Props) {
  const [activeTab, setActiveTab] = useState<TabMode>('transform')

  // UV Rebake Parameters
  const [rotationYaw, setRotationYaw] = useState(0)
  const [rotationPitch, setRotationPitch] = useState(0)
  const [uvSize, setUvSize] = useState(2048)
  const [inpaintMode, setInpaintMode] = useState<'uv' | 'view'>('uv')
  const [bakeSteps, setBakeSteps] = useState(50)
  const [isRebaking, setIsRebaking] = useState(false)
  const [rebakeMessage, setRebakeMessage] = useState<string | null>(null)

  const handleRebake = async () => {
    if (!jobId) return
    setIsRebaking(true)
    setRebakeMessage(null)
    try {
      await api.rebakeJob(jobId, {
        rotation_yaw: rotationYaw,
        rotation_pitch: rotationPitch,
        uv_size: uvSize,
        inpaint_mode: inpaintMode,
        steps: bakeSteps,
      })
      setRebakeMessage('Rebake queued! Re-projecting texture on existing mesh…')
      onRefresh?.()
    } catch (err: any) {
      setRebakeMessage(`Error: ${err?.message || 'Rebake failed'}`)
    } finally {
      setIsRebaking(false)
    }
  }

  return (
    <aside className="dcc-outliner-panel">
      {/* Top Half: Scene Outliner Tree */}
      <div className="dcc-panel-header">
        <h3>
          <Folder size={14} style={{ color: 'var(--blender-orange)' }} />
          <span>Scene Outliner</span>
        </h3>
        <span style={{ fontSize: '11px', color: 'var(--text-dim)' }}>Layer 1</span>
      </div>

      <div className="outliner-tree-view">
        {/* Collection Root */}
        <div
          className={`outliner-node ${selectedNode === 'collection' ? 'active' : ''}`}
          onClick={() => onSelectNode('collection')}
        >
          <div className="outliner-node-left">
            <Folder size={13} style={{ color: 'var(--blender-orange)' }} />
            <span>Character_Collection</span>
          </div>
          <div
            className="outliner-node-icons"
            onClick={(e) => {
              e.stopPropagation()
              onToggleMesh()
            }}
            title="Toggle Collection Visibility"
            style={{ cursor: 'pointer' }}
          >
            {visibleMesh ? <Eye size={13} /> : <EyeOff size={13} style={{ color: 'var(--ruby-danger)' }} />}
          </div>
        </div>

        {/* Mesh Object */}
        <div
          className={`outliner-node ${selectedNode === 'mesh' ? 'active' : ''}`}
          style={{ paddingLeft: '20px' }}
          onClick={() => {
            onSelectNode('mesh')
            setActiveTab('transform')
          }}
        >
          <div className="outliner-node-left">
            <Box size={13} style={{ color: 'var(--cyan-accent)' }} />
            <span>Mesh_Character_35k</span>
          </div>
          <div
            className="outliner-node-icons"
            onClick={(e) => {
              e.stopPropagation()
              onToggleMesh()
            }}
            title="Toggle Mesh Visibility"
            style={{ cursor: 'pointer' }}
          >
            {visibleMesh ? <Eye size={13} /> : <EyeOff size={13} style={{ color: 'var(--ruby-danger)' }} />}
          </div>
        </div>

        {/* Armature Object */}
        <div
          className={`outliner-node ${selectedNode === 'armature' ? 'active' : ''}`}
          style={{ paddingLeft: '20px' }}
          onClick={() => {
            onSelectNode('armature')
            setActiveTab('mesh')
          }}
        >
          <div className="outliner-node-left">
            <Bone size={13} style={{ color: 'var(--blender-orange-hover)' }} />
            <span>Armature_Humanoid ({stats.bones} joints)</span>
          </div>
          <div
            className="outliner-node-icons"
            onClick={(e) => {
              e.stopPropagation()
              onToggleArmature()
            }}
            title="Toggle Skeleton Bone Helper"
            style={{ cursor: 'pointer' }}
          >
            {visibleArmature ? (
              <Eye size={13} style={{ color: 'var(--blender-orange)' }} />
            ) : (
              <EyeOff size={13} style={{ color: 'var(--text-dim)' }} />
            )}
          </div>
        </div>

        {/* Material Slot */}
        <div
          className={`outliner-node ${selectedNode === 'material' ? 'active' : ''}`}
          style={{ paddingLeft: '32px' }}
          onClick={() => {
            onSelectNode('material')
            setActiveTab('material')
          }}
        >
          <div className="outliner-node-left">
            <Layers size={13} style={{ color: 'var(--emerald-accent)' }} />
            <span>Mat_Atlas_4K_PBR</span>
          </div>
        </div>

        {/* Scene Lights */}
        <div
          className={`outliner-node ${selectedNode === 'lights' ? 'active' : ''}`}
          style={{ marginTop: '8px' }}
          onClick={() => onSelectNode('lights')}
        >
          <div className="outliner-node-left">
            <Sun size={13} style={{ color: '#f59e0b' }} />
            <span>Studio_KeyLight_HDR</span>
          </div>
          <div
            className="outliner-node-icons"
            onClick={(e) => {
              e.stopPropagation()
              onToggleLights()
            }}
            title="Toggle Scene Studio Lights"
            style={{ cursor: 'pointer' }}
          >
            {visibleLights ? <Eye size={13} /> : <EyeOff size={13} style={{ color: 'var(--ruby-danger)' }} />}
          </div>
        </div>

        {/* Camera Node */}
        <div
          className={`outliner-node ${selectedNode === 'camera' ? 'active' : ''}`}
          onClick={() => {
            onSelectNode('camera')
            onFocusCamera()
          }}
          title="Click to frame & focus camera"
        >
          <div className="outliner-node-left">
            <Camera size={13} style={{ color: 'var(--text-muted)' }} />
            <span>DCC_Perspective_Camera</span>
          </div>
          <div
            className="outliner-node-icons"
            onClick={(e) => {
              e.stopPropagation()
              onFocusCamera()
            }}
            title="Reset / Focus Viewport Camera"
            style={{ cursor: 'pointer' }}
          >
            <Eye size={13} />
          </div>
        </div>
      </div>

      {/* Bottom Half: Properties Inspector */}
      <div className="dcc-properties-area">
        <div className="properties-tabs-bar">
          <button
            type="button"
            className={`properties-tab-btn ${activeTab === 'transform' ? 'active' : ''}`}
            onClick={() => setActiveTab('transform')}
          >
            Transform
          </button>
          <button
            type="button"
            className={`properties-tab-btn ${activeTab === 'mesh' ? 'active' : ''}`}
            onClick={() => setActiveTab('mesh')}
          >
            Mesh Data
          </button>
          <button
            type="button"
            className={`properties-tab-btn ${activeTab === 'material' ? 'active' : ''}`}
            onClick={() => setActiveTab('material')}
          >
            Material
          </button>
          <button
            type="button"
            className={`properties-tab-btn ${activeTab === 'uv_rebake' ? 'active' : ''}`}
            onClick={() => setActiveTab('uv_rebake')}
          >
            UV & Rebake
          </button>
          <button
            type="button"
            className={`properties-tab-btn ${activeTab === 'export' ? 'active' : ''}`}
            onClick={() => setActiveTab('export')}
          >
            Export
          </button>
        </div>

        <div className="properties-body">
          {/* Transform Tab */}
          {activeTab === 'transform' && (
            <>
              {/* Location */}
              <div className="dcc-field-group">
                <span className="dcc-field-label">Location (X, Y, Z Meters)</span>
                <div className="dcc-vector3-row">
                  <span className="vec-label vec-x">X</span>
                  <input
                    type="number"
                    step="0.05"
                    value={location[0]}
                    onChange={(e) => onChangeLocation([parseFloat(e.target.value) || 0, location[1], location[2]])}
                  />
                  <span className="vec-label vec-y">Y</span>
                  <input
                    type="number"
                    step="0.05"
                    value={location[1]}
                    onChange={(e) => onChangeLocation([location[0], parseFloat(e.target.value) || 0, location[2]])}
                  />
                  <span className="vec-label vec-z">Z</span>
                  <input
                    type="number"
                    step="0.05"
                    value={location[2]}
                    onChange={(e) => onChangeLocation([location[0], location[1], parseFloat(e.target.value) || 0])}
                  />
                </div>
              </div>

              {/* Rotation */}
              <div className="dcc-field-group">
                <span className="dcc-field-label">Rotation (Euler Deg)</span>
                <div className="dcc-vector3-row">
                  <span className="vec-label vec-x">X</span>
                  <input
                    type="number"
                    step="5"
                    value={rotation[0]}
                    onChange={(e) => onChangeRotation([parseFloat(e.target.value) || 0, rotation[1], rotation[2]])}
                  />
                  <span className="vec-label vec-y">Y</span>
                  <input
                    type="number"
                    step="5"
                    value={rotation[1]}
                    onChange={(e) => onChangeRotation([rotation[0], parseFloat(e.target.value) || 0, rotation[2]])}
                  />
                  <span className="vec-label vec-z">Z</span>
                  <input
                    type="number"
                    step="5"
                    value={rotation[2]}
                    onChange={(e) => onChangeRotation([rotation[0], rotation[1], parseFloat(e.target.value) || 0])}
                  />
                </div>
              </div>

              {/* Scale */}
              <div className="dcc-field-group">
                <span className="dcc-field-label">Scale Factor</span>
                <div className="dcc-vector3-row">
                  <span className="vec-label vec-x">X</span>
                  <input
                    type="number"
                    step="0.1"
                    value={scale[0]}
                    onChange={(e) => onChangeScale([parseFloat(e.target.value) || 1, scale[1], scale[2]])}
                  />
                  <span className="vec-label vec-y">Y</span>
                  <input
                    type="number"
                    step="0.1"
                    value={scale[1]}
                    onChange={(e) => onChangeScale([scale[0], parseFloat(e.target.value) || 1, scale[2]])}
                  />
                  <span className="vec-label vec-z">Z</span>
                  <input
                    type="number"
                    step="0.1"
                    value={scale[2]}
                    onChange={(e) => onChangeScale([scale[0], scale[1], parseFloat(e.target.value) || 1])}
                  />
                </div>
              </div>

              {/* Reset to Origin */}
              <button
                type="button"
                className="ghost"
                onClick={onResetTransform}
                style={{
                  fontSize: '11px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '6px',
                  padding: '6px 0',
                  marginTop: '4px',
                }}
              >
                <RotateCcw size={12} />
                <span>Reset Transform to Origin</span>
              </button>

              <div className="dcc-field-group" style={{ marginTop: '6px' }}>
                <span className="dcc-field-label">Bounding Dimensions (Meters)</span>
                <div className="dcc-vector3-row">
                  <span className="vec-label vec-x">W</span>
                  <input type="text" readOnly value={`${stats.dims[0]} m`} />
                  <span className="vec-label vec-y">H</span>
                  <input type="text" readOnly value={`${stats.dims[1]} m`} />
                  <span className="vec-label vec-z">D</span>
                  <input type="text" readOnly value={`${stats.dims[2]} m`} />
                </div>
              </div>
            </>
          )}

          {/* Mesh Data Tab */}
          {activeTab === 'mesh' && (
            <>
              <div className="dcc-field-group">
                <span className="dcc-field-label">Topology Metrics</span>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                  <div style={{ background: 'var(--bg-darkest)', padding: '8px', borderRadius: '4px' }}>
                    <div style={{ fontSize: '10px', color: 'var(--text-dim)' }}>TRIANGLES</div>
                    <div style={{ fontSize: '15px', fontWeight: 700, color: 'var(--cyan-accent)' }}>
                      {stats.tris.toLocaleString()}
                    </div>
                  </div>
                  <div style={{ background: 'var(--bg-darkest)', padding: '8px', borderRadius: '4px' }}>
                    <div style={{ fontSize: '10px', color: 'var(--text-dim)' }}>VERTICES</div>
                    <div style={{ fontSize: '15px', fontWeight: 700, color: 'var(--text-bright)' }}>
                      {stats.verts.toLocaleString()}
                    </div>
                  </div>
                </div>
              </div>

              <div className="dcc-field-group">
                <span className="dcc-field-label">Skeleton & Rigging</span>
                <div style={{ background: 'var(--bg-darkest)', padding: '8px', borderRadius: '4px' }}>
                  <div style={{ fontSize: '10px', color: 'var(--text-dim)' }}>TOTAL JOINTS</div>
                  <div style={{ fontSize: '15px', fontWeight: 700, color: 'var(--blender-orange-hover)' }}>
                    {stats.bones} Humanoid Bones
                  </div>
                </div>
              </div>

              <button
                type="button"
                className="ghost"
                onClick={onToggleArmature}
                style={{
                  fontSize: '11px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '6px',
                  padding: '7px 0',
                }}
              >
                <Bone size={12} />
                <span>{visibleArmature ? 'Hide Skeleton Helper' : 'Show Skeleton Helper'}</span>
              </button>
            </>
          )}

          {/* Material Tab */}
          {activeTab === 'material' && (
            <>
              <div className="dcc-field-group">
                <div className="dcc-field-label" style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span>Roughness</span>
                  <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, color: 'var(--cyan-accent)' }}>
                    {roughness.toFixed(2)}
                  </span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.05"
                  value={roughness}
                  onChange={(e) => onChangeRoughness(parseFloat(e.target.value))}
                />
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '4px', marginTop: '4px' }}>
                  <button
                    type="button"
                    style={{ fontSize: '10px', padding: '3px 0' }}
                    onClick={() => onChangeRoughness(0.9)}
                  >
                    Matte (0.9)
                  </button>
                  <button
                    type="button"
                    style={{ fontSize: '10px', padding: '3px 0' }}
                    onClick={() => onChangeRoughness(0.4)}
                  >
                    Satin (0.4)
                  </button>
                  <button
                    type="button"
                    style={{ fontSize: '10px', padding: '3px 0' }}
                    onClick={() => onChangeRoughness(0.1)}
                  >
                    Glossy (0.1)
                  </button>
                </div>
              </div>

              <div className="dcc-field-group">
                <div className="dcc-field-label" style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span>Metallic</span>
                  <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, color: 'var(--cyan-accent)' }}>
                    {metalness.toFixed(2)}
                  </span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.05"
                  value={metalness}
                  onChange={(e) => onChangeMetalness(parseFloat(e.target.value))}
                />
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '4px', marginTop: '4px' }}>
                  <button
                    type="button"
                    style={{ fontSize: '10px', padding: '3px 0' }}
                    onClick={() => onChangeMetalness(0.0)}
                  >
                    Plastic (0.0)
                  </button>
                  <button
                    type="button"
                    style={{ fontSize: '10px', padding: '3px 0' }}
                    onClick={() => onChangeMetalness(0.5)}
                  >
                    Metal (0.5)
                  </button>
                  <button
                    type="button"
                    style={{ fontSize: '10px', padding: '3px 0' }}
                    onClick={() => onChangeMetalness(1.0)}
                  >
                    Chrome (1.0)
                  </button>
                </div>
              </div>

              <div className="dcc-field-group">
                <span className="dcc-field-label">Bake Texture Resolution</span>
                <div
                  style={{
                    fontSize: '11px',
                    fontFamily: 'var(--font-mono)',
                    color: 'var(--emerald-accent)',
                    background: 'var(--bg-darkest)',
                    padding: '8px 10px',
                    borderRadius: 'var(--radius-sm)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                  }}
                >
                  <span>
                    {textureInfo
                      ? `${textureInfo.width} × ${textureInfo.height} ${textureInfo.format}`
                      : '4096 × 4096 Ultra-HD UV Atlas'}
                  </span>
                  <span style={{ fontSize: '10px', color: 'var(--text-dim)' }}>PBR Shaded</span>
                </div>

                <button
                  type="button"
                  className="ghost"
                  onClick={() => setActiveTab('uv_rebake')}
                  style={{
                    fontSize: '10.5px',
                    padding: '6px 0',
                    marginTop: '6px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '6px',
                  }}
                >
                  <RotateCcw size={11} />
                  <span>Adjust UV Warps / Rebake Texture</span>
                </button>
              </div>
            </>
          )}

          {/* UV & Rebake Tab */}
          {activeTab === 'uv_rebake' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <div
                style={{
                  fontSize: '11px',
                  color: 'var(--text-muted)',
                  lineHeight: 1.4,
                  background: 'var(--bg-darkest)',
                  padding: '8px 10px',
                  borderRadius: 'var(--radius-sm)',
                  borderLeft: '3px solid var(--blender-orange)',
                }}
              >
                Adjust camera projection angles to fix texture misalignment, seams, or back-facing distortion without regenerating the 3D mesh.
              </div>

              {/* Camera Heading / Yaw Offset */}
              <div className="dcc-field-group">
                <div className="dcc-field-label" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                    <Compass size={12} style={{ color: 'var(--blender-orange)' }} />
                    Camera Yaw (Heading)
                  </span>
                  <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, color: 'var(--cyan-accent)' }}>
                    {rotationYaw > 0 ? `+${rotationYaw}` : rotationYaw}°
                  </span>
                </div>
                <input
                  type="range"
                  min="-180"
                  max="180"
                  step="5"
                  value={rotationYaw}
                  onChange={(e) => setRotationYaw(parseInt(e.target.value, 10))}
                />
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '4px', marginTop: '4px' }}>
                  <button
                    type="button"
                    style={{ fontSize: '10px', padding: '3px 0' }}
                    className={rotationYaw === 0 ? 'active' : ''}
                    onClick={() => setRotationYaw(0)}
                  >
                    0° Front
                  </button>
                  <button
                    type="button"
                    style={{ fontSize: '10px', padding: '3px 0' }}
                    className={rotationYaw === 90 ? 'active' : ''}
                    onClick={() => setRotationYaw(90)}
                  >
                    +90° R
                  </button>
                  <button
                    type="button"
                    style={{ fontSize: '10px', padding: '3px 0' }}
                    className={rotationYaw === 180 ? 'active' : ''}
                    onClick={() => setRotationYaw(180)}
                  >
                    180° Back
                  </button>
                  <button
                    type="button"
                    style={{ fontSize: '10px', padding: '3px 0' }}
                    className={rotationYaw === -90 ? 'active' : ''}
                    onClick={() => setRotationYaw(-90)}
                  >
                    -90° L
                  </button>
                </div>
              </div>

              {/* Camera Elevation / Pitch Offset */}
              <div className="dcc-field-group">
                <div className="dcc-field-label" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                    <Sliders size={12} style={{ color: 'var(--emerald-accent)' }} />
                    Camera Pitch (Tilt)
                  </span>
                  <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, color: 'var(--cyan-accent)' }}>
                    {rotationPitch > 0 ? `+${rotationPitch}` : rotationPitch}°
                  </span>
                </div>
                <input
                  type="range"
                  min="-45"
                  max="45"
                  step="5"
                  value={rotationPitch}
                  onChange={(e) => setRotationPitch(parseInt(e.target.value, 10))}
                />
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '4px', marginTop: '4px' }}>
                  <button
                    type="button"
                    style={{ fontSize: '10px', padding: '3px 0' }}
                    className={rotationPitch === -15 ? 'active' : ''}
                    onClick={() => setRotationPitch(-15)}
                  >
                    -15° Low
                  </button>
                  <button
                    type="button"
                    style={{ fontSize: '10px', padding: '3px 0' }}
                    className={rotationPitch === 0 ? 'active' : ''}
                    onClick={() => setRotationPitch(0)}
                  >
                    0° Level
                  </button>
                  <button
                    type="button"
                    style={{ fontSize: '10px', padding: '3px 0' }}
                    className={rotationPitch === 15 ? 'active' : ''}
                    onClick={() => setRotationPitch(15)}
                  >
                    +15° High
                  </button>
                </div>
              </div>

              {/* UV Atlas Resolution */}
              <div className="dcc-field-group">
                <span className="dcc-field-label">UV Atlas Resolution</span>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '4px' }}>
                  {[1024, 2048, 4096].map((res) => (
                    <button
                      key={res}
                      type="button"
                      style={{ fontSize: '10px', padding: '5px 0' }}
                      className={uvSize === res ? 'active' : ''}
                      onClick={() => setUvSize(res)}
                    >
                      {res === 1024 ? '1K (Fast)' : res === 2048 ? '2K (Standard)' : '4K (Ultra)'}
                    </button>
                  ))}
                </div>
              </div>

              {/* Seam Inpainting Mode */}
              <div className="dcc-field-group">
                <span className="dcc-field-label">Seam Inpaint Filter</span>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '4px' }}>
                  <button
                    type="button"
                    style={{ fontSize: '10px', padding: '5px 0' }}
                    className={inpaintMode === 'uv' ? 'active' : ''}
                    onClick={() => setInpaintMode('uv')}
                  >
                    Atlas Crisp
                  </button>
                  <button
                    type="button"
                    style={{ fontSize: '10px', padding: '5px 0' }}
                    className={inpaintMode === 'view' ? 'active' : ''}
                    onClick={() => setInpaintMode('view')}
                  >
                    View Blend
                  </button>
                </div>
              </div>

              {/* Diffusion Steps */}
              <div className="dcc-field-group">
                <div className="dcc-field-label" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span>Bake Denoising Steps</span>
                  <span style={{ fontFamily: 'var(--font-mono)' }}>{bakeSteps}</span>
                </div>
                <input
                  type="range"
                  min="20"
                  max="75"
                  step="5"
                  value={bakeSteps}
                  onChange={(e) => setBakeSteps(parseInt(e.target.value, 10))}
                />
              </div>

              {/* Rebake Trigger Button */}
              <button
                type="button"
                className="primary"
                disabled={!jobId || isRebaking}
                onClick={handleRebake}
                style={{
                  width: '100%',
                  padding: '10px 0',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '8px',
                  opacity: !jobId || isRebaking ? 0.6 : 1,
                }}
              >
                {isRebaking ? (
                  <>
                    <RefreshCw size={13} className="spin" />
                    <span>Re-Projecting UV Atlas…</span>
                  </>
                ) : (
                  <>
                    <RotateCcw size={13} />
                    <span>Rebake UV Map</span>
                  </>
                )}
              </button>

              {rebakeMessage && (
                <div
                  style={{
                    fontSize: '11px',
                    padding: '8px',
                    borderRadius: '4px',
                    background: rebakeMessage.startsWith('Error') ? 'rgba(239, 68, 68, 0.1)' : 'rgba(16, 185, 129, 0.1)',
                    color: rebakeMessage.startsWith('Error') ? 'var(--ruby-danger)' : 'var(--emerald-accent)',
                    borderLeft: `3px solid ${rebakeMessage.startsWith('Error') ? 'var(--ruby-danger)' : 'var(--emerald-accent)'}`,
                  }}
                >
                  {rebakeMessage}
                </div>
              )}
            </div>
          )}

          {/* Export Tab */}
          {activeTab === 'export' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              <p style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                Export game-engine ready rigged model with embedded textures and skin weights.
              </p>
              {onDownloadGlb && (
                <button
                  type="button"
                  className="primary"
                  onClick={onDownloadGlb}
                  style={{ width: '100%', padding: '10px 0' }}
                >
                  <Download size={14} />
                  <span>Download Skinned GLB</span>
                </button>
              )}
            </div>
          )}
        </div>
      </div>
    </aside>
  )
}
