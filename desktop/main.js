// Desktop window for the local web app: runs `ilovestock serve`, shows it, stops it on close.
import { spawn } from 'node:child_process'
import path from 'node:path'
import { app, BrowserWindow, dialog } from 'electron'

const bin = process.env.ILOVESTOCK_BIN || 'ilovestock' // e.g. ..\.venv\Scripts\ilovestock.exe
let server
let win
let output = ''
let quitting = false

function fail(message) {
  if (quitting) return
  quitting = true
  dialog.showErrorBox('ilovestock', message)
  app.quit()
}

function open(url) {
  const icon = path.join(import.meta.dirname, '..', 'web', 'public', 'logo.png')
  const w = new BrowserWindow({ width: 1280, height: 860, icon })
  const origin = new URL(url).origin
  w.webContents.setWindowOpenHandler(() => ({ action: 'deny' }))
  w.webContents.on('will-navigate', (event, target) => {
    if (new URL(target).origin !== origin) event.preventDefault()
  })
  // `serve` prints the URL just before uvicorn listens: retry while the connection is refused.
  w.webContents.on('did-fail-load', (_event, code) => {
    if (code === -102) setTimeout(() => w.loadURL(url), 300)
  })
  w.loadURL(url)
  return w
}

app.whenReady().then(() => {
  server = spawn(bin, ['serve'], {
    windowsHide: true,
    env: { ...process.env, PYTHONUNBUFFERED: '1', PYTHONIOENCODING: 'utf-8' },
  })
  const read = (chunk) => {
    output += chunk
    const match = !win && output.match(/http:\/\/127\.0\.0\.1:\d+/)
    if (match) win = open(match[0])
  }
  server.stdout.on('data', read)
  server.stderr.on('data', read)
  server.on('error', (e) => fail(`Cannot start ${bin}: ${e.message}`))
  server.on('exit', () => fail(`The ilovestock server stopped.\n\n${output.trim()}`))
})

app.on('window-all-closed', () => app.quit())
app.on('before-quit', () => {
  quitting = true
  server?.kill()
})
