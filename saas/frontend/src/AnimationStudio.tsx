import { useEffect, useRef, useState, useCallback } from 'react'
import * as THREE from 'three'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import {
  Play,
  Pause,
  SkipBack,
  ChevronLeft,
  ChevronRight,
  Repeat,
  Upload,
  Activity,
} from 'lucide-react'

type Props = {
  src: string | null
  jobId?: number | null
}

type ClipInfo = {
  name: string
  label: string
  duration: number
  isEmbedded: boolean
}

// Generate keyframed humanoid animation clips targeting humanoid armature bone names
function createHumanoidClip(name: string, root: THREE.Object3D): THREE.AnimationClip | null {
  const bones: THREE.Bone[] = []
  root.traverse((o) => {
    if ((o as THREE.Bone).isBone) bones.push(o as THREE.Bone)
  })
  if (bones.length === 0) return null

  // Classify bones by vertical position & lateral position
  root.updateMatrixWorld(true)
  const withPos = bones.map((b) => {
    const v = new THREE.Vector3()
    b.getWorldPosition(v)
    return { bone: b, pos: v }
  })
  withPos.sort((a, b) => a.pos.y - b.pos.y)

  const n = withPos.length
  const lower = withPos.slice(0, Math.max(1, Math.floor(n * 0.35)))
  const mid = withPos.slice(Math.floor(n * 0.35), Math.floor(n * 0.7))
  const upper = withPos.slice(Math.floor(n * 0.7))

  const leftLegs = lower.filter((x) => x.pos.x < -0.02).map((x) => x.bone)
  const rightLegs = lower.filter((x) => x.pos.x > 0.02).map((x) => x.bone)
  const spineBones = mid.map((x) => x.bone)
  const leftArms = upper.filter((x) => x.pos.x < -0.03).map((x) => x.bone)
  const rightArms = upper.filter((x) => x.pos.x > 0.03).map((x) => x.bone)
  const rootBone = bones[0]

  const tracks: THREE.KeyframeTrack[] = []

  if (name === 'idle') {
    const duration = 2.4
    const times = [0, 0.6, 1.2, 1.8, 2.4]

    // Spine breathing quaternion keyframes
    spineBones.forEach((b) => {
      const qRest = b.quaternion.clone()
      const qBreath = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(1, 0, 0), 0.04).multiply(qRest)
      const values = [
        qRest.x, qRest.y, qRest.z, qRest.w,
        qBreath.x, qBreath.y, qBreath.z, qBreath.w,
        qRest.x, qRest.y, qRest.z, qRest.w,
        qBreath.x, qBreath.y, qBreath.z, qBreath.w,
        qRest.x, qRest.y, qRest.z, qRest.w,
      ]
      tracks.push(new THREE.QuaternionKeyframeTrack(`${b.name}.quaternion`, times, values))
    })

    // Root subtle vertical breathing
    if (rootBone) {
      const p = rootBone.position
      const values = [
        p.x, p.y, p.z,
        p.x, p.y + 0.015, p.z,
        p.x, p.y, p.z,
        p.x, p.y + 0.015, p.z,
        p.x, p.y, p.z,
      ]
      tracks.push(new THREE.VectorKeyframeTrack(`${rootBone.name}.position`, times, values))
    }

    return new THREE.AnimationClip('Idle', duration, tracks)
  }

  if (name === 'walk') {
    const duration = 1.2
    const times = [0, 0.3, 0.6, 0.9, 1.2]

    leftLegs.forEach((b) => {
      const qRest = b.quaternion.clone()
      const qFwd = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(1, 0, 0), 0.35).multiply(qRest)
      const qBack = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(1, 0, 0), -0.35).multiply(qRest)
      const values = [
        qRest.x, qRest.y, qRest.z, qRest.w,
        qFwd.x, qFwd.y, qFwd.z, qFwd.w,
        qRest.x, qRest.y, qRest.z, qRest.w,
        qBack.x, qBack.y, qBack.z, qBack.w,
        qRest.x, qRest.y, qRest.z, qRest.w,
      ]
      tracks.push(new THREE.QuaternionKeyframeTrack(`${b.name}.quaternion`, times, values))
    })

    rightLegs.forEach((b) => {
      const qRest = b.quaternion.clone()
      const qFwd = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(1, 0, 0), 0.35).multiply(qRest)
      const qBack = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(1, 0, 0), -0.35).multiply(qRest)
      const values = [
        qRest.x, qRest.y, qRest.z, qRest.w,
        qBack.x, qBack.y, qBack.z, qBack.w,
        qRest.x, qRest.y, qRest.z, qRest.w,
        qFwd.x, qFwd.y, qFwd.z, qFwd.w,
        qRest.x, qRest.y, qRest.z, qRest.w,
      ]
      tracks.push(new THREE.QuaternionKeyframeTrack(`${b.name}.quaternion`, times, values))
    })

    leftArms.forEach((b) => {
      const qRest = b.quaternion.clone()
      const qFwd = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(1, 0, 0), -0.3).multiply(qRest)
      const qBack = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(1, 0, 0), 0.3).multiply(qRest)
      const values = [
        qRest.x, qRest.y, qRest.z, qRest.w,
        qBack.x, qBack.y, qBack.z, qBack.w,
        qRest.x, qRest.y, qRest.z, qRest.w,
        qFwd.x, qFwd.y, qFwd.z, qFwd.w,
        qRest.x, qRest.y, qRest.z, qRest.w,
      ]
      tracks.push(new THREE.QuaternionKeyframeTrack(`${b.name}.quaternion`, times, values))
    })

    rightArms.forEach((b) => {
      const qRest = b.quaternion.clone()
      const qFwd = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(1, 0, 0), -0.3).multiply(qRest)
      const qBack = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(1, 0, 0), 0.3).multiply(qRest)
      const values = [
        qRest.x, qRest.y, qRest.z, qRest.w,
        qFwd.x, qFwd.y, qFwd.z, qFwd.w,
        qRest.x, qRest.y, qRest.z, qRest.w,
        qBack.x, qBack.y, qBack.z, qBack.w,
        qRest.x, qRest.y, qRest.z, qRest.w,
      ]
      tracks.push(new THREE.QuaternionKeyframeTrack(`${b.name}.quaternion`, times, values))
    })

    return new THREE.AnimationClip('Walk Cycle', duration, tracks)
  }

  if (name === 'sprint') {
    const duration = 0.8
    const times = [0, 0.2, 0.4, 0.6, 0.8]

    leftLegs.forEach((b) => {
      const qRest = b.quaternion.clone()
      const qFwd = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(1, 0, 0), 0.6).multiply(qRest)
      const qBack = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(1, 0, 0), -0.5).multiply(qRest)
      const values = [
        qRest.x, qRest.y, qRest.z, qRest.w,
        qFwd.x, qFwd.y, qFwd.z, qFwd.w,
        qRest.x, qRest.y, qRest.z, qRest.w,
        qBack.x, qBack.y, qBack.z, qBack.w,
        qRest.x, qRest.y, qRest.z, qRest.w,
      ]
      tracks.push(new THREE.QuaternionKeyframeTrack(`${b.name}.quaternion`, times, values))
    })

    rightLegs.forEach((b) => {
      const qRest = b.quaternion.clone()
      const qFwd = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(1, 0, 0), 0.6).multiply(qRest)
      const qBack = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(1, 0, 0), -0.5).multiply(qRest)
      const values = [
        qRest.x, qRest.y, qRest.z, qRest.w,
        qBack.x, qBack.y, qBack.z, qBack.w,
        qRest.x, qRest.y, qRest.z, qRest.w,
        qFwd.x, qFwd.y, qFwd.z, qFwd.w,
        qRest.x, qRest.y, qRest.z, qRest.w,
      ]
      tracks.push(new THREE.QuaternionKeyframeTrack(`${b.name}.quaternion`, times, values))
    })

    spineBones.forEach((b) => {
      const qLean = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(1, 0, 0), 0.15).multiply(b.quaternion)
      const values = [
        qLean.x, qLean.y, qLean.z, qLean.w,
        qLean.x, qLean.y, qLean.z, qLean.w,
        qLean.x, qLean.y, qLean.z, qLean.w,
        qLean.x, qLean.y, qLean.z, qLean.w,
        qLean.x, qLean.y, qLean.z, qLean.w,
      ]
      tracks.push(new THREE.QuaternionKeyframeTrack(`${b.name}.quaternion`, times, values))
    })

    return new THREE.AnimationClip('Sprint', duration, tracks)
  }

  if (name === 'combat') {
    const duration = 1.8
    const times = [0, 0.45, 0.9, 1.35, 1.8]

    spineBones.forEach((b) => {
      const qLean = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(1, 0, 0), 0.08).multiply(b.quaternion)
      const values = [
        qLean.x, qLean.y, qLean.z, qLean.w,
        qLean.x, qLean.y, qLean.z, qLean.w,
        qLean.x, qLean.y, qLean.z, qLean.w,
        qLean.x, qLean.y, qLean.z, qLean.w,
        qLean.x, qLean.y, qLean.z, qLean.w,
      ]
      tracks.push(new THREE.QuaternionKeyframeTrack(`${b.name}.quaternion`, times, values))
    })

    leftArms.forEach((b) => {
      const qGuard = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(1, 0, 0), -0.5).multiply(b.quaternion)
      const values = [
        qGuard.x, qGuard.y, qGuard.z, qGuard.w,
        qGuard.x, qGuard.y, qGuard.z, qGuard.w,
        qGuard.x, qGuard.y, qGuard.z, qGuard.w,
        qGuard.x, qGuard.y, qGuard.z, qGuard.w,
        qGuard.x, qGuard.y, qGuard.z, qGuard.w,
      ]
      tracks.push(new THREE.QuaternionKeyframeTrack(`${b.name}.quaternion`, times, values))
    })

    return new THREE.AnimationClip('Combat Stance', duration, tracks)
  }

  if (name === 'attack') {
    const duration = 1.0
    const times = [0, 0.3, 0.5, 0.7, 1.0]

    rightArms.forEach((b) => {
      const qRest = b.quaternion.clone()
      const qWindup = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(1, 0, 0), 0.4).multiply(qRest)
      const qStrike = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(1, 0, 0), -0.9).multiply(qRest)
      const values = [
        qRest.x, qRest.y, qRest.z, qRest.w,
        qWindup.x, qWindup.y, qWindup.z, qWindup.w,
        qStrike.x, qStrike.y, qStrike.z, qStrike.w,
        qStrike.x, qStrike.y, qStrike.z, qStrike.w,
        qRest.x, qRest.y, qRest.z, qRest.w,
      ]
      tracks.push(new THREE.QuaternionKeyframeTrack(`${b.name}.quaternion`, times, values))
    })

    return new THREE.AnimationClip('Attack Strike', duration, tracks)
  }

  if (name === 'cheer') {
    const duration = 1.6
    const times = [0, 0.4, 0.8, 1.2, 1.6]

    leftArms.concat(rightArms).forEach((b) => {
      const qRest = b.quaternion.clone()
      const qUp = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 0, 1), 1.2).multiply(qRest)
      const values = [
        qRest.x, qRest.y, qRest.z, qRest.w,
        qUp.x, qUp.y, qUp.z, qUp.w,
        qUp.x, qUp.y, qUp.z, qUp.w,
        qUp.x, qUp.y, qUp.z, qUp.w,
        qRest.x, qRest.y, qRest.z, qRest.w,
      ]
      tracks.push(new THREE.QuaternionKeyframeTrack(`${b.name}.quaternion`, times, values))
    })

    return new THREE.AnimationClip('Victory Cheer', duration, tracks)
  }

  return null
}

