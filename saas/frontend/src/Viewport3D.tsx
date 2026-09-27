import { useEffect, useRef, useState, useCallback } from 'react'
import * as THREE from 'three'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import {
  Maximize2,
  Camera,
  Download,
  Grid,
  Sun,
  RotateCw,
  Box,
  Layers,
  Sparkles,
} from 'lucide-react'

export type ShadingMode = 'rendered' | 'material' | 'solid' | 'wireframe' | 'normals' | 'skeleton'
export type LightingPreset = 'studio' | 'outdoor' | 'neon' | 'dark'

type Props = {
  src: string | null
  jobId?: number | null
  onDownloadGlb?: () => void
  onMeshStats?: (stats: { tris: number; verts: number; bones: number; dims: [number, number, number] }) => void

  // Interactive Scene & Transform Props from Outliner/Parent
  location?: [number, number, number]
  rotation?: [number, number, number] // in degrees
  scale?: [number, number, number]
  visibleMesh?: boolean
  visibleArmature?: boolean
  visibleLights?: boolean
  roughness?: number
  metalness?: number
  cameraTrigger?: number
  onTextureDetails?: (details: { width: number; height: number; format: string }) => void
}

export function Viewport3D({
  src,
  jobId,
  onDownloadGlb,
  onMeshStats,
  location = [0, 0, 0],
  rotation = [0, 0, 0],
  scale = [1, 1, 1],
  visibleMesh = true,
  visibleArmature = false,
  visibleLights = true,
  roughness = 0.4,
  metalness = 0.1,
  cameraTrigger = 0,
  onTextureDetails,
}: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const canvasRef = useRef<HTMLCanvasElement | null>(null)

  // Viewport Settings State
  const [shadingMode, setShadingMode] = useState<ShadingMode>('rendered')
  const [lightingPreset, setLightingPreset] = useState<LightingPreset>('studio')
  const [showGrid, setShowGrid] = useState(true)
  const [showShadow, setShowShadow] = useState(true)
  const [autoRotate, setAutoRotate] = useState(false)
  const [stats, setStats] = useState({ tris: 0, verts: 0, bones: 0, dims: [0, 0, 0] as [number, number, number] })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Three.js Core Refs
  const sceneRef = useRef<THREE.Scene | null>(null)
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null)
  const controlsRef = useRef<OrbitControls | null>(null)
  const modelGroupRef = useRef<THREE.Group | null>(null)
  const loadedRootRef = useRef<THREE.Group | null>(null)
  const baseOffsetRef = useRef<{ x: number; y: number; z: number }>({ x: 0, y: 0, z: 0 })
  const skeletonHelperRef = useRef<THREE.SkeletonHelper | null>(null)
  const gridHelperRef = useRef<THREE.GridHelper | null>(null)
  const shadowPlaneRef = useRef<THREE.Mesh | null>(null)
  const lightsGroupRef = useRef<THREE.Group | null>(null)
  const originalMaterialsRef = useRef<Map<THREE.Mesh, THREE.Material | THREE.Material[]>>(new Map())
  const autoRotateRef = useRef(false)

  // Focus on model
  const focusModel = useCallback(() => {
    if (!cameraRef.current || !controlsRef.current) return
    let center = new THREE.Vector3(0, 1, 0)
    let cameraZ = 3.5

    if (loadedRootRef.current) {
      const box = new THREE.Box3().setFromObject(loadedRootRef.current)
      if (!box.isEmpty()) {
        center = box.getCenter(new THREE.Vector3())
        const size = box.getSize(new THREE.Vector3())
        const maxDim = Math.max(size.x, size.y, size.z)
        const fov = cameraRef.current.fov * (Math.PI / 180)
        cameraZ = Math.abs((maxDim / 2) / Math.tan(fov / 2)) * 1.6
        cameraZ = Math.max(cameraZ, 2.2)
      }
    }

    cameraRef.current.position.set(center.x, center.y + 0.3, center.z + cameraZ)
    controlsRef.current.target.copy(center)
    controlsRef.current.update()
  }, [])

  // Camera preset view
  const setCameraView = (view: 'front' | 'side' | 'top' | 'iso') => {
    if (!cameraRef.current || !controlsRef.current) return
    let center = new THREE.Vector3(0, 1, 0)
    let dist = 3.2

    if (loadedRootRef.current) {
      const box = new THREE.Box3().setFromObject(loadedRootRef.current)
      if (!box.isEmpty()) {
        center = box.getCenter(new THREE.Vector3())
        const size = box.getSize(new THREE.Vector3())
        dist = Math.max(size.y, size.x, size.z) * 2.2
      }
    }

    if (view === 'front') {
      cameraRef.current.position.set(center.x, center.y, center.z + dist)
    } else if (view === 'side') {
      cameraRef.current.position.set(center.x + dist, center.y, center.z)
    } else if (view === 'top') {
      cameraRef.current.position.set(center.x, center.y + dist, center.z + 0.001)
    } else if (view === 'iso') {
      cameraRef.current.position.set(center.x + dist * 0.7, center.y + dist * 0.5, center.z + dist * 0.7)
    }
    controlsRef.current.target.copy(center)
    controlsRef.current.update()
  }

  // Snapshot capture
  const captureSnapshot = () => {
    const canvas = canvasRef.current
    if (!canvas) return
    const url = canvas.toDataURL('image/png')
    const a = document.createElement('a')
    a.href = url
    a.download = `yeetgen_asset_${jobId ?? 'export'}_screenshot.png`
    a.click()
  }

  // Synchronize autoRotate ref
  useEffect(() => {
    autoRotateRef.current = autoRotate
    if (controlsRef.current) {
      controlsRef.current.autoRotate = autoRotate
    }
  }, [autoRotate])

  // React to camera trigger from outliner or parent
  useEffect(() => {
    if (cameraTrigger && cameraTrigger > 0) {
      focusModel()
    }
  }, [cameraTrigger, focusModel])

  // Setup Three.js Scene ONCE on mount
  useEffect(() => {
    const container = containerRef.current
    const canvas = canvasRef.current
    if (!container || !canvas) return

    const scene = new THREE.Scene()
    scene.background = new THREE.Color(0xE0E5EC) // Monochromatic clay surface
    sceneRef.current = scene

    const camera = new THREE.PerspectiveCamera(45, container.clientWidth / container.clientHeight, 0.05, 500)
    camera.position.set(0, 1.2, 3.5)
    cameraRef.current = camera

    const renderer = new THREE.WebGLRenderer({
      canvas,
      antialias: true,
      preserveDrawingBuffer: true,
      powerPreference: 'high-performance',
    })
    renderer.setSize(container.clientWidth, container.clientHeight)
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    renderer.shadowMap.enabled = true
    renderer.shadowMap.type = THREE.PCFSoftShadowMap
    renderer.toneMapping = THREE.ACESFilmicToneMapping
    renderer.toneMappingExposure = 1.05

    const controls = new OrbitControls(camera, canvas)
    controls.enableDamping = true
    controls.dampingFactor = 0.08
    controls.maxDistance = 50
    controls.minDistance = 0.2
    controls.target.set(0, 1, 0)
    controlsRef.current = controls

    // Soft UI Ground Grid
    const grid = new THREE.GridHelper(10, 20, 0xA3B1C6, 0xCBD5E1)
    grid.position.y = 0
    scene.add(grid)
    gridHelperRef.current = grid

    // Soft Shadow Floor Plane
    const planeGeo = new THREE.PlaneGeometry(15, 15)
    const planeMat = new THREE.ShadowMaterial({ opacity: 0.25 })
    const shadowPlane = new THREE.Mesh(planeGeo, planeMat)
    shadowPlane.rotation.x = -Math.PI / 2
    shadowPlane.receiveShadow = true
    scene.add(shadowPlane)
    shadowPlaneRef.current = shadowPlane

    // Lighting Group
    const lightsGroup = new THREE.Group()
    scene.add(lightsGroup)
    lightsGroupRef.current = lightsGroup

    // Model Group
    const modelGroup = new THREE.Group()
    scene.add(modelGroup)
    modelGroupRef.current = modelGroup

    // Keyboard Shortcuts (F for focus)
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return
      if (e.key.toLowerCase() === 'f') {
        focusModel()
      }
    }
    window.addEventListener('keydown', onKeyDown)

    // Render loop
    let animId: number
    const animate = () => {
      animId = requestAnimationFrame(animate)
      if (controlsRef.current) {
        controlsRef.current.autoRotate = autoRotateRef.current
        controlsRef.current.update()
      }
      renderer.render(scene, camera)
    }
    animate()

    // Resize observer
    const ro = new ResizeObserver(() => {
      if (!container || !renderer || !camera) return
      camera.aspect = container.clientWidth / container.clientHeight
      camera.updateProjectionMatrix()
      renderer.setSize(container.clientWidth, container.clientHeight)
    })
    ro.observe(container)

    return () => {
      cancelAnimationFrame(animId)
      window.removeEventListener('keydown', onKeyDown)
      ro.disconnect()
      renderer.dispose()
      grid.geometry.dispose()
      planeGeo.dispose()
      planeMat.dispose()
    }
  }, [focusModel])

  // Update Lighting Presets
  useEffect(() => {
    const group = lightsGroupRef.current
    if (!group) return

    while (group.children.length > 0) {
      const obj = group.children[0]
      group.remove(obj)
      if ((obj as THREE.Light).dispose) (obj as THREE.Light).dispose()
    }

    if (lightingPreset === 'studio') {
      const amb = new THREE.AmbientLight(0xffffff, 0.9)
      const key = new THREE.DirectionalLight(0xffffff, 2.4)
      key.position.set(-4, 6, 4)
      key.castShadow = true
      key.shadow.mapSize.set(2048, 2048)

      const fill = new THREE.DirectionalLight(0xA3B1C6, 1.2)
      fill.position.set(4, -3, -2)

      const rim = new THREE.DirectionalLight(0x8B84FF, 1.2)
      rim.position.set(0, 5, -5)

      group.add(amb, key, fill, rim)
    } else if (lightingPreset === 'outdoor') {
      const amb = new THREE.AmbientLight(0xdbeafe, 0.9)
      const sun = new THREE.DirectionalLight(0xfffaed, 3.0)
      sun.position.set(-6, 8, 3)
      sun.castShadow = true
      sun.shadow.mapSize.set(2048, 2048)
      group.add(amb, sun)
    } else if (lightingPreset === 'neon') {
      const amb = new THREE.AmbientLight(0xE0E5EC, 0.6)
      const violet = new THREE.DirectionalLight(0x6C63FF, 3.5)
      violet.position.set(-4, 4, 3)
      const teal = new THREE.DirectionalLight(0x38B2AC, 3.5)
      teal.position.set(4, 3, -3)
      group.add(amb, violet, teal)
    } else {
      // Dark
      const amb = new THREE.AmbientLight(0xffffff, 0.4)
      const spot = new THREE.SpotLight(0xffffff, 2.5, 15, Math.PI / 4, 0.5)
      spot.position.set(0, 6, 2)
      spot.castShadow = true
      group.add(amb, spot)
    }
  }, [lightingPreset])

  // Lights Visibility (Outliner toggle)
  useEffect(() => {
    if (lightsGroupRef.current) {
      lightsGroupRef.current.visible = visibleLights
    }
  }, [visibleLights])

  // Grid and Shadow Toggles
  useEffect(() => {
    if (gridHelperRef.current) gridHelperRef.current.visible = showGrid
    if (shadowPlaneRef.current) shadowPlaneRef.current.visible = showShadow
  }, [showGrid, showShadow])

  // Apply Shading Mode
  const applyShadingMode = useCallback((mode: ShadingMode) => {
    if (!loadedRootRef.current) return

    loadedRootRef.current.traverse((node) => {
      if (!(node as THREE.Mesh).isMesh) return
      const mesh = node as THREE.Mesh
      const original = originalMaterialsRef.current.get(mesh)
      if (!original) return

      const origMat = Array.isArray(original) ? original[0] : original

      if (mode === 'rendered') {
        mesh.material = original
        const mats = Array.isArray(mesh.material) ? mesh.material : [mesh.material]
        mats.forEach((m: any) => {
          m.wireframe = false
          if ('roughness' in m && roughness != null) m.roughness = roughness
          if ('metalness' in m && metalness != null) m.metalness = metalness
          m.needsUpdate = true
        })
        mesh.visible = visibleMesh
      } else if (mode === 'wireframe') {
        mesh.material = original
        const mats = Array.isArray(mesh.material) ? mesh.material : [mesh.material]
        mats.forEach((m: any) => {
          m.wireframe = true
          m.needsUpdate = true
        })
        mesh.visible = true
      } else if (mode === 'material') {
        // BaseColor Unlit Preview
        const clone = (origMat as THREE.MeshStandardMaterial).clone()
        clone.roughness = 1.0
        clone.metalness = 0.0
        if (clone.map) {
          clone.emissiveMap = clone.map
          clone.emissive = new THREE.Color(0xffffff)
        }
        clone.wireframe = false
        clone.needsUpdate = true
        mesh.material = clone
        mesh.visible = true
      } else if (mode === 'solid') {
        // Soft Matte Clay Sculpt
        const clone = (origMat as THREE.MeshStandardMaterial).clone()
        clone.map = null
        clone.color = new THREE.Color(0xD9E2EC)
        clone.roughness = 0.65
        clone.metalness = 0.05
        clone.wireframe = false
        clone.needsUpdate = true
        mesh.material = clone
        mesh.visible = true
      } else if (mode === 'normals') {
        const normMat = new THREE.MeshNormalMaterial({ wireframe: false })
        mesh.material = normMat
        mesh.visible = true
      } else if (mode === 'skeleton') {
        const clone = (origMat as THREE.MeshStandardMaterial).clone()
        clone.transparent = true
        clone.opacity = 0.22
        clone.roughness = 0.8
        clone.wireframe = false
        clone.needsUpdate = true
        mesh.material = clone
        mesh.visible = true
      }
    })

    if (skeletonHelperRef.current) {
      skeletonHelperRef.current.visible = mode === 'skeleton' || visibleArmature
    }
  }, [roughness, metalness, visibleMesh, visibleArmature])

  // Re-apply shading mode whenever shadingMode or active model changes
  useEffect(() => {
    applyShadingMode(shadingMode)
  }, [shadingMode, applyShadingMode])

  // Live Roughness & Metalness Adjustments on rendered material
  useEffect(() => {
    if (!loadedRootRef.current || shadingMode !== 'rendered') return
    loadedRootRef.current.traverse((node) => {
      if ((node as THREE.Mesh).isMesh) {
        const mesh = node as THREE.Mesh
        const mats = Array.isArray(mesh.material) ? mesh.material : [mesh.material]
        for (const mat of mats) {
          if ('roughness' in mat && roughness != null) {
            ;(mat as THREE.MeshStandardMaterial).roughness = roughness
            mat.needsUpdate = true
          }
          if ('metalness' in mat && metalness != null) {
            ;(mat as THREE.MeshStandardMaterial).metalness = metalness
            mat.needsUpdate = true
          }
        }
      }
    })
  }, [roughness, metalness, shadingMode])

  // Live Mesh Visibility Toggle
  useEffect(() => {
    if (!loadedRootRef.current) return
    loadedRootRef.current.traverse((node) => {
      if ((node as THREE.Mesh).isMesh) {
        node.visible = visibleMesh
      }
    })
  }, [visibleMesh])

  // Live Armature Visibility Toggle
  useEffect(() => {
    if (skeletonHelperRef.current) {
      skeletonHelperRef.current.visible = visibleArmature || shadingMode === 'skeleton'
    }
  }, [visibleArmature, shadingMode])

  // Live Model Location, Rotation, Scale (Transform tab)
  useEffect(() => {
    if (!loadedRootRef.current) return
    const root = loadedRootRef.current
    root.position.set(
      baseOffsetRef.current.x + (location ? location[0] : 0),
      baseOffsetRef.current.y + (location ? location[1] : 0),
      baseOffsetRef.current.z + (location ? location[2] : 0)
    )
    if (rotation) {
      root.rotation.set(
        THREE.MathUtils.degToRad(rotation[0]),
        THREE.MathUtils.degToRad(rotation[1]),
        THREE.MathUtils.degToRad(rotation[2])
      )
    }
    if (scale) {
      root.scale.set(scale[0], scale[1], scale[2])
    }
  }, [location, rotation, scale])

  // Load GLB Model
  useEffect(() => {
    if (!src) {
      if (modelGroupRef.current) {
        while (modelGroupRef.current.children.length > 0) {
          modelGroupRef.current.remove(modelGroupRef.current.children[0])
        }
      }
      if (skeletonHelperRef.current && sceneRef.current) {
        sceneRef.current.remove(skeletonHelperRef.current)
        skeletonHelperRef.current = null
      }
      loadedRootRef.current = null
      return
    }

    setLoading(true)
    setError(null)
    const loader = new GLTFLoader()

    loader.load(
      src,
      (gltf) => {
        const root = gltf.scene
        if (!modelGroupRef.current || !sceneRef.current) return

        // Clear existing model
        while (modelGroupRef.current.children.length > 0) {
          modelGroupRef.current.remove(modelGroupRef.current.children[0])
        }
        if (skeletonHelperRef.current) {
          sceneRef.current.remove(skeletonHelperRef.current)
          skeletonHelperRef.current = null
        }
        originalMaterialsRef.current.clear()

        let totalTris = 0
        let totalVerts = 0
        let totalBones = 0
        let hasSkinnedMesh = false
        let detectedTexture = false

        root.traverse((node) => {
          if ((node as THREE.Mesh).isMesh) {
            const mesh = node as THREE.Mesh
            mesh.castShadow = true
            mesh.receiveShadow = true
            originalMaterialsRef.current.set(mesh, mesh.material)

            if (mesh.geometry) {
              const geo = mesh.geometry
              if (geo.index) {
                totalTris += geo.index.count / 3
              } else if (geo.attributes.position) {
                totalTris += geo.attributes.position.count / 3
              }
              if (geo.attributes.position) {
                totalVerts += geo.attributes.position.count
              }
            }

            // Inspect texture map resolution
            if (!detectedTexture) {
              const mats = Array.isArray(mesh.material) ? mesh.material : [mesh.material]
              for (const m of mats) {
                const stdMat = m as THREE.MeshStandardMaterial
                if (stdMat.map && stdMat.map.image) {
                  const img = stdMat.map.image as any
                  const w = Number(img?.width) || 4096
                  const h = Number(img?.height) || 4096
                  onTextureDetails?.({ width: w, height: h, format: 'Embedded PBR Atlas' })
                  detectedTexture = true
                  break
                }
              }
            }
          }
          if ((node as THREE.Bone).isBone) {
            totalBones++
          }
          if ((node as THREE.SkinnedMesh).isSkinnedMesh) {
            hasSkinnedMesh = true
          }
        })

        // Center on floor
        const box = new THREE.Box3().setFromObject(root)
        const center = box.getCenter(new THREE.Vector3())
        const size = box.getSize(new THREE.Vector3())

        baseOffsetRef.current = {
          x: -center.x,
          y: -box.min.y,
          z: -center.z,
        }

        root.position.set(
          baseOffsetRef.current.x + (location ? location[0] : 0),
          baseOffsetRef.current.y + (location ? location[1] : 0),
          baseOffsetRef.current.z + (location ? location[2] : 0)
        )
        if (rotation) {
          root.rotation.set(
            THREE.MathUtils.degToRad(rotation[0]),
            THREE.MathUtils.degToRad(rotation[1]),
            THREE.MathUtils.degToRad(rotation[2])
          )
        }
        if (scale) {
          root.scale.set(scale[0], scale[1], scale[2])
        }

        modelGroupRef.current.add(root)
        loadedRootRef.current = root

        // Skeleton Helper if rigged
        if (hasSkinnedMesh || totalBones > 0) {
          const helper = new THREE.SkeletonHelper(root)
          helper.visible = visibleArmature || shadingMode === 'skeleton'
          sceneRef.current.add(helper)
          skeletonHelperRef.current = helper
        }

        const newStats = {
          tris: Math.round(totalTris),
          verts: Math.round(totalVerts),
          bones: totalBones,
          dims: [Number(size.x.toFixed(2)), Number(size.y.toFixed(2)), Number(size.z.toFixed(2))] as [number, number, number],
        }
        setStats(newStats)
        if (onMeshStats) onMeshStats(newStats)

        // Apply active shading and materials
        applyShadingMode(shadingMode)

        setLoading(false)
        focusModel()
      },
      undefined,
      (err) => {
        console.error('GLTF load error:', err)
        setError('Failed to load 3D GLB mesh asset.')
        setLoading(false)
      }
    )
  }, [src, focusModel, onMeshStats, onTextureDetails])

  return (
    <div ref={containerRef} className="dcc-viewport-container">
      <canvas ref={canvasRef} className="dcc-viewport-canvas" />

      {/* Top HUD: Shading Modes & Actions */}
      <div className="viewport-top-hud">
        {/* Shading Mode Switcher */}
        <div className="viewport-mode-pills">
          <button
            type="button"
            className={`viewport-mode-btn ${shadingMode === 'rendered' ? 'active' : ''}`}
            onClick={() => setShadingMode('rendered')}
            title="Rendered (PBR Lit with live Roughness & Metallic)"
            style={{ cursor: 'pointer' }}
          >
            <Sparkles size={13} />
            <span>PBR Lit</span>
          </button>
          <button
            type="button"
            className={`viewport-mode-btn ${shadingMode === 'material' ? 'active' : ''}`}
            onClick={() => setShadingMode('material')}
            title="Material Preview (Unlit Base Color Map)"
            style={{ cursor: 'pointer' }}
          >
            <Layers size={13} />
            <span>Material</span>
          </button>
          <button
            type="button"
            className={`viewport-mode-btn ${shadingMode === 'solid' ? 'active' : ''}`}
            onClick={() => setShadingMode('solid')}
            title="Solid (Clay Sculpt)"
            style={{ cursor: 'pointer' }}
          >
            <Box size={13} />
            <span>Solid</span>
          </button>
          <button
            type="button"
            className={`viewport-mode-btn ${shadingMode === 'wireframe' ? 'active' : ''}`}
            onClick={() => setShadingMode('wireframe')}
            title="Wireframe Mesh Overlay"
            style={{ cursor: 'pointer' }}
          >
            <span>Wire</span>
          </button>
          <button
            type="button"
            className={`viewport-mode-btn ${shadingMode === 'normals' ? 'active' : ''}`}
            onClick={() => setShadingMode('normals')}
            title="Surface Normals Inspection"
            style={{ cursor: 'pointer' }}
          >
            <span>Normals</span>
          </button>
          <button
            type="button"
            className={`viewport-mode-btn ${shadingMode === 'skeleton' ? 'active' : ''}`}
            onClick={() => setShadingMode('skeleton')}
            title="Skeleton & Joint Hierarchy X-Ray"
            style={{ cursor: 'pointer' }}
          >
            <span>Skeleton</span>
          </button>
        </div>

        {/* Viewport Action Tools */}
        <div className="viewport-actions-hud">
          {/* Lighting Preset */}
          <button
            type="button"
            className="viewport-mode-btn"
            onClick={() => {
              const next: LightingPreset =
                lightingPreset === 'studio' ? 'outdoor' : lightingPreset === 'outdoor' ? 'neon' : lightingPreset === 'neon' ? 'dark' : 'studio'
              setLightingPreset(next)
            }}
            title={`Lighting: ${lightingPreset}`}
            style={{ cursor: 'pointer' }}
          >
            <Sun size={13} />
            <span style={{ textTransform: 'capitalize' }}>{lightingPreset}</span>
          </button>

          {/* Grid Toggle */}
          <button
            type="button"
            className={`viewport-mode-btn ${showGrid ? 'active' : ''}`}
            onClick={() => setShowGrid((g) => !g)}
            title="Toggle Ground Grid"
            style={{ cursor: 'pointer' }}
          >
            <Grid size={13} />
          </button>

          {/* Floor Shadow Toggle */}
          <button
            type="button"
            className={`viewport-mode-btn ${showShadow ? 'active' : ''}`}
            onClick={() => setShowShadow((s) => !s)}
            title="Toggle Floor Shadows"
            style={{ cursor: 'pointer' }}
          >
            <span>Shadows</span>
          </button>

          {/* Turntable Auto Rotate */}
          <button
            type="button"
            className={`viewport-mode-btn ${autoRotate ? 'active' : ''}`}
            onClick={() => setAutoRotate((r) => !r)}
            title="Toggle Turntable Auto-Rotate"
            style={{ cursor: 'pointer' }}
          >
            <RotateCw size={13} />
          </button>

          {/* Focus Selected */}
          <button
            type="button"
            className="viewport-mode-btn"
            onClick={focusModel}
            title="Focus Frame (F)"
            style={{ cursor: 'pointer' }}
          >
            <Maximize2 size={13} />
          </button>

          {/* Snapshot Screenshot */}
          <button
            type="button"
            className="viewport-mode-btn"
            onClick={captureSnapshot}
            title="Capture Viewport Screenshot (PNG)"
            style={{ cursor: 'pointer' }}
          >
            <Camera size={13} />
          </button>

          {/* Download GLB */}
          {onDownloadGlb && (
            <button
              type="button"
              className="viewport-mode-btn primary"
              onClick={onDownloadGlb}
              title="Download Skinned GLB"
              style={{ cursor: 'pointer' }}
            >
              <Download size={13} />
              <span>Export GLB</span>
            </button>
          )}
        </div>
      </div>

      {/* 3D Orientation Navigation Gizmo Widget */}
      <div className="viewport-gizmo-box">
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 26px)', gap: '4px' }}>
          <div />
          <button
            type="button"
            className="viewport-mode-btn"
            style={{ padding: '2px', color: 'var(--accent)', fontWeight: 800, cursor: 'pointer' }}
            onClick={() => setCameraView('top')}
            title="Top View (Numpad 7)"
          >
            +Y
          </button>
          <div />

          <button
            type="button"
            className="viewport-mode-btn"
            style={{ padding: '2px', color: 'var(--danger)', fontWeight: 800, cursor: 'pointer' }}
            onClick={() => setCameraView('side')}
            title="Right Side View (Numpad 3)"
          >
            +X
          </button>
          <button
            type="button"
            className="viewport-mode-btn"
            style={{ padding: '2px', color: 'var(--text-primary)', fontWeight: 800, cursor: 'pointer' }}
            onClick={() => setCameraView('iso')}
            title="Isometric View"
          >
            ISO
          </button>
          <button
            type="button"
            className="viewport-mode-btn"
            style={{ padding: '2px', color: 'var(--accent-secondary)', fontWeight: 800, cursor: 'pointer' }}
            onClick={() => setCameraView('front')}
            title="Front View (Numpad 1)"
          >
            +Z
          </button>
        </div>
      </div>

      {/* Bottom HUD: Mesh Metrics & Dimensions */}
      <div className="viewport-bottom-hud">
        {loading ? (
          <span>Loading 3D asset geometry…</span>
        ) : error ? (
          <span style={{ color: 'var(--danger)' }}>{error}</span>
        ) : src ? (
          <>
            <span>Tris: <strong>{stats.tris.toLocaleString()}</strong></span>
            <span>Verts: <strong>{stats.verts.toLocaleString()}</strong></span>
            <span>Bones: <strong>{stats.bones}</strong></span>
            <span>Dim: <strong>{stats.dims[0]}m × {stats.dims[1]}m × {stats.dims[2]}m</strong></span>
          </>
        ) : (
          <span>No asset loaded · Select or generate an asset from the studio</span>
        )}
      </div>
    </div>
  )
}
