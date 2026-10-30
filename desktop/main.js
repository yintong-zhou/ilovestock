// Desktop window for the local web app: runs `ilovestock serve`, shows it, stops it on close.
import { spawn } from 'node:child_process'
import path from 'node:path'
import readline from 'node:readline'
import { pathToFileURL } from 'node:url'
import { app, BrowserWindow, dialog, ipcMain, Menu } from 'electron'

const ASK_PIN = 'ilovestock: set PIN' // printed by `serve` (cli.py) when no PIN is set
// Installed: the bundled Python (resources/python). From the repo: `ilovestock` on the PATH.
const [bin, cli] = app.isPackaged
  ? [path.join(process.resourcesPath, 'python', 'python.exe'), ['-m', 'ilovestock']]
  : [process.env.ILOVESTOCK_BIN || 'ilovestock', []] // e.g. ..\.venv\Scripts\ilovestock.exe
const options = {
  windowsHide: true,
  env: { ...process.env, PYTHONUNBUFFERED: '1', PYTHONIOENCODING: 'utf-8' },
}
const pinPage = path.join(import.meta.dirname, 'pin.html')
const starting = `data:text/html;charset=utf-8,${encodeURIComponent(
  '<body style="margin:0;height:100vh;display:grid;place-items:center;background:#0b3d62;' +
    'color:#eef3f6;font:18px Segoe UI,sans-serif">Starting iLoveStock…</body>',
)}`
let win
let server
let origin // of the running server: the only site the window may navigate to
let quitting = false

function fail(message) {
  if (quitting) return
  quitting = true
  dialog.showErrorBox('iLoveStock', message)
  app.quit()
}

function start() {
  const proc = spawn(bin, [...cli, 'serve'], options)
  let output = ''
  let asked = false
  server = proc
  // The tail only: `serve` writes every warning to stderr, the reason it stopped comes last.
  const keep = (text) => (output = (output + text).slice(-4000))
  readline.createInterface({ input: proc.stdout }).on('line', (line) => {
    keep(`${line}\n`)
    const url = line.match(/http:\/\/127\.0\.0\.1:\d+/)?.[0]
    if (line === ASK_PIN) {
      win.loadFile(pinPage, { query: asked ? { error: '1' } : {} }) // asked again: PIN refused
      asked = true
    } else if (url) {
      origin = new URL(url).origin
      win.loadURL(url)
    }
  })
  proc.stderr.on('data', keep)
  proc.on('error', (e) => fail(`Cannot start ${bin}: ${e.message}`))
  proc.on('close', () => {
    if (proc === server) fail(`The iLoveStock server stopped.\n\n${output.trim()}`)
  })
}

async function resetPin() {
  const { response } = await dialog.showMessageBox(win, {
    type: 'warning',
    buttons: ['Reset PIN', 'Cancel'],
    defaultId: 1,
    cancelId: 1,
    message: 'Reset the PIN?',
    detail: 'You will choose a new PIN. History, watchlist and settings are kept.',
  })
  if (response !== 0) return
  const old = server
  server = null // its exit is expected now
  old?.kill()
  origin = undefined
  win.loadURL(starting)
  const reset = spawn(bin, [...cli, 'pin', 'reset', '--yes'], options)
  const code = await new Promise((resolve) => reset.on('close', resolve))
  if (code !== 0) dialog.showErrorBox('iLoveStock', 'The PIN could not be reset.')
  start()
}

function createWindow() {
  win = new BrowserWindow({
    width: 1280,
    height: 860,
    icon: path.join(import.meta.dirname, 'logo.png'),
    webPreferences: { preload: path.join(import.meta.dirname, 'preload.cjs') },
  })
  win.webContents.setWindowOpenHandler(() => ({ action: 'deny' }))
  win.webContents.on('will-navigate', (event, target) => {
    if (new URL(target).origin !== origin) event.preventDefault()
  })
  // `serve` prints the URL just before uvicorn listens: retry while the connection is refused.
  win.webContents.on('did-fail-load', (_event, code, _text, url) => {
    if (code === -102 && new URL(url).origin === origin) setTimeout(() => win.loadURL(url), 300)
  })
  win.loadURL(starting)
}

// Only pin.html may answer `serve`, and only with what it accepts (one line, 4 to 8 digits).
ipcMain.on('pin', (event, pin) => {
  if (event.senderFrame?.url.startsWith(pathToFileURL(pinPage).href) && /^\d{4,8}$/.test(pin))
    server?.stdin.write(`${pin}\n`)
})

if (!app.requestSingleInstanceLock()) app.quit()
else
  app.whenReady().then(() => {
    Menu.setApplicationMenu(
      Menu.buildFromTemplate([
        {
          label: 'iLoveStock',
          submenu: [{ label: 'Reset PIN…', click: resetPin }, { type: 'separator' }, { role: 'quit' }],
        },
        { role: 'editMenu' },
        { role: 'viewMenu' },
      ]),
    )
    createWindow()
    start()
  })

// A second double-click on the shortcut brings this window back instead of a second server.
app.on('second-instance', () => {
  if (win?.isMinimized()) win.restore()
  win?.focus()
})
app.on('window-all-closed', () => app.quit())
app.on('before-quit', () => {
  quitting = true
  server?.kill()
})
