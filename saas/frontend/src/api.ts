/** Backend base — Tailscale hostname, not localhost. Override with VITE_API_URL. */
const API = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, '') || 'http://proxpc:8000'

export type TokenResponse = { access_token: string; token_type: string; role: string }
export type Me = { subject: string; role: string }
export type AllowedPassword = {
  id: number
  label: string
  active: boolean
  created_at: string
}
export type Job = {
  id: number
  status: string
  mode: string
  prompt: string | null
  glb_path: string | null
  error: string | null
  seed: number
  created_at: string
  started_at: string | null
  finished_at: string | null
  download_url: string | null
  preview_url: string | null
}
export type JobLog = { job_id: number; status: string; log: string }
export type TposePreview = {
  preview_url: string
  filename: string
  seed: number
  prompt: string
}

function authHeaders(): HeadersInit {
  const token = localStorage.getItem('yeetgen_token') || localStorage.getItem('anilab_token')
  return token ? { Authorization: `Bearer ${token}` } : {}
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  if (!(init.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json')
  }
  Object.entries(authHeaders()).forEach(([k, v]) => headers.set(k, v as string))

  const res = await fetch(`${API}${path}`, { ...init, headers })
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      detail = body.detail ?? JSON.stringify(body)
    } catch {
      /* ignore */
    }
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail))
  }
  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}

async function uploadJob(
  path: string,
  file: File,
  seed = 42,
  assetType = 'character',
): Promise<Job> {
  const fd = new FormData()
  fd.append('file', file)
  fd.append('seed', String(seed))
  fd.append('asset_type', assetType)
  const res = await fetch(`${API}${path}`, {
    method: 'POST',
    headers: authHeaders(),
    body: fd,
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail ?? res.statusText)
  }
  return res.json() as Promise<Job>
}

async function fetchGlbBlob(jobId: number): Promise<Blob> {
  const res = await fetch(`${API}/api/jobs/${jobId}/download`, { headers: authHeaders() })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail ?? res.statusText)
  }
  return res.blob()
}

async function fetchPreviewBlob(jobId: number): Promise<Blob> {
  const res = await fetch(`${API}/api/jobs/${jobId}/preview`, { headers: authHeaders() })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail ?? res.statusText)
  }
  return res.blob()
}

export const api = {
  login: (password: string) =>
    request<TokenResponse>('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ password }),
    }),
  me: () => request<Me>('/api/auth/me'),
  listJobs: () => request<Job[]>('/api/jobs'),
  createImageJob: (file: File, seed = 42, assetType = 'character') =>
    uploadJob('/api/jobs/image', file, seed, assetType),
  createRigJob: (file: File, seed = 42) => uploadJob('/api/jobs/rig', file, seed),
  createTextJob: (prompt: string, seed = 42, assetType = 'character') =>
    request<Job>('/api/jobs/text', {
      method: 'POST',
      body: JSON.stringify({ prompt, seed, asset_type: assetType }),
    }),
  generateTposePreview: (prompt: string, seed = 42, assetType = 'character') =>
    request<TposePreview>('/api/jobs/text/preview', {
      method: 'POST',
      body: JSON.stringify({ prompt, seed, asset_type: assetType }),
    }),
  createJobFromTposePreview: (
    prompt: string,
    filename: string,
    seed = 42,
    assetType = 'character',
  ) =>
    request<Job>('/api/jobs/text/from-preview', {
      method: 'POST',
      body: JSON.stringify({ prompt, filename, seed, asset_type: assetType }),
    }),
  fetchUploadPreviewBlob: async (previewUrl: string): Promise<Blob> => {
    const res = await fetch(`${API}${previewUrl}`, { headers: authHeaders() })
    if (!res.ok) {
      const body = await res.json().catch(() => ({}))
      throw new Error(body.detail ?? res.statusText)
    }
    return res.blob()
  },
  getJobLogs: (jobId: number) => request<JobLog>(`/api/jobs/${jobId}/logs`),
  retryJob: (jobId: number) =>
    request<Job>(`/api/jobs/${jobId}/retry`, { method: 'POST' }),
  rebakeJob: (jobId: number, params: {
    rotation_yaw?: number
    rotation_pitch?: number
    uv_size?: number
    inpaint_mode?: string
    steps?: number
    guidance?: number
  } = {}) =>
    request<Job>(`/api/jobs/${jobId}/rebake`, {
      method: 'POST',
      body: JSON.stringify(params),
    }),
  deleteJob: (jobId: number) =>
    request<void>(`/api/jobs/${jobId}`, { method: 'DELETE' }),
  deleteFailedJobs: () =>
    request<{ deleted: number }>('/api/jobs/failed', { method: 'DELETE' }),
  listPasswords: () => request<AllowedPassword[]>('/api/admin/passwords'),
  addPassword: (password: string, label = 'access') =>
    request<AllowedPassword>('/api/admin/passwords', {
      method: 'POST',
      body: JSON.stringify({ password, label }),
    }),
  revokePassword: (id: number) =>
    request<void>(`/api/admin/passwords/${id}`, { method: 'DELETE' }),
  fetchGlbBlob,
  fetchPreviewBlob,
  downloadGlb: async (jobId: number) => {
    const blob = await fetchGlbBlob(jobId)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `yeetgen_job_${jobId}.glb`
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  },
}
