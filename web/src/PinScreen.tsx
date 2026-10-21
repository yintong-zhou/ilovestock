import { type FormEvent, type ReactNode, useState } from 'react'

import { api } from './api'
import { Button, Field, Message } from './components'
import { Wordmark } from './Sidebar'

const pinInput =
  'h-14 w-full rounded-sm border border-line bg-well px-4 text-center text-2xl tracking-[0.5em] text-text focus:border-teal-tint focus:outline-none'

function Card({ title, children, onSubmit }: { title: string; children: ReactNode; onSubmit?: (e: FormEvent) => void }) {
  const Tag = onSubmit ? 'form' : 'section'
  return (
    <main className="flex min-h-screen items-center justify-center bg-navy p-4">
      <Tag onSubmit={onSubmit} className="w-full max-w-sm rounded-md border border-line bg-canvas p-8">
        <Wordmark />
        <h1 className="mt-8 text-xl font-semibold">{title}</h1>
        {children}
      </Tag>
    </main>
  )
}

export default function PinScreen({ mode, onUnlocked }: { mode: 'setup' | 'unlock'; onUnlocked: () => void }) {
  const [pin, setPin] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  // The PIN is set in the terminal, so no other program on this computer can claim the app first.
  if (mode === 'setup')
    return (
      <Card title="No PIN set">
        <p className="mt-2 text-muted">
          The PIN is set in the terminal. Stop the server and run{' '}
          <code className="text-text">ilovestock serve</code> again: it asks for a PIN (4 to 8 digits).
        </p>
      </Card>
    )

  async function submit(e: FormEvent) {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      await api.unlock(pin)
      onUnlocked()
    } catch (err) {
      setError((err as Error).message)
      setPin('')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card title="Enter your PIN" onSubmit={submit}>
      <p className="mt-2 text-muted">The app is locked.</p>
      <div className="mt-6">
        <Field label="PIN">
          <input
            className={pinInput}
            type="password"
            inputMode="numeric"
            autoComplete="off"
            maxLength={8}
            autoFocus
            value={pin}
            onChange={(e) => setPin(e.target.value.replace(/\D/g, ''))}
          />
        </Field>
      </div>
      {error && <Message kind="error">{error}</Message>}
      <Button type="submit" disabled={busy || !pin} className="mt-6 w-full">
        Unlock
      </Button>
      <p className="mt-6 text-sm text-muted">
        Forgot the PIN? Run <code className="text-text">ilovestock pin reset</code> in a terminal.
      </p>
    </Card>
  )
}
