import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import {
  Image,
  Type,
  Bone,
  Sparkles,
  Upload,
  RefreshCw,
  CheckCircle2,
  Wand2,
  AlertCircle,
  ZoomIn,
  X,
  RotateCcw,
  Box,
} from 'lucide-react'
import { api } from './api'
import type { TposePreview } from './api'

type Mode = 'image' | 'text' | 'rig'
type AssetType = 'character' | 'prop'

type Props = {
  onJobCreated: () => Promise<void>
}

export function AIGenerationStudio({ onJobCreated }: Props) {
  const [mode, setMode] = useState<Mode>('text')
  const [assetType, setAssetType] = useState<AssetType>('character')
  const [imageFile, setImageFile] = useState<File | null>(null)
  const [imagePreview, setImagePreview] = useState<string | null>(null)
  const [meshFile, setMeshFile] = useState<File | null>(null)
  const [prompt, setPrompt] = useState('')
  const [seed, setSeed] = useState(42)

  // Text pipeline: T2I preview → user consent → 3D build
  const [tposePreview, setTposePreview] = useState<TposePreview | null>(null)
  const [tposeBlobUrl, setTposeBlobUrl] = useState<string | null>(null)
  const [generatingTpose, setGeneratingTpose] = useState(false)
  const [isApproved, setIsApproved] = useState(false)
  const [previewZoomOpen, setPreviewZoomOpen] = useState(false)

  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [successMsg, setSuccessMsg] = useState<string | null>(null)

  const promptChips = [
    'Cyberpunk neon street fighter, glowing visor, combat jacket',
    'Anime heroine adventurer, fantasy leather armor, cape',
    'Sci-fi heavy mech suit, futuristic helmet, tactical plating',
    'Medieval knight in dark iron plate armor, royal surcoat',
    'Stylized low-poly goblin rogue with daggers',
  ]

  useEffect(() => {
    return () => {
      if (tposeBlobUrl) URL.revokeObjectURL(tposeBlobUrl)
      if (imagePreview) URL.revokeObjectURL(imagePreview)
    }
  }, [tposeBlobUrl, imagePreview])

  const resetTextPreview = () => {
    setIsApproved(false)
    setTposePreview(null)
    if (tposeBlobUrl) URL.revokeObjectURL(tposeBlobUrl)
    setTposeBlobUrl(null)
  }

  const handleImageChange = (file: File | null) => {
    if (imagePreview) URL.revokeObjectURL(imagePreview)
    setImageFile(file)
    setImagePreview(file ? URL.createObjectURL(file) : null)
  }

  const handlePromptChange = (val: string) => {
    setPrompt(val)
    if (tposePreview || isApproved) resetTextPreview()
  }

  const handleSelectChip = (chip: string) => {
    setPrompt(chip)
    if (tposePreview || isApproved) resetTextPreview()
  }

  const handleSeedChange = (val: number) => {
    setSeed(val)
    if (tposePreview || isApproved) resetTextPreview()
  }

  async function handleGenerateTpose() {
    if (!prompt.trim()) {
      setError('Enter a character prompt first.')
      return
    }
    setError(null)
    setGeneratingTpose(true)
    setIsApproved(false)
    setTposePreview(null)
    if (tposeBlobUrl) URL.revokeObjectURL(tposeBlobUrl)
    setTposeBlobUrl(null)
    try {
      const preview = await api.generateTposePreview(prompt.trim(), seed, assetType)
      setTposePreview(preview)
      const blob = await api.fetchUploadPreviewBlob(preview.preview_url)
      setTposeBlobUrl(URL.createObjectURL(blob))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Image preview generation failed')
    } finally {
      setGeneratingTpose(false)
    }
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setSuccessMsg(null)

    if (mode === 'text') {
      if (!tposePreview || !tposeBlobUrl) {
        setError('Generate a 2D image preview first.')
        return
      }
      if (!isApproved) {
        setError('Approve the preview image before starting the 3D build.')
        return
      }
    }

    setBusy(true)
    try {
      if (mode === 'image') {
        if (!imageFile) throw new Error('Select a reference image.')
        await api.createImageJob(imageFile, seed, assetType)
        handleImageChange(null)
      } else if (mode === 'text') {
        if (!tposePreview) throw new Error('No preview image available.')
        await api.createJobFromTposePreview(prompt.trim(), tposePreview.filename, seed, assetType)
        setPrompt('')
        resetTextPreview()
      } else if (mode === 'rig') {
        if (!meshFile) throw new Error('Select a mesh (.glb / .obj / .fbx).')
        await api.createRigJob(meshFile, seed)
        setMeshFile(null)
      }

      setSuccessMsg(
        mode === 'text'
          ? '3D build queued from your approved image.'
          : 'Job queued on the GPU workers.',
      )
      await onJobCreated()
      setTimeout(() => setSuccessMsg(null), 4000)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  const textStep = !tposeBlobUrl ? 1 : !isApproved ? 2 : 3

  return (
    <aside className="dcc-sidebar">
      <div className="dcc-panel-header">
        <h3>
          <Wand2 size={14} style={{ color: 'var(--accent)' }} />
          <span>Generation Studio</span>
        </h3>
      </div>

      <div style={{ padding: '12px 16px 0' }}>
        <div className="dcc-workspace-tabs" style={{ width: '100%', justifyContent: 'space-between' }}>
          <button
            type="button"
            className={`dcc-workspace-tab ${mode === 'image' ? 'active' : ''}`}
            onClick={() => setMode('image')}
            style={{ flex: 1 }}
          >
            <Image size={12} />
            <span>Image</span>
          </button>
          <button
            type="button"
            className={`dcc-workspace-tab ${mode === 'text' ? 'active' : ''}`}
            onClick={() => setMode('text')}
            style={{ flex: 1 }}
          >
            <Type size={12} />
            <span>Text</span>
          </button>
          <button
            type="button"
            className={`dcc-workspace-tab ${mode === 'rig' ? 'active' : ''}`}
            onClick={() => setMode('rig')}
            style={{ flex: 1 }}
          >
            <Bone size={12} />
            <span>Mesh Rig</span>
          </button>
        </div>
      </div>

      <form className="dcc-panel-body" onSubmit={handleSubmit}>
        {mode !== 'rig' && (
          <div className="dcc-field-group">
            <span className="dcc-field-label">Asset type</span>
            <div className="dcc-chip-row">
              <button
                type="button"
                className={`dcc-chip ${assetType === 'character' ? 'active' : ''}`}
                onClick={() => setAssetType('character')}
              >
                Character (rigged)
              </button>
              <button
                type="button"
                className={`dcc-chip ${assetType === 'prop' ? 'active' : ''}`}
                onClick={() => setAssetType('prop')}
              >
                Prop (static)
              </button>
            </div>
          </div>
        )}

        {mode === 'image' && (
          <div className="dcc-field-group">
            <span className="dcc-field-label">Reference image</span>
            <label className="dcc-dropzone" style={{ padding: imagePreview ? '10px' : '26px 16px' }}>
              {imagePreview ? (
                <div style={{ position: 'relative', width: '100%' }}>
                  <div
                    style={{
                      height: '210px',
                      background: 'radial-gradient(circle, #252b36 0%, #151821 100%)',
                      borderRadius: 'var(--radius-sm)',
                      boxShadow: 'var(--shadow-inset)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      padding: '8px',
                      overflow: 'hidden',
                    }}
                  >
                    <img
                      src={imagePreview}
                      alt="Preview"
                      style={{
                        maxHeight: '100%',
                        maxWidth: '100%',
                        width: 'auto',
                        height: 'auto',
                        objectFit: 'contain',
                        display: 'block',
                      }}
                    />
                  </div>
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      marginTop: '8px',
                    }}
                  >
                    <span
                      style={{
                        fontSize: '11px',
                        color: 'var(--text-muted)',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                        maxWidth: '170px',
                      }}
                    >
                      {imageFile?.name}
                    </span>
                    <span style={{ fontSize: '11px', color: 'var(--accent)', fontWeight: 600 }}>
                      Replace
                    </span>
                  </div>
                </div>
              ) : (
                <>
                  <Upload className="dcc-dropzone-icon" />
                  <div style={{ fontWeight: 600, color: 'var(--text-primary)', marginBottom: '4px' }}>
                    Drop reference image
                  </div>
                  <div style={{ fontSize: '11px', color: 'var(--text-dim)' }}>
                    PNG, JPG, WebP · front / T-pose works best
                  </div>
                </>
              )}
              <input
                type="file"
                accept="image/png,image/jpeg,image/webp"
                style={{ display: 'none' }}
                onChange={(e) => handleImageChange(e.target.files?.[0] ?? null)}
              />
            </label>
          </div>
        )}

        {mode === 'text' && (
          <>
            <div
              style={{
                display: 'flex',
                gap: '6px',
                marginBottom: '4px',
                fontSize: '10.5px',
                fontWeight: 700,
                letterSpacing: '0.02em',
              }}
            >
              {[
                { n: 1, label: 'Prompt' },
                { n: 2, label: 'Preview' },
                { n: 3, label: 'Build 3D' },
              ].map((s) => (
                <div
                  key={s.n}
                  style={{
                    flex: 1,
                    textAlign: 'center',
                    padding: '6px 4px',
                    borderRadius: 'var(--radius-sm)',
                    background:
                      textStep === s.n
                        ? 'rgba(59, 130, 246, 0.18)'
                        : textStep > s.n
                          ? 'rgba(16, 185, 129, 0.12)'
                          : 'rgba(255,255,255,0.03)',
                    color:
                      textStep === s.n
                        ? 'var(--accent)'
                        : textStep > s.n
                          ? '#059669'
                          : 'var(--text-dim)',
                    border: `1px solid ${
                      textStep === s.n
                        ? 'rgba(59, 130, 246, 0.35)'
                        : textStep > s.n
                          ? 'rgba(16, 185, 129, 0.3)'
                          : 'transparent'
                    }`,
                  }}
                >
                  {s.n}. {s.label}
                </div>
              ))}
            </div>

            <div className="dcc-field-group">
              <span className="dcc-field-label">Character prompt</span>
              <textarea
                rows={3}
                placeholder="Describe your character (full body, clear silhouette works best)…"
                value={prompt}
                onChange={(e) => handlePromptChange(e.target.value)}
                required
              />
            </div>

            <div className="dcc-field-group">
              <span className="dcc-field-label">Presets</span>
              <div className="dcc-chip-row">
                {promptChips.map((chip, idx) => (
                  <button
                    key={idx}
                    type="button"
                    className="dcc-chip"
                    onClick={() => handleSelectChip(chip)}
                  >
                    {chip.split(',')[0]}
                  </button>
                ))}
              </div>
            </div>

            <div className={`approval-card ${isApproved ? 'is-approved' : ''}`}>
              <div className="approval-header">
                <span
                  style={{
                    fontSize: '11px',
                    fontWeight: 700,
                    color: 'var(--text-primary)',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                  }}
                >
                  <Sparkles size={12} style={{ color: 'var(--accent)' }} />
                  <span>Image preview</span>
                </span>
                {generatingTpose ? (
                  <span className="approval-badge pending">
                    <RefreshCw size={11} className="spin" />
                    <span>Generating…</span>
                  </span>
                ) : !tposeBlobUrl ? (
                  <span className="approval-badge pending">
                    <span>Needed</span>
                  </span>
                ) : isApproved ? (
                  <span className="approval-badge approved">
                    <CheckCircle2 size={11} />
                    <span>Approved</span>
                  </span>
                ) : (
                  <span className="approval-badge pending">
                    <AlertCircle size={11} />
                    <span>Awaiting consent</span>
                  </span>
                )}
              </div>

              {generatingTpose ? (
                <div style={{ textAlign: 'center', padding: '24px 8px', color: 'var(--text-muted)' }}>
                  <RefreshCw
                    size={24}
                    className="spin"
                    style={{ color: 'var(--accent)', margin: '0 auto 8px', display: 'block' }}
                  />
                  <div style={{ fontSize: '12px', fontWeight: 600 }}>Generating preview image…</div>
                  <div style={{ fontSize: '10.5px', color: 'var(--text-dim)', marginTop: '4px' }}>
                    Seed {seed} · no 3D yet
                  </div>
                </div>
              ) : tposeBlobUrl ? (
                <>
                  <div
                    className="approval-preview-wrap"
                    onClick={() => setPreviewZoomOpen(true)}
                    title="Inspect full size"
                  >
                    <img src={tposeBlobUrl} alt="Generated preview" />
                    <div className="approval-preview-overlay">
                      <ZoomIn size={14} />
                      <span>Inspect</span>
                    </div>
                  </div>

                  <p className={`approval-instruction ${isApproved ? 'highlight' : ''}`}>
                    {isApproved
                      ? 'Preview approved. You can start the 3D build (35k · MV-Adapter · UniRig).'
                      : 'Check the silhouette and details. Approve only if you want this image converted to 3D.'}
                  </p>

                  <div className="approval-actions-row">
                    {!isApproved ? (
                      <>
                        <button
                          type="button"
                          className="ghost"
                          onClick={handleGenerateTpose}
                          disabled={generatingTpose || !prompt.trim()}
                          style={{ flex: 1, fontSize: '11px', minHeight: '34px' }}
                        >
                          <RefreshCw size={11} />
                          <span>Regenerate</span>
                        </button>
                        <button
                          type="button"
                          className="success"
                          onClick={() => setIsApproved(true)}
                          style={{ flex: 2, fontSize: '11.5px', minHeight: '34px' }}
                        >
                          <CheckCircle2 size={13} />
                          <span>Approve preview</span>
                        </button>
                      </>
                    ) : (
                      <button
                        type="button"
                        className="ghost"
                        onClick={() => setIsApproved(false)}
                        style={{
                          width: '100%',
                          fontSize: '11px',
                          minHeight: '32px',
                          color: 'var(--text-muted)',
                        }}
                      >
                        <RotateCcw size={11} />
                        <span>Revoke / try another</span>
                      </button>
                    )}
                  </div>
                </>
              ) : (
                <div style={{ textAlign: 'center', padding: '14px 6px' }}>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '10px' }}>
                    Step 1 → generate a 2D image. You review it before any 3D work starts.
                  </div>
                  <button
                    type="button"
                    className="primary"
                    onClick={handleGenerateTpose}
                    disabled={generatingTpose || !prompt.trim()}
                    style={{ width: '100%', fontSize: '11.5px', minHeight: '34px' }}
                  >
                    <Sparkles size={12} />
                    <span>Generate image preview</span>
                  </button>
                </div>
              )}
            </div>
          </>
        )}

        {mode === 'rig' && (
          <div className="dcc-field-group">
            <span className="dcc-field-label">Static mesh</span>
            <label className="dcc-dropzone">
              <Upload className="dcc-dropzone-icon" />
              <div style={{ fontWeight: 600, color: 'var(--text-primary)', marginBottom: '4px' }}>
                {meshFile ? meshFile.name : 'Drop mesh here'}
              </div>
              <div style={{ fontSize: '11px', color: 'var(--text-dim)' }}>
                .glb, .gltf, .obj, .fbx, .ply
              </div>
              <input
                type="file"
                accept=".glb,.gltf,.obj,.fbx,.ply"
                style={{ display: 'none' }}
                onChange={(e) => setMeshFile(e.target.files?.[0] ?? null)}
              />
            </label>
          </div>
        )}

        {mode !== 'rig' && (
          <div
            className="dcc-field-group"
            style={{
              padding: '10px 12px',
              borderRadius: 'var(--radius-sm)',
              background: 'rgba(255,255,255,0.03)',
              border: '1px solid rgba(255,255,255,0.06)',
            }}
          >
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                fontSize: '11.5px',
                fontWeight: 700,
                color: 'var(--text-primary)',
                marginBottom: '4px',
              }}
            >
              <Box size={13} style={{ color: 'var(--accent)' }} />
              <span>Pipeline (bench quality)</span>
            </div>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', lineHeight: 1.45 }}>
              TripoSG 35k · 50 steps → MV-Adapter i2tex → UniRig
              {assetType === 'prop' ? ' (rig skipped for props)' : ''}
            </div>
          </div>
        )}

        <div className="dcc-field-group">
          <div className="dcc-field-label">
            <span>Seed</span>
            <button
              type="button"
              className="ghost"
              style={{ padding: '0 4px', height: 'auto', fontSize: '10px' }}
              onClick={() => handleSeedChange(Math.floor(Math.random() * 100000))}
            >
              <RefreshCw size={10} />
              <span>Random</span>
            </button>
          </div>
          <input
            type="number"
            value={seed}
            onChange={(e) => handleSeedChange(parseInt(e.target.value) || 0)}
          />
        </div>

        {error && (
          <div
            style={{
              fontSize: '11.5px',
              color: 'var(--danger)',
              background: 'rgba(239, 68, 68, 0.1)',
              padding: '8px 12px',
              borderRadius: 'var(--radius-sm)',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}
          >
            <AlertCircle size={13} />
            <span>{error}</span>
          </div>
        )}
        {successMsg && (
          <div
            style={{
              fontSize: '11.5px',
              color: '#059669',
              background: 'rgba(16, 185, 129, 0.12)',
              padding: '8px 12px',
              borderRadius: 'var(--radius-sm)',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}
          >
            <CheckCircle2 size={13} />
            <span>{successMsg}</span>
          </div>
        )}

        {mode === 'text' && !tposeBlobUrl ? (
          <button
            type="button"
            className="primary"
            style={{ width: '100%', padding: '12px 0', marginTop: '6px' }}
            disabled={busy || generatingTpose || !prompt.trim()}
            onClick={handleGenerateTpose}
          >
            <Sparkles size={14} />
            <span>{generatingTpose ? 'Generating preview…' : '1. Generate image preview'}</span>
          </button>
        ) : mode === 'text' && !isApproved ? (
          <button
            type="button"
            className="ghost"
            style={{
              width: '100%',
              padding: '12px 0',
              marginTop: '6px',
              opacity: 0.85,
              cursor: 'not-allowed',
              border: '1px dashed #F59E0B',
              color: 'var(--text-muted)',
            }}
            disabled
          >
            <AlertCircle size={14} style={{ color: '#F59E0B' }} />
            <span>2. Approve the preview to unlock 3D</span>
          </button>
        ) : (
          <button
            type="submit"
            className="primary"
            style={{ width: '100%', padding: '12px 0', marginTop: '6px' }}
            disabled={
              busy ||
              generatingTpose ||
              (mode === 'image' && !imageFile) ||
              (mode === 'rig' && !meshFile) ||
              (mode === 'text' && (!tposePreview || !isApproved))
            }
          >
            <Sparkles size={14} />
            <span>
              {busy
                ? 'Queueing…'
                : mode === 'text'
                  ? '3. Start 3D build'
                  : mode === 'rig'
                    ? 'Queue auto-rig'
                    : 'Queue 3D pipeline'}
            </span>
          </button>
        )}
      </form>

      {previewZoomOpen && tposeBlobUrl && (
        <div className="modal-backdrop" onClick={() => setPreviewZoomOpen(false)}>
          <div
            className="modal-box"
            style={{ width: 'min(680px, 95vw)', textAlign: 'center', padding: '32px 28px' }}
            onClick={(e) => e.stopPropagation()}
          >
            <button
              type="button"
              className="modal-close-btn"
              onClick={() => setPreviewZoomOpen(false)}
              aria-label="Close"
            >
              <X size={16} />
            </button>

            <h4 style={{ fontSize: '18px', fontWeight: 800, marginBottom: '6px' }}>
              Preview inspection
            </h4>
            <p style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '16px' }}>
              Approve only if you want this image sent to the 3D pipeline.
            </p>

            <div
              style={{
                borderRadius: 'var(--radius-sm)',
                overflow: 'hidden',
                boxShadow: 'var(--shadow-inset)',
                padding: '12px',
                background: 'radial-gradient(circle, #252b36 0%, #151821 100%)',
                marginBottom: '18px',
                height: 'min(480px, 65vh)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <img
                src={tposeBlobUrl}
                alt="Full preview"
                style={{
                  maxHeight: '100%',
                  maxWidth: '100%',
                  width: 'auto',
                  height: 'auto',
                  borderRadius: '4px',
                  objectFit: 'contain',
                }}
              />
            </div>

            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '12px' }}>
              {!isApproved ? (
                <button
                  type="button"
                  className="success"
                  style={{ minWidth: '160px' }}
                  onClick={() => {
                    setIsApproved(true)
                    setPreviewZoomOpen(false)
                  }}
                >
                  <CheckCircle2 size={14} />
                  <span>Approve this image</span>
                </button>
              ) : (
                <button
                  type="button"
                  className="ghost"
                  onClick={() => {
                    setIsApproved(false)
                    setPreviewZoomOpen(false)
                  }}
                >
                  <RotateCcw size={14} />
                  <span>Revoke approval</span>
                </button>
              )}
              <button type="button" className="ghost" onClick={() => setPreviewZoomOpen(false)}>
                <span>Close</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </aside>
  )
}
