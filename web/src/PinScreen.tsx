import { type FormEvent, useState } from 'react'

import { api } from './api'
import { Button, Field, Message } from './components'
import { Wordmark } from './Sidebar'

const PIN_RE = /^\d{4,8}$/
const pinInput =
  'h-14 w-full rounded-sm border border-line bg-well px-4 text-center text-2xl tracking-[0.5em] text-text focus:border-teal-tint focus:outline-none'

export default function PinScreen({ mode, onUnlocked }: { mode: 'setup' | 'unlock'; onUnlocked: () => void }) {
  const [pin, setPin] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const setup = mode === 'setup'

  async function submit(e: FormEvent) {
    e.preventDefault()
    setError('')
    if (setup && !PIN_RE.test(pin)) return setError('Use 4 to 8 digits.')
    if (setup && pin !== confirm) return setError('The two PINs are different. Type the same PIN twice.')
    setBusy(true)
    try {
      await (setup ? api.setupPin(pin) : api.unlock(pin))
      onUnlocked()
    } catch (err) {
      setError((err as Error).message)
      setPin('')
    } finally {
      setBusy(false)
    }
  }

  const digits = (value: string, set: (v: string) => void, autoFocus = false) => (
    <input
      className={pinInput}
      type="password"
      inputMode="numeric"
      autoComplete="off"
      maxLength={8}
      autoFocus={autoFocus}
      value={value}
      onChange={(e) => set(e.target.value.replace(/\D/g, ''))}
    />
  )

  return (
    <main className="flex min-h-screen items-center justify-center bg-navy p-4">
      <form onSubmit={submit} className="w-full max-w-sm rounded-md border border-line bg-canvas p-8">
        <Wordmark />
        <h1 className="mt-8 text-xl font-semibold">{setup ? 'Set a PIN' : 'Enter your PIN'}</h1>
        <p className="mt-2 text-muted">
          {setup ? 'The PIN locks this app on this computer. Use 4 to 8 digits.' : 'The app is locked.'}
        </p>
        <div className="mt-6 flex flex-col gap-4">
          <Field label="PIN">{digits(pin, setPin, true)}</Field>
          {setup && <Field label="Confirm PIN">{digits(confirm, setConfirm)}</Field>}
        </div>
        {error && <Message kind="error">{error}</Message>}
        <Button type="submit" disabled={busy || !pin} className="mt-6 w-full">
          {setup ? 'Set PIN' : 'Unlock'}
        </Button>
        <p className="mt-6 text-sm text-muted">
          Forgot the PIN? Run <code className="text-text">ilovestock pin reset</code> in a terminal.
        </p>
      </form>
    </main>
  )
}
