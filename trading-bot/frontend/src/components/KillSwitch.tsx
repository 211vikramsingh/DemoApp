/**
 * KillSwitch component
 * - Always-visible red KILL button in the header
 * - Ctrl+Shift+K keyboard shortcut
 * - Scope selector modal (global / instrument / trade)
 * - Double-confirmation for global kill
 */
import React, { useState, useEffect, useCallback } from 'react'
import toast from 'react-hot-toast'
import { killApi } from '@/api'
import type { KillScope } from '@/types'

interface KillSwitchProps {
  compact?: boolean
}

export const KillSwitch: React.FC<KillSwitchProps> = ({ compact = false }) => {
  const [open, setOpen] = useState(false)
  const [scope, setScope] = useState<KillScope>('global')
  const [instrument, setInstrument] = useState('')
  const [tradeId, setTradeId] = useState('')
  const [confirm, setConfirm] = useState(false)
  const [loading, setLoading] = useState(false)

  // Keyboard shortcut: Ctrl+Shift+K
  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    if (e.ctrlKey && e.shiftKey && e.key === 'K') {
      e.preventDefault()
      setOpen(true)
    }
  }, [])

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [handleKeyDown])

  const handleOpen = () => {
    setScope('global')
    setInstrument('')
    setTradeId('')
    setConfirm(false)
    setOpen(true)
  }

  const handleExecute = async () => {
    if (scope === 'global' && !confirm) {
      setConfirm(true)
      return
    }
    setLoading(true)
    try {
      const payload = {
        scope,
        ...(scope === 'instrument' || scope === 'trade' ? { instrument } : {}),
        ...(scope === 'trade' ? { trade_id: tradeId } : {}),
      }
      const { data } = await killApi.execute(payload)
      toast.success(
        `Kill executed: ${data.positions_closed} positions closed, ${data.orders_cancelled} orders cancelled`,
        { duration: 8000 }
      )
      setOpen(false)
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Kill switch failed'
      toast.error(msg)
    } finally {
      setLoading(false)
      setConfirm(false)
    }
  }

  return (
    <>
      <button
        onClick={handleOpen}
        className="kill-btn"
        aria-label="Kill Switch (Ctrl+Shift+K)"
        title="Kill Switch — Ctrl+Shift+K"
        style={{
          background: '#dc2626',
          color: '#fff',
          border: 'none',
          borderRadius: 6,
          padding: compact ? '4px 10px' : '8px 18px',
          fontWeight: 700,
          fontSize: compact ? 13 : 15,
          cursor: 'pointer',
          letterSpacing: 1,
        }}
      >
        ⚡ KILL
      </button>

      {open && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="kill-modal-title"
          style={{
            position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)',
            display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 9999,
          }}
        >
          <div style={{
            background: '#1a1a2e', border: '2px solid #dc2626', borderRadius: 10,
            padding: 32, minWidth: 380, color: '#fff',
          }}>
            <h2 id="kill-modal-title" style={{ color: '#dc2626', margin: 0 }}>
              ⚡ Kill Switch
            </h2>
            <p style={{ color: '#aaa', fontSize: 13 }}>
              Cancels all open orders and exits positions for the selected scope.
              This action cannot be undone.
            </p>

            <div style={{ marginBottom: 16 }}>
              <label style={{ fontWeight: 600 }}>Scope</label>
              <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
                {(['global', 'instrument', 'trade'] as KillScope[]).map((s) => (
                  <button
                    key={s}
                    onClick={() => { setScope(s); setConfirm(false) }}
                    style={{
                      background: scope === s ? '#dc2626' : '#333',
                      color: '#fff', border: 'none', borderRadius: 4,
                      padding: '6px 14px', cursor: 'pointer', fontWeight: scope === s ? 700 : 400,
                    }}
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>

            {(scope === 'instrument' || scope === 'trade') && (
              <div style={{ marginBottom: 12 }}>
                <label>Instrument (e.g. NIFTY, BTCUSDT)</label>
                <input
                  value={instrument}
                  onChange={(e) => setInstrument(e.target.value)}
                  placeholder="NIFTY"
                  style={{ display: 'block', width: '100%', marginTop: 4, padding: 8, borderRadius: 4, border: '1px solid #555', background: '#111', color: '#fff' }}
                />
              </div>
            )}

            {scope === 'trade' && (
              <div style={{ marginBottom: 12 }}>
                <label>Trade / Order ID</label>
                <input
                  value={tradeId}
                  onChange={(e) => setTradeId(e.target.value)}
                  placeholder="order-uuid"
                  style={{ display: 'block', width: '100%', marginTop: 4, padding: 8, borderRadius: 4, border: '1px solid #555', background: '#111', color: '#fff' }}
                />
              </div>
            )}

            {confirm && scope === 'global' && (
              <p style={{ color: '#fbbf24', fontWeight: 700, border: '1px solid #fbbf24', borderRadius: 4, padding: '8px 12px' }}>
                ⚠ CONFIRM: This will exit ALL positions and cancel ALL orders across all brokers. Click again to confirm.
              </p>
            )}

            <div style={{ display: 'flex', gap: 10, marginTop: 20 }}>
              <button
                onClick={handleExecute}
                disabled={loading}
                style={{
                  background: confirm ? '#7f1d1d' : '#dc2626',
                  color: '#fff', border: 'none', borderRadius: 6,
                  padding: '10px 24px', fontWeight: 700, cursor: loading ? 'not-allowed' : 'pointer',
                  fontSize: 15,
                }}
              >
                {loading ? 'Executing…' : confirm ? 'CONFIRM KILL' : `Execute ${scope} kill`}
              </button>
              <button
                onClick={() => setOpen(false)}
                style={{
                  background: '#333', color: '#fff', border: 'none',
                  borderRadius: 6, padding: '10px 18px', cursor: 'pointer',
                }}
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}

export default KillSwitch
