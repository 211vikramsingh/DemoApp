/**
 * KillSwitch unit tests
 * - Renders the KILL button
 * - Opens modal on click
 * - Shows confirmation for global kill
 * - Ctrl+Shift+K shortcut opens modal
 */
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { KillSwitch } from '@/components/KillSwitch'

// Mock API
vi.mock('@/api', () => ({
  killApi: {
    execute: vi.fn().mockResolvedValue({
      data: { scope: 'global', positions_closed: 2, orders_cancelled: 3, timestamp: '', instrument: null, trade_id: null },
    }),
  },
}))

// Mock toast
vi.mock('react-hot-toast', () => ({
  default: { success: vi.fn(), error: vi.fn() },
}))

describe('KillSwitch', () => {
  it('renders the KILL button', () => {
    render(<KillSwitch />)
    expect(screen.getByRole('button', { name: /kill/i })).toBeInTheDocument()
  })

  it('opens modal on KILL button click', async () => {
    render(<KillSwitch />)
    await userEvent.click(screen.getByRole('button', { name: /kill/i }))
    expect(screen.getByRole('dialog')).toBeInTheDocument()
  })

  it('opens modal on Ctrl+Shift+K', () => {
    render(<KillSwitch />)
    fireEvent.keyDown(window, { key: 'K', ctrlKey: true, shiftKey: true })
    expect(screen.getByRole('dialog')).toBeInTheDocument()
  })

  it('shows confirmation warning for global scope', async () => {
    render(<KillSwitch />)
    await userEvent.click(screen.getByRole('button', { name: /kill/i }))
    // Click execute (first click = confirmation step)
    const executeBtn = screen.getByText(/execute global kill/i)
    await userEvent.click(executeBtn)
    expect(screen.getByText(/confirm:/i)).toBeInTheDocument()
  })

  it('can cancel the modal', async () => {
    render(<KillSwitch />)
    await userEvent.click(screen.getByRole('button', { name: /kill/i }))
    await userEvent.click(screen.getByText('Cancel'))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })
})
