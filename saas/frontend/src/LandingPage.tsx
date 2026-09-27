import { useState } from 'react'
import type { FormEvent } from 'react'
import {
  Boxes,
  Cpu,
  Layers,
  Sparkles,
  Zap,
  Check,
  ArrowRight,
  ShieldCheck,
  ChevronDown,
  Lock,
  X,
} from 'lucide-react'
import { PlayfulMascot } from './PlayfulMascot'

type Props = {
  onLogin: (password: string) => Promise<void>
}

export function LandingPage({ onLogin }: Props) {
  const [showAuthModal, setShowAuthModal] = useState(false)
  const [password, setPassword] = useState('')
  const [isAnnual, setIsAnnual] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [openFaq, setOpenFaq] = useState<number | null>(null)

  async function handleAuthSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      await onLogin(password)
      setShowAuthModal(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Invalid access password')
    } finally {
      setLoading(false)
    }
  }

  const faqs = [
    {
      q: 'How does the YeetGen AI Pipeline generate game-ready 3D characters?',
      a: 'We combine TripoSG shape (~35k faces, bench quality), MV-Adapter multi-view texture bake into clean UVs, and UniRig skeleton + skinning — exporting a rigged GLB ready for Unreal, Unity, or Blender.',
    },
    {
      q: 'Can I export to Unreal Engine 5, Unity, and Blender?',
      a: 'Yes! Generated characters are standard GLTF/GLB files with clean quad/tri topology, PBR textures (BaseColor, Normal, Roughness), and standard humanoid bone naming, allowing instant drag-and-drop into Unreal 5, Unity, Godot, and Blender.',
    },
    {
      q: 'What is the generation turnaround time per model?',
      a: 'Powered by dual dedicated RTX 4000 Ada GPUs, full pipeline generation (shape + 4K texture baking + auto-rigging) averages between 2.5 to 3.5 minutes per character.',
    },
    {
      q: 'Do I retain commercial rights to generated 3D models?',
      a: 'Yes. Studio Pro and Enterprise tiers include full commercial licensing for use in commercial games, film VFX, VR, and interactive experiences.',
    },
  ]

  return (
    <div className="landing-shell">
      {/* Top Navbar */}
      <header className="landing-nav">
        <div className="landing-brand">
          <div className="dcc-brand-icon">Y</div>
          <span>YeetGen</span>
        </div>

        <nav className="landing-nav-links">
          <a className="landing-nav-link" href="#features">Pipeline</a>
          <a className="landing-nav-link" href="#engines">Engines</a>
          <a className="landing-nav-link" href="#pricing">Pricing</a>
          <a className="landing-nav-link" href="#faq">FAQ</a>
        </nav>

        <button
          type="button"
          className="primary"
          onClick={() => setShowAuthModal(true)}
        >
          <Lock size={14} />
          <span>Enter Studio</span>
        </button>
      </header>

      {/* Hero Section */}
      <section className="landing-hero">
        <div className="hero-content">
          <div className="hero-pill">
            <Sparkles size={14} />
            <span>Dual RTX 4000 Ada GPU Accelerated</span>
          </div>

          <h1 className="hero-title">
            Tactile Game-Ready <br />
            <span className="gradient-text">3D Characters</span> in 3 Mins
          </h1>

          <p className="hero-subtitle">
            The next-generation AI 3D creation pipeline for game developers. Transform single 2D images
            or text prompts into ~35k-face textured, rigged GLB character assets (bench pipeline quality).
          </p>

          <div className="hero-cta-group">
            <button
              type="button"
              className="primary"
              onClick={() => setShowAuthModal(true)}
            >
              <span>Launch Studio</span>
              <ArrowRight size={16} />
            </button>
            <a href="#pricing">
              <button type="button" className="ghost">
                <span>View Pricing Plans</span>
              </button>
            </a>
          </div>
        </div>

        <PlayfulMascot />
      </section>

      {/* Engine Compatibility */}
      <section id="engines" className="landing-engines">
        <p className="landing-engines-title">Directly Compatible With Game Engines & DCC Tools</p>
        <div className="landing-engine-grid">
          <div className="landing-engine-badge">
            <Boxes size={18} />
            <span>Unreal Engine 5</span>
          </div>
          <div className="landing-engine-badge">
            <Layers size={18} />
            <span>Unity Engine</span>
          </div>
          <div className="landing-engine-badge">
            <Cpu size={18} />
            <span>Blender 4.x</span>
          </div>
          <div className="landing-engine-badge">
            <Zap size={18} />
            <span>Godot 4</span>
          </div>
        </div>
      </section>

      {/* Features Showcase */}
      <section id="features" className="landing-features">
        <div className="section-header">
          <h2>The Triple-Engine 3D Pipeline</h2>
          <p>Engineered exclusively with clean topology and game-engine standard rigging.</p>
        </div>

        <div className="feature-cards-grid">
          <div className="feature-card">
            <div className="feature-icon-box">
              <Boxes size={26} />
            </div>
            <h3>1. Neural Shape Synthesis</h3>
            <p>
              Reconstructs clean, watertight manifold geometry from a single front-facing image
              at ~35k faces (TripoSG → MV-Adapter → UniRig), matching our proven bench_image recipe.
            </p>
            <span className="feature-metric-tag">Shape Step · ~30s</span>
          </div>

          <div className="feature-card">
            <div className="feature-icon-box">
              <Layers size={26} />
            </div>
            <h3>2. 4K UV Texture Baking</h3>
            <p>
              Multi-view diffusion synthesis generates 360-degree surface consistency and automatically
              bakes high-definition 4096 UV diffuse and normal maps.
            </p>
            <span className="feature-metric-tag">Texture Step · ~100s</span>
          </div>

          <div className="feature-card">
            <div className="feature-icon-box">
              <Cpu size={26} />
            </div>
            <h3>3. Humanoid Auto-Rigging</h3>
            <p>
              Predicts full humanoid skeletal joint hierarchies and computes smooth skinning weights,
              exporting an animated, skinned GLB ready for motion retargeting.
            </p>
            <span className="feature-metric-tag">Rig Step · ~60s</span>
          </div>
        </div>
      </section>

      {/* Pricing Section */}
      <section id="pricing" className="landing-pricing">
        <div className="section-header">
          <h2>Transparent Game-Dev Pricing</h2>
          <p>Select the plan tailored for your studio workflow.</p>
        </div>

        <div className="pricing-billing-toggle">
          <span style={{ color: !isAnnual ? 'var(--text-primary)' : 'var(--text-muted)' }}>Monthly</span>
          <div className="pricing-toggle-pill">
            <button
              type="button"
              className={`pricing-toggle-btn ${!isAnnual ? 'active' : ''}`}
              onClick={() => setIsAnnual(false)}
            >
              Monthly
            </button>
            <button
              type="button"
              className={`pricing-toggle-btn ${isAnnual ? 'active' : ''}`}
              onClick={() => setIsAnnual(true)}
            >
              Annual (20% Off)
            </button>
          </div>
          <span style={{ color: isAnnual ? 'var(--text-primary)' : 'var(--text-muted)' }}>Annual</span>
        </div>

        <div className="pricing-grid">
          {/* Indie Tier */}
          <div className="pricing-card">
            <h3 className="pricing-title">Indie Creator</h3>
            <p className="pricing-desc">Perfect for solo indie devs and 3D modders.</p>
            <div className="pricing-price">
              ${isAnnual ? '24' : '29'}
              <span>/month</span>
            </div>
            <ul className="pricing-features">
              <li><Check size={16} /> 100 3D Game Assets / mo</li>
              <li><Check size={16} /> 2048 UV Texture Resolution</li>
              <li><Check size={16} /> Automated Humanoid Skeleton</li>
              <li><Check size={16} /> Standard GLB & FBX Export</li>
              <li><Check size={16} /> Community Support</li>
            </ul>
            <button
              type="button"
              onClick={() => setShowAuthModal(true)}
            >
              Get Started
            </button>
          </div>

          {/* Studio Pro Tier */}
          <div className="pricing-card featured">
            <div className="pricing-badge-popular">Most Popular</div>
            <h3 className="pricing-title">Studio Pro</h3>
            <p className="pricing-desc">For game studios, indie teams, and professional artists.</p>
            <div className="pricing-price">
              ${isAnnual ? '64' : '79'}
              <span>/month</span>
            </div>
            <ul className="pricing-features">
              <li><Check size={16} /> <strong>Unlimited</strong> 3D Generations</li>
              <li><Check size={16} /> <strong>4096 Ultra-HD</strong> UV Texture Bakes</li>
              <li><Check size={16} /> <strong>Dual RTX 4000 GPU</strong> Priority Queue</li>
              <li><Check size={16} /> Full Commercial Rights & License</li>
              <li><Check size={16} /> Interactive T-Pose Studio & Rigging</li>
              <li><Check size={16} /> Priority 24/7 Technical Support</li>
            </ul>
            <button
              type="button"
              className="primary"
              onClick={() => setShowAuthModal(true)}
            >
              Launch Studio Pro
            </button>
          </div>

          {/* Enterprise Tier */}
          <div className="pricing-card">
            <h3 className="pricing-title">AAA Studio / Enterprise</h3>
            <p className="pricing-desc">For large production studios requiring on-prem or API clusters.</p>
            <div className="pricing-price">
              ${isAnnual ? '239' : '299'}
              <span>/month</span>
            </div>
            <ul className="pricing-features">
              <li><Check size={16} /> Dedicated On-Premises GPU Cluster</li>
              <li><Check size={16} /> Custom Joint Rigging & Retargeting Profiles</li>
              <li><Check size={16} /> High-Throughput REST & Python API</li>
              <li><Check size={16} /> Custom Polycount LOD Generation</li>
              <li><Check size={16} /> Dedicated Account Manager & SLAs</li>
            </ul>
            <button
              type="button"
              onClick={() => setShowAuthModal(true)}
            >
              Contact Enterprise
            </button>
          </div>
        </div>
      </section>

      {/* FAQ Section */}
      <section id="faq" className="landing-features" style={{ marginBottom: '90px' }}>
        <div className="section-header">
          <h2>Frequently Asked Questions</h2>
          <p>Everything you need to know about YeetGen Studio.</p>
        </div>

        <div style={{ maxWidth: '820px', margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {faqs.map((faq, idx) => {
            const isOpen = openFaq === idx
            return (
              <div
                key={idx}
                className="neu-extruded-sm"
                style={{
                  padding: '20px 24px',
                  cursor: 'pointer',
                  borderRadius: 'var(--radius-btn)',
                }}
                onClick={() => setOpenFaq(isOpen ? null : idx)}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: '15px', color: 'var(--text-primary)' }}>
                  <span>{faq.q}</span>
                  <ChevronDown
                    size={20}
                    style={{
                      transform: isOpen ? 'rotate(180deg)' : 'none',
                      transition: 'transform 0.3s ease',
                      color: 'var(--accent)',
                    }}
                  />
                </div>
                {isOpen && (
                  <p style={{ marginTop: '14px', fontSize: '14px', color: 'var(--text-muted)', lineHeight: '1.65' }}>
                    {faq.a}
                  </p>
                )}
              </div>
            )
          })}
        </div>
      </section>

      {/* Footer */}
      <footer style={{ padding: '36px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '13px', boxShadow: 'var(--shadow-inset-sm)' }}>
        <p>© 2026 YeetGen 3D. Built for Game Developers. Full-Stack 3D Generative AI Engine.</p>
      </footer>

      {/* Password-Only Sign-In Modal */}
      {showAuthModal && (
        <div className="modal-backdrop" onClick={() => setShowAuthModal(false)}>
          <div className="modal-box" onClick={(e) => e.stopPropagation()}>
            <button
              type="button"
              className="modal-close-btn"
              onClick={() => setShowAuthModal(false)}
            >
              <X size={18} />
            </button>

            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '10px' }}>
              <div className="dcc-brand-icon">Y</div>
              <h3 className="modal-title" style={{ margin: 0 }}>Enter Studio</h3>
            </div>
            <p className="modal-subtitle">
              Enter your access password to unlock the Studio workspace.
            </p>

            <form onSubmit={handleAuthSubmit}>
              <div className="auth-form-group">
                <label htmlFor="access-pwd">Access Password</label>
                <input
                  id="access-pwd"
                  type="password"
                  required
                  autoFocus
                  placeholder="Enter studio access password…"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              </div>

              {error && <div className="auth-error">{error}</div>}

              <button
                type="submit"
                className="primary"
                style={{ width: '100%', padding: '14px 0', marginTop: '10px' }}
                disabled={loading}
              >
                <ShieldCheck size={18} />
                <span>{loading ? 'Authenticating…' : 'Enter Studio'}</span>
              </button>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