export function AnimationStudio({ src }: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const canvasRef = useRef<HTMLCanvasElement | null>(null)

  // Playback State
  const [playing, setPlaying] = useState(true)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(1.0)
  const [playbackSpeed, setPlaybackSpeed] = useState(1.0)
  const [loop, setLoop] = useState(true)
  const [selectedClipName, setSelectedClipName] = useState<string>('Idle')
  const [availableClips, setAvailableClips] = useState<ClipInfo[]>([])

  // Three.js Engine Refs
  const mixerRef = useRef<THREE.AnimationMixer | null>(null)
  const clipsMapRef = useRef<Map<string, THREE.AnimationClip>>(new Map())
  const activeActionRef = useRef<THREE.AnimationAction | null>(null)
  const sceneRef = useRef<THREE.Scene | null>(null)
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null)
  const modelGroupRef = useRef<THREE.Group | null>(null)
  const skeletonHelperRef = useRef<THREE.SkeletonHelper | null>(null)

  // Play / Switch animation clip with cross-fade
  const playClip = useCallback((clipName: string) => {
    const mixer = mixerRef.current
    const clip = clipsMapRef.current.get(clipName)
    if (!mixer || !clip) return

    const prevAction = activeActionRef.current
    const newAction = mixer.clipAction(clip)

    if (prevAction && prevAction !== newAction) {
      prevAction.fadeOut(0.2)
    }

    newAction.reset()
    newAction.fadeIn(0.2)
    newAction.play()
    newAction.setLoop(loop ? THREE.LoopRepeat : THREE.LoopOnce, Infinity)
    newAction.timeScale = playbackSpeed

    activeActionRef.current = newAction
    setSelectedClipName(clipName)
    setDuration(clip.duration || 1.0)
  }, [loop, playbackSpeed])

  // Scrub timeline
  const handleScrub = (timeVal: number) => {
    setCurrentTime(timeVal)
    if (activeActionRef.current && mixerRef.current) {
      activeActionRef.current.time = timeVal
      mixerRef.current.update(0)
    }
  }

  // Setup Scene
  useEffect(() => {
    const container = containerRef.current
    const canvas = canvasRef.current
    if (!container || !canvas) return

    const scene = new THREE.Scene()
    scene.background = new THREE.Color(0xE0E5EC) // Monochromatic clay surface
    sceneRef.current = scene

    const camera = new THREE.PerspectiveCamera(45, container.clientWidth / container.clientHeight, 0.05, 500)
    camera.position.set(0, 1.4, 3.8)
    cameraRef.current = camera

    const renderer = new THREE.WebGLRenderer({ canvas, antialias: true })
    renderer.setSize(container.clientWidth, container.clientHeight)
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    renderer.shadowMap.enabled = true
    renderer.toneMapping = THREE.ACESFilmicToneMapping

    const controls = new OrbitControls(camera, canvas)
    controls.enableDamping = true
    controls.target.set(0, 0.9, 0)

    // Dual Opposing Soft Lights
    const amb = new THREE.AmbientLight(0xffffff, 0.9)
    const dir = new THREE.DirectionalLight(0xffffff, 2.4)
    dir.position.set(-3, 5, 3)
    dir.castShadow = true
    const rim = new THREE.DirectionalLight(0x6C63FF, 1.6)
    rim.position.set(3, -2, -3)
    scene.add(amb, dir, rim)

    // Floor Grid
    const grid = new THREE.GridHelper(10, 20, 0xA3B1C6, 0xCBD5E1)
    scene.add(grid)

    const modelGroup = new THREE.Group()
    scene.add(modelGroup)
    modelGroupRef.current = modelGroup

    const clock = new THREE.Clock()
    let animId: number

    const animate = () => {
      animId = requestAnimationFrame(animate)
      const delta = clock.getDelta()

      if (mixerRef.current && playing) {
        mixerRef.current.update(delta * playbackSpeed)
        if (activeActionRef.current) {
          setCurrentTime(activeActionRef.current.time % (activeActionRef.current.getClip().duration || 1))
        }
      }

      controls.update()
      renderer.render(scene, camera)
    }
    animate()

    const ro = new ResizeObserver(() => {
      if (!container || !renderer || !camera) return
      camera.aspect = container.clientWidth / container.clientHeight
      camera.updateProjectionMatrix()
      renderer.setSize(container.clientWidth, container.clientHeight)
    })
    ro.observe(container)

    return () => {
      cancelAnimationFrame(animId)
      ro.disconnect()
      renderer.dispose()
    }
  }, [playing, playbackSpeed])

  // Load Model & Generate Animation Clips
  useEffect(() => {
    if (!src) return

    const loader = new GLTFLoader()

    loader.load(
      src,
      (gltf) => {
        const root = gltf.scene
        if (!modelGroupRef.current || !sceneRef.current) return

        while (modelGroupRef.current.children.length > 0) {
          modelGroupRef.current.remove(modelGroupRef.current.children[0])
        }
        if (skeletonHelperRef.current) {
          sceneRef.current.remove(skeletonHelperRef.current)
          skeletonHelperRef.current = null
        }

        root.traverse((node) => {
          if ((node as THREE.Mesh).isMesh) {
            node.castShadow = true
            node.receiveShadow = true
          }
        })

        // Center on floor
        const box = new THREE.Box3().setFromObject(root)
        const center = box.getCenter(new THREE.Vector3())
        root.position.x = -center.x
        root.position.y = -box.min.y
        root.position.z = -center.z
        modelGroupRef.current.add(root)

        // Skeleton Helper
        const helper = new THREE.SkeletonHelper(root)
        sceneRef.current.add(helper)
        skeletonHelperRef.current = helper

        // Animation Mixer setup
        const mixer = new THREE.AnimationMixer(root)
        mixerRef.current = mixer
        clipsMapRef.current.clear()

        const clipList: ClipInfo[] = []

        // 1. Check embedded animations in GLB
        if (gltf.animations && gltf.animations.length > 0) {
          gltf.animations.forEach((c) => {
            clipsMapRef.current.set(c.name, c)
            clipList.push({ name: c.name, label: `Embedded: ${c.name}`, duration: c.duration, isEmbedded: true })
          })
        }

        // 2. Generate calibrated humanoid keyframed animation tracks
        const proceduralPresets = ['idle', 'combat', 'walk', 'sprint', 'attack', 'cheer']
        proceduralPresets.forEach((pName) => {
          const clip = createHumanoidClip(pName, root)
          if (clip) {
            clipsMapRef.current.set(clip.name, clip)
            clipList.push({ name: clip.name, label: clip.name, duration: clip.duration, isEmbedded: false })
          }
        })

        setAvailableClips(clipList)

        // Start with Idle or first clip
        const initial = clipList.find((c) => c.name.toLowerCase().includes('idle')) || clipList[0]
        if (initial) {
          playClip(initial.name)
        }
      },
      undefined,
      (err) => {
        console.error(err)
      }
    )
  }, [src, playClip])

  // External Animation Clip Import (.glb)
  const handleImportClip = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file || !modelGroupRef.current) return

    const reader = new FileReader()
    reader.onload = (ev) => {
      const buffer = ev.target?.result as ArrayBuffer
      const loader = new GLTFLoader()
      loader.parse(buffer, '', (gltf) => {
        if (!gltf.animations || gltf.animations.length === 0) {
          alert('No animation tracks found in the imported GLTF/GLB file.')
          return
        }
        gltf.animations.forEach((c, idx) => {
          const customName = c.name || `Imported_Track_${idx + 1}`
          clipsMapRef.current.set(customName, c)
          setAvailableClips((prev) => [
            ...prev,
            { name: customName, label: `Custom: ${customName}`, duration: c.duration, isEmbedded: false },
          ])
        })
        playClip(gltf.animations[0].name || 'Imported_Track_1')
      })
    }
    reader.readAsArrayBuffer(file)
  }

  const currentFrame = Math.round((currentTime / (duration || 1)) * 60)
  const totalFrames = Math.round((duration || 1) * 60)

  return (
    <div ref={containerRef} className="dcc-viewport-container">
      <canvas ref={canvasRef} className="dcc-viewport-canvas" />

      {/* Top HUD: Clip Selector & Animation HUD */}
      <div className="viewport-top-hud">
        <div className="viewport-mode-pills">
          <Activity size={14} style={{ color: 'var(--accent)', marginLeft: '4px' }} />
          <span style={{ fontWeight: 700, fontSize: '12px', color: 'var(--text-primary)', marginRight: '6px' }}>
            Motion Track:
          </span>
          <select
            value={selectedClipName}
            onChange={(e) => playClip(e.target.value)}
            style={{ padding: '4px 10px', fontSize: '12px', background: 'var(--bg-surface)', border: 'none', borderRadius: 'var(--radius-pill)', boxShadow: 'var(--shadow-inset-sm)' }}
          >
            {availableClips.map((c) => (
              <option key={c.name} value={c.name}>
                {c.label} ({c.duration.toFixed(1)}s)
              </option>
            ))}
          </select>
        </div>

        <div className="viewport-actions-hud">
          <label className="viewport-mode-btn" style={{ cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px' }} title="Import External Animation Clip (.glb)">
            <Upload size={13} />
            <span>Import Clip</span>
            <input type="file" accept=".glb,.gltf" style={{ display: 'none' }} onChange={handleImportClip} />
          </label>
        </div>
      </div>

      {/* Bottom Timeline Transport Scrubber */}
      <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, background: 'var(--bg-surface)', boxShadow: '0 -4px 12px rgba(163, 177, 198, 0.4)', zIndex: 20, padding: '4px 0' }}>
        <div className="timeline-transport-bar">
          <div className="transport-buttons">
            <button
              type="button"
              className="transport-btn"
              onClick={() => handleScrub(0)}
              title="First Frame"
            >
              <SkipBack size={13} />
            </button>
            <button
              type="button"
              className="transport-btn"
              onClick={() => handleScrub(Math.max(0, currentTime - 0.05))}
              title="Step Back"
            >
              <ChevronLeft size={14} />
            </button>
            <button
              type="button"
              className="transport-btn play-btn"
              onClick={() => setPlaying((p) => !p)}
              title={playing ? 'Pause (Space)' : 'Play (Space)'}
            >
              {playing ? <Pause size={14} /> : <Play size={14} />}
            </button>
            <button
              type="button"
              className="transport-btn"
              onClick={() => handleScrub(Math.min(duration, currentTime + 0.05))}
              title="Step Forward"
            >
              <ChevronRight size={14} />
            </button>
            <button
              type="button"
              className={`transport-btn ${loop ? 'play-btn' : ''}`}
              onClick={() => setLoop((l) => !l)}
              title="Loop Track"
            >
              <Repeat size={13} />
            </button>
          </div>

          <div className="timeline-scrubber-track">
            <input
              type="range"
              min="0"
              max={duration || 1}
              step="0.01"
              value={currentTime}
              onChange={(e) => handleScrub(parseFloat(e.target.value))}
              className="timeline-slider"
            />
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', fontSize: '12px', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
            <span>Frame: <strong style={{ color: 'var(--text-primary)' }}>{currentFrame} / {totalFrames}</strong></span>
            <span>Speed:</span>
            <select
              value={playbackSpeed}
              onChange={(e) => setPlaybackSpeed(parseFloat(e.target.value))}
              style={{ padding: '3px 6px', fontSize: '11px', background: 'var(--bg-surface)', border: 'none', borderRadius: 'var(--radius-sm)', boxShadow: 'var(--shadow-inset-sm)' }}
            >
              <option value="0.25">0.25x</option>
              <option value="0.5">0.5x</option>
              <option value="1.0">1.0x</option>
              <option value="1.5">1.5x</option>
              <option value="2.0">2.0x</option>
            </select>
          </div>
        </div>
      </div>
    </div>
  )
}
