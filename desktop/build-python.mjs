// Python for the installer, in desktop/python: embeddable CPython + ilovestock with the built web UI.
// Windows only. Needs Python 3.12 (`py -3.12`): its pip installs into the matching embeddable build.
import { execFileSync } from 'node:child_process'
import { appendFileSync, mkdirSync, rmSync, writeFileSync } from 'node:fs'
import path from 'node:path'

const version = '3.12.10' // the last 3.12 release with an embeddable build
const root = path.join(import.meta.dirname, '..')
const out = path.join(import.meta.dirname, 'python')
const run = (cmd, args, cwd) => execFileSync(cmd, args, { cwd, stdio: 'inherit', shell: cmd === 'npm' })

run('npm', ['ci'], path.join(root, 'web'))
run('npm', ['run', 'build'], path.join(root, 'web')) // into src/ilovestock/static: ships in the wheel

rmSync(out, { recursive: true, force: true })
mkdirSync(out)
const url = `https://www.python.org/ftp/python/${version}/python-${version}-embed-amd64.zip`
const response = await fetch(url)
if (!response.ok) throw new Error(`${url}: HTTP ${response.status}`)
writeFileSync(path.join(out, 'python.zip'), Buffer.from(await response.arrayBuffer()))
// Windows' own tar reads zip files (Git's tar, maybe first on the PATH, does not).
run(path.join(process.env.SystemRoot, 'System32', 'tar.exe'), ['-xf', 'python.zip'], out)
rmSync(path.join(out, 'python.zip'))
appendFileSync(path.join(out, 'python312._pth'), 'Lib\\site-packages\n')

const target = path.join(out, 'Lib', 'site-packages')
run('py', ['-3.12', '-m', 'pip', 'install', '--no-cache-dir', '--target', target, root], root)
