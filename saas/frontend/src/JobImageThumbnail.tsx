import { useState, useEffect } from 'react'
import { Box, Bone, RefreshCw, ImageOff } from 'lucide-react'
import type { Job } from './api'
import { api } from './api'

// Global in-memory cache of object URLs so browsing and tab switching is instantaneous
const blobCache = new Map<number, string>()

export function invalidateJobImageCache(jobId: number) {
  const existing = blobCache.get(jobId)
  if (existing) {
    URL.revokeObjectURL(existing)
    blobCache.delete(jobId)
  }
}

export function getCachedJobImageUrl(jobId: number): string | null {
  return blobCache.get(jobId) ?? null
}

type Props = {
  job: Job
  className?: string
  style?: React.CSSProperties
  onClick?: () => void
}

export function JobImageThumbnail({ job, className, style, onClick }: Props) {
  const [url, setUrl] = useState<string | null>(blobCache.get(job.id) ?? null)
  const [loading, setLoading] = useState(!blobCache.has(job.id) && !!job.preview_url)
  const [hasError, setHasError] = useState(false)

  useEffect(() => {
    if (blobCache.has(job.id)) {
      setUrl(blobCache.get(job.id)!)
      setLoading(false)
      return
    }

    if (!job.preview_url) {
      setLoading(false)
      return
    }

    let cancelled = false
    setLoading(true)
    setHasError(false)

    api
      .fetchPreviewBlob(job.id)
      .then((blob) => {
        if (!cancelled) {
          const objectUrl = URL.createObjectURL(blob)
          blobCache.set(job.id, objectUrl)
          setUrl(objectUrl)
          setLoading(false)
        }
      })
      .catch(() => {
        if (!cancelled) {
          setHasError(true)
          setLoading(false)
        }
      })

    return () => {
      cancelled = true
    }
  }, [job.id, job.preview_url])

  if (loading) {
    return (
      <div
        className={className}
        style={{
          display: 'grid',
          placeItems: 'center',
          background: 'radial-gradient(circle, #252b36 0%, #151821 100%)',
          ...style,
        }}
      >
        <RefreshCw size={16} className="spin" style={{ color: 'var(--accent)' }} />
      </div>
    )
  }

  if (url && !hasError) {
    return (
      <div
        className={className}
        style={{
          position: 'relative',
          overflow: 'hidden',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          cursor: onClick ? 'pointer' : 'default',
          ...style,
        }}
        onClick={onClick}
      >
        <img
          src={url}
          alt={job.prompt || `Asset #${job.id}`}
          style={{
            maxWidth: '100%',
            maxHeight: '100%',
            width: 'auto',
            height: 'auto',
            objectFit: 'contain',
            display: 'block',
          }}
        />
      </div>
    )
  }

  return (
    <div
      className={className}
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: '4px',
        background: 'radial-gradient(circle, #252b36 0%, #151821 100%)',
        color: 'var(--text-dim)',
        ...style,
      }}
      onClick={onClick}
    >
      {hasError ? (
        <>
          <ImageOff size={20} style={{ color: 'var(--text-muted)' }} />
          <span style={{ fontSize: '10px' }}>No Preview</span>
        </>
      ) : job.mode === 'rig' ? (
        <>
          <Bone size={22} style={{ color: 'var(--warning, #F59E0B)' }} />
          <span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>Rigged Mesh</span>
        </>
      ) : (
        <>
          <Box size={22} style={{ color: 'var(--accent)' }} />
          <span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>3D Model</span>
        </>
      )}
    </div>
  )
}
