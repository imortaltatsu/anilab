import { useEffect, useRef, useState } from 'react'
import { Sparkles, Smile, Zap, Heart } from 'lucide-react'

type Mood = 'curious' | 'hyped' | 'chill' | 'snooze'

const SPEECH_QUOTES: Record<Mood, string[]> = {
  curious: [
    'I see your cursor! 👀',
    'Ready to turn 2D into 3D 🚀',
    'Watching every pixel you move ✨',
    'Feed me a character concept! 🎨',
  ],
  hyped: [
    'Dual RTX 4000s go BRRRR! ⚡',
    'Rigged in under 3 minutes flat! ⏱️',
    '54 bones, zero weight pinching! 🦴',
    'YEET! Game-ready GLB inbound! 🎮',
  ],
  chill: [
    'Clean manifold quads all day 😌',
    'Topology looking silky smooth 🧼',
    '4096 UV bakes, no sweat ☕',
    'Just vibing in Neumorphism 🎧',
  ],
  snooze: [
    'Zzz... dreaming in 3D wireframes 💤',
    'Nap time between GPU batches 😴',
    'Click me to wake me up! ⏰',
    'Low power mode active 🔋',
  ],
}

export function PlayfulMascot() {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const leftEyeRef = useRef<SVGGElement | null>(null)
  const rightEyeRef = useRef<SVGGElement | null>(null)

  const [mood, setMood] = useState<Mood>('curious')
  const [isBlinking, setIsBlinking] = useState(false)
  const [quoteIndex, setQuoteIndex] = useState(0)
  const [isClicked, setIsClicked] = useState(false)
  const [hearts, setHearts] = useState<Array<{ id: number; x: number; y: number }>>([])

  // Tracking pupil offsets
  const pupilTarget = useRef({ lx: 0, ly: 0, rx: 0, ry: 0 })
  const pupilCurrent = useRef({ lx: 0, ly: 0, rx: 0, ry: 0 })

  // Mouse move listener across entire window
  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (mood === 'snooze') {
        pupilTarget.current = { lx: 0, ly: 6, rx: 0, ry: 6 }
        return
      }

      const leftEye = leftEyeRef.current
      const rightEye = rightEyeRef.current
      if (!leftEye || !rightEye) return

      const leftRect = leftEye.getBoundingClientRect()
      const rightRect = rightEye.getBoundingClientRect()

      const leftCenter = {
        x: leftRect.left + leftRect.width / 2,
        y: leftRect.top + leftRect.height / 2,
      }
      const rightCenter = {
        x: rightRect.left + rightRect.width / 2,
        y: rightRect.top + rightRect.height / 2,
      }

      // Max eye travel in SVG units
      const maxOffset = 15

      // Left eye calculation
      const ldx = e.clientX - leftCenter.x
      const ldy = e.clientY - leftCenter.y
      const lAngle = Math.atan2(ldy, ldx)
      const lDist = Math.min(Math.hypot(ldx, ldy) / 14, maxOffset)

      // Right eye calculation
      const rdx = e.clientX - rightCenter.x
      const rdy = e.clientY - rightCenter.y
      const rAngle = Math.atan2(rdy, rdx)
      const rDist = Math.min(Math.hypot(rdx, rdy) / 14, maxOffset)

      pupilTarget.current = {
        lx: Math.cos(lAngle) * lDist,
        ly: Math.sin(lAngle) * lDist,
        rx: Math.cos(rAngle) * rDist,
        ry: Math.sin(rAngle) * rDist,
      }
    }

    window.addEventListener('mousemove', handleMouseMove)
    return () => window.removeEventListener('mousemove', handleMouseMove)
  }, [mood])

  // Animation frame for smooth pupil lerping
  useEffect(() => {
    let animId: number
    const updatePupils = () => {
      const cur = pupilCurrent.current
      const tgt = pupilTarget.current

      cur.lx += (tgt.lx - cur.lx) * 0.18
      cur.ly += (tgt.ly - cur.ly) * 0.18
      cur.rx += (tgt.rx - cur.rx) * 0.18
      cur.ry += (tgt.ry - cur.ry) * 0.18

      const leftPupil = document.getElementById('mascot-left-pupil')
      const rightPupil = document.getElementById('mascot-right-pupil')

      if (leftPupil) {
        leftPupil.setAttribute('transform', `translate(${cur.lx.toFixed(2)}, ${cur.ly.toFixed(2)})`)
      }
      if (rightPupil) {
        rightPupil.setAttribute('transform', `translate(${cur.rx.toFixed(2)}, ${cur.ry.toFixed(2)})`)
      }

      animId = requestAnimationFrame(updatePupils)
    }

    animId = requestAnimationFrame(updatePupils)
    return () => cancelAnimationFrame(animId)
  }, [])

  // Natural spontaneous blinking
  useEffect(() => {
    if (mood === 'snooze') return

    const blinkInterval = setInterval(() => {
      setIsBlinking(true)
      setTimeout(() => setIsBlinking(false), 180)
    }, 3200 + Math.random() * 2500)

    return () => clearInterval(blinkInterval)
  }, [mood])

  // Autonomous random mood changer at natural intervals (5.5s - 9s)
  useEffect(() => {
    const MOOD_POOL: Mood[] = ['curious', 'hyped', 'chill', 'snooze']

    let timer: number
    const scheduleNextMood = () => {
      const delay = 5500 + Math.random() * 3500 // Random 5.5s - 9s
      timer = window.setTimeout(() => {
        setMood((prev) => {
          const remaining = MOOD_POOL.filter((m) => m !== prev)
          return remaining[Math.floor(Math.random() * remaining.length)]
        })
        setQuoteIndex((prev) => prev + 1)
        scheduleNextMood()
      }, delay)
    }

    scheduleNextMood()
    return () => window.clearTimeout(timer)
  }, [])

  // Mascot poke / click reaction
  const handleMascotClick = (e: React.MouseEvent) => {
    setIsClicked(true)
    setTimeout(() => setIsClicked(false), 350)

    // If sleeping, wake up immediately into hyped!
    if (mood === 'snooze') {
      setMood('hyped')
      setQuoteIndex(0)
    } else {
      // Cycle speech quotes
      setQuoteIndex((prev) => (prev + 1) % SPEECH_QUOTES[mood].length)
    }

    // Spawn cute heart particle at click location
    if (containerRef.current) {
      const rect = containerRef.current.getBoundingClientRect()
      const newHeart = {
        id: Date.now() + Math.random(),
        x: e.clientX - rect.left,
        y: e.clientY - rect.top,
      }
      setHearts((prev) => [...prev.slice(-6), newHeart])
      setTimeout(() => {
        setHearts((prev) => prev.filter((h) => h.id !== newHeart.id))
      }, 1000)
    }
  }

  return (
    <div ref={containerRef} className="playful-mascot-wrapper">
      {/* Floating Speech Bubble */}
      <div className="mascot-speech-bubble" onClick={handleMascotClick}>
        <span className="speech-badge">
          {mood === 'hyped' ? 'YeetBot ⚡' : mood === 'chill' ? 'YeetBot 🎧' : mood === 'snooze' ? 'YeetBot 💤' : 'YeetBot 👀'}
        </span>
        <p className="speech-text">{SPEECH_QUOTES[mood][quoteIndex % SPEECH_QUOTES[mood].length]}</p>
        <span className="speech-hint">Click me!</span>
      </div>

      {/* Main Mascot Card with Interactive SVG Creature */}
      <div
        className={`mascot-stage-card ${isClicked ? 'mascot-bounce' : ''}`}
        onClick={handleMascotClick}
        title="Click to interact with YeetBot!"
      >
        <svg
          viewBox="0 0 340 310"
          className="mascot-svg"
          xmlns="http://www.w3.org/2000/svg"
        >
          <defs>
            {/* Body Clay Gradient */}
            <linearGradient id="bodyGrad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#F5F8FC" />
              <stop offset="60%" stopColor="#E0E5EC" />
              <stop offset="100%" stopColor="#CCD4DF" />
            </linearGradient>

            {/* Eye Sclera Inset Shadow Filter */}
            <filter id="eyeShadow" x="-20%" y="-20%" width="140%" height="140%">
              <feDropShadow dx="2" dy="3" stdDeviation="3" floodColor="#A3B1C6" floodOpacity="0.5" />
              <feDropShadow dx="-2" dy="-3" stdDeviation="3" floodColor="#FFFFFF" floodOpacity="0.8" />
            </filter>

            {/* Pupil Gradient */}
            <radialGradient id="pupilGrad" cx="35%" cy="35%" r="65%">
              <stop offset="0%" stopColor="#2A323D" />
              <stop offset="70%" stopColor="#191F26" />
              <stop offset="100%" stopColor="#0D1117" />
            </radialGradient>

            {/* Glowing Antenna Orb */}
            <radialGradient id="glowOrb" cx="40%" cy="40%" r="60%">
              <stop offset="0%" stopColor="#A5F3FC" />
              <stop offset="50%" stopColor="#38B2AC" />
              <stop offset="100%" stopColor="#0F766E" />
            </radialGradient>
          </defs>

          {/* Soft Ground Shadow */}
          <ellipse cx="170" cy="285" rx="100" ry="14" fill="#A3B1C6" opacity="0.35" />

          {/* Floating Antenna with Glowing Orb */}
          <path
            d="M170 80 Q170 42 162 25"
            stroke="#94A3B8"
            strokeWidth="5"
            strokeLinecap="round"
            fill="none"
          />
          <circle cx="160" cy="20" r="11" fill="url(#glowOrb)" className="mascot-antenna-glow" />
          <circle cx="157" cy="17" r="3.5" fill="#FFFFFF" opacity="0.9" />

          {/* Cute Robot Ears / Joint Nodes */}
          <rect x="42" y="130" width="16" height="36" rx="8" fill="#CCD4DF" />
          <circle cx="50" cy="148" r="4.5" fill="#6C63FF" />
          <rect x="282" y="130" width="16" height="36" rx="8" fill="#CCD4DF" />
          <circle cx="290" cy="148" r="4.5" fill="#6C63FF" />

          {/* Main Rounded Clay Head / Body */}
          <rect
            x="54"
            y="65"
            width="232"
            height="195"
            rx="64"
            fill="url(#bodyGrad)"
            stroke="#FFFFFF"
            strokeWidth="1.5"
          />

          {/* Cheek Blushes */}
          <ellipse cx="94" cy="190" rx="15" ry="8" fill="#FF8BA7" opacity={mood === 'hyped' ? 0.7 : 0.4} />
          <ellipse cx="246" cy="190" rx="15" ry="8" fill="#FF8BA7" opacity={mood === 'hyped' ? 0.7 : 0.4} />

          {/* LEFT EYE */}
          <g ref={leftEyeRef} id="mascot-left-eye-socket">
            {/* Eye Sclera */}
            <circle cx="118" cy="142" r="32" fill="#FFFFFF" filter="url(#eyeShadow)" />

            {/* Pupil & Specular (Follows mouse) */}
            {!isBlinking && mood !== 'snooze' ? (
              <g id="mascot-left-pupil">
                <circle cx="118" cy="142" r="19" fill="url(#pupilGrad)" />
                <circle cx="118" cy="142" r="7" fill={mood === 'hyped' ? '#6C63FF' : '#38B2AC'} opacity="0.8" />
                <circle cx="112" cy="135" r="5" fill="#FFFFFF" />
                <circle cx="123" cy="147" r="2.2" fill="#FFFFFF" opacity="0.85" />
              </g>
            ) : null}

            {/* Snooze Eyes */}
            {mood === 'snooze' && !isBlinking && (
              <path
                d="M96 142 Q118 158 140 142"
                stroke="#3D4852"
                strokeWidth="5"
                strokeLinecap="round"
                fill="none"
              />
            )}

            {/* Blink eyelid animation */}
            {isBlinking && (
              <line
                x1="94"
                y1="142"
                x2="142"
                y2="142"
                stroke="#3D4852"
                strokeWidth="5"
                strokeLinecap="round"
              />
            )}
          </g>

          {/* RIGHT EYE */}
          <g ref={rightEyeRef} id="mascot-right-eye-socket">
            {/* Eye Sclera */}
            <circle cx="222" cy="142" r="32" fill="#FFFFFF" filter="url(#eyeShadow)" />

            {/* Pupil & Specular (Follows mouse) */}
            {!isBlinking && mood !== 'snooze' ? (
              <g id="mascot-right-pupil">
                <circle cx="222" cy="142" r="19" fill="url(#pupilGrad)" />
                <circle cx="222" cy="142" r="7" fill={mood === 'hyped' ? '#6C63FF' : '#38B2AC'} opacity="0.8" />
                <circle cx="216" cy="135" r="5" fill="#FFFFFF" />
                <circle cx="227" cy="147" r="2.2" fill="#FFFFFF" opacity="0.85" />
              </g>
            ) : null}

            {/* Snooze Eyes */}
            {mood === 'snooze' && !isBlinking && (
              <path
                d="M200 142 Q222 158 244 142"
                stroke="#3D4852"
                strokeWidth="5"
                strokeLinecap="round"
                fill="none"
              />
            )}

            {/* Blink eyelid animation */}
            {isBlinking && (
              <line
                x1="198"
                y1="142"
                x2="246"
                y2="142"
                stroke="#3D4852"
                strokeWidth="5"
                strokeLinecap="round"
              />
            )}
          </g>

          {/* MOUTH */}
          {mood === 'curious' && (
            <path
              d="M152 195 Q170 212 188 195"
              stroke="#3D4852"
              strokeWidth="4.5"
              strokeLinecap="round"
              fill="none"
            />
          )}

          {mood === 'hyped' && (
            <path
              d="M148 190 Q170 228 192 190 Z"
              fill="#E11D48"
              stroke="#3D4852"
              strokeWidth="3.5"
              strokeLinejoin="round"
            />
          )}

          {mood === 'chill' && (
            <path
              d="M154 196 Q170 205 186 196"
              stroke="#3D4852"
              strokeWidth="4"
              strokeLinecap="round"
              fill="none"
            />
          )}

          {mood === 'snooze' && (
            <ellipse cx="170" cy="198" rx="6" ry="7" fill="#3D4852" />
          )}
        </svg>

        {/* Floating Hearts spawned on poke */}
        {hearts.map((h) => (
          <div
            key={h.id}
            className="mascot-heart-particle"
            style={{ left: `${h.x}px`, top: `${h.y}px` }}
          >
            <Heart size={16} fill="#FF4D6D" color="#FF4D6D" />
          </div>
        ))}
      </div>

      {/* Playful Feature Chips */}
      <div className="mascot-feature-chips">
        <div className="mascot-chip">
          <Sparkles size={13} style={{ color: 'var(--accent)' }} />
          <span>35k Bench Mesh</span>
        </div>
        <div className="mascot-chip">
          <Zap size={13} style={{ color: 'var(--accent-teal)' }} />
          <span>4K UV Texture Bake</span>
        </div>
        <div className="mascot-chip">
          <Smile size={13} style={{ color: '#E11D48' }} />
          <span>54 Bone Auto-Rig</span>
        </div>
      </div>
    </div>
  )
}
