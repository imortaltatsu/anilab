import { useState } from 'react'
import type { FormEvent } from 'react'
import {
  ShieldCheck,
  Key,
  Trash2,
  Plus,
  Cpu,
} from 'lucide-react'
import { api } from './api'
import type { AllowedPassword } from './api'

type Props = {
  passwords: AllowedPassword[]
  onRefresh: () => Promise<void>
}

export function AdminPortal({ passwords, onRefresh }: Props) {
  const [newLabel, setNewLabel] = useState('team-creator')
  const [newPassword, setNewPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  async function handleAddPassword(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setSuccess(null)
    setBusy(true)
    try {
      await api.addPassword(newPassword, newLabel)
      setNewPassword('')
      setNewLabel('team-creator')
      setSuccess('New access token allowlisted successfully.')
      await onRefresh()
      setTimeout(() => setSuccess(null), 3000)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  async function handleRevoke(id: number) {
    if (!confirm(`Revoke access token #${id}?`)) return
    try {
      await api.revokePassword(id)
      await onRefresh()
    } catch (err) {
      alert(err instanceof Error ? err.message : String(err))
    }
  }

  return (
    <div style={{ flex: 1, overflowY: 'auto', padding: '24px', background: 'var(--bg-darker)', color: 'var(--text-main)' }}>
      <div style={{ maxWidth: '960px', margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '24px' }}>
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <ShieldCheck size={24} style={{ color: 'var(--emerald-accent)' }} />
          <div>
            <h2 style={{ fontSize: '18px', fontWeight: 700, color: 'var(--text-bright)' }}>
              Hidden Admin & Cluster Telemetry Portal
            </h2>
            <p style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
              Master Admin Mode unlocked. Manage creator access passwords and GPU worker pools.
            </p>
          </div>
        </div>

        {/* GPU Cluster Telemetry Cards */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '16px' }}>
          <div style={{ background: 'var(--bg-main)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-md)', padding: '16px' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
              <span style={{ fontWeight: 600, color: 'var(--text-bright)', display: 'flex', alignItems: 'center', gap: '6px' }}>
                <Cpu size={16} style={{ color: 'var(--emerald-accent)' }} />
                GPU Node #0
              </span>
              <span style={{ fontSize: '11px', color: 'var(--emerald-accent)', background: 'rgba(16, 185, 129, 0.12)', padding: '2px 6px', borderRadius: '4px' }}>
                Online · Ready
              </span>
            </div>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
              Model: NVIDIA RTX 4000 Ada (20 GB VRAM)<br />
              Pipelines: Shape Gen · 4K UV Bake · Auto-Rigging
            </div>
          </div>

          <div style={{ background: 'var(--bg-main)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-md)', padding: '16px' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
              <span style={{ fontWeight: 600, color: 'var(--text-bright)', display: 'flex', alignItems: 'center', gap: '6px' }}>
                <Cpu size={16} style={{ color: 'var(--emerald-accent)' }} />
                GPU Node #1
              </span>
              <span style={{ fontSize: '11px', color: 'var(--emerald-accent)', background: 'rgba(16, 185, 129, 0.12)', padding: '2px 6px', borderRadius: '4px' }}>
                Online · Ready
              </span>
            </div>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
              Model: NVIDIA RTX 4000 Ada (20 GB VRAM)<br />
              Concurrency: 2 Parallel 3D Jobs
            </div>
          </div>
        </div>

        {/* Add Allowed Password Form */}
        <div style={{ background: 'var(--bg-main)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-md)', padding: '20px' }}>
          <h3 style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-bright)', marginBottom: '14px', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Plus size={14} style={{ color: 'var(--blender-orange)' }} />
            <span>Allowlist New Creator Access Password</span>
          </h3>

          <form onSubmit={handleAddPassword} style={{ display: 'grid', gridTemplateColumns: '1fr 1.2fr auto', gap: '10px' }}>
            <input
              type="text"
              required
              placeholder="Label (e.g. game-studio-a)"
              value={newLabel}
              onChange={(e) => setNewLabel(e.target.value)}
            />
            <input
              type="password"
              required
              minLength={4}
              placeholder="Access password…"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
            />
            <button type="submit" className="primary" disabled={busy}>
              <span>{busy ? 'Adding…' : 'Add Password'}</span>
            </button>
          </form>

          {error && <div className="auth-error" style={{ marginTop: '12px' }}>{error}</div>}
          {success && (
            <div style={{ fontSize: '12px', color: 'var(--emerald-accent)', marginTop: '12px' }}>
              {success}
            </div>
          )}
        </div>

        {/* Active Allowed Passwords Table */}
        <div style={{ background: 'var(--bg-main)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-md)', padding: '20px' }}>
          <h3 style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-bright)', marginBottom: '14px', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Key size={14} style={{ color: 'var(--cyan-accent)' }} />
            <span>Active Access Passwords ({passwords.length})</span>
          </h3>

          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border-subtle)', textAlign: 'left', color: 'var(--text-dim)' }}>
                <th style={{ padding: '8px' }}>ID</th>
                <th style={{ padding: '8px' }}>Label</th>
                <th style={{ padding: '8px' }}>Created At</th>
                <th style={{ padding: '8px', textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {passwords.map((p) => (
                <tr key={p.id} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                  <td style={{ padding: '10px 8px', fontFamily: 'var(--font-mono)' }}>#{p.id}</td>
                  <td style={{ padding: '10px 8px', fontWeight: 600, color: 'var(--text-bright)' }}>{p.label}</td>
                  <td style={{ padding: '10px 8px', color: 'var(--text-muted)' }}>{new Date(p.created_at).toLocaleString()}</td>
                  <td style={{ padding: '10px 8px', textAlign: 'right' }}>
                    <button
                      type="button"
                      className="danger"
                      style={{ padding: '3px 8px', fontSize: '11px' }}
                      onClick={() => handleRevoke(p.id)}
                    >
                      <Trash2 size={11} />
                      <span>Revoke</span>
                    </button>
                  </td>
                </tr>
              ))}
              {passwords.length === 0 && (
                <tr>
                  <td colSpan={4} style={{ padding: '20px', textAlign: 'center', color: 'var(--text-dim)' }}>
                    No custom allowlisted passwords.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
