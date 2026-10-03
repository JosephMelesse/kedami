// Starts the local Python server and waits for it to answer /health.
import { type ChildProcess, spawn } from 'node:child_process'
import { randomBytes } from 'node:crypto'
import { createServer } from 'node:net'
import { join } from 'node:path'

export interface ServerInfo {
  port: number
  token: string
}

export interface ServerHandle extends ServerInfo {
  stop(): void
}

interface StartOptions {
  serverDir: string
  dataDir: string
  allowedOrigin: string
}

const HEALTH_TIMEOUT_MS = 20_000
const HEALTH_INTERVAL_MS = 200

export async function startServer(options: StartOptions): Promise<ServerHandle> {
  const external = externalServer()
  if (external) {
    await waitForHealth(external)
    return { ...external, stop: () => {} }
  }

  const info = { port: await freePort(), token: randomBytes(32).toString('hex') }
  const child = spawn(pythonPath(options.serverDir), ['-m', 'kedami_server'], {
    cwd: options.serverDir,
    env: {
      ...process.env,
      KEDAMI_PORT: String(info.port),
      KEDAMI_TOKEN: info.token,
      KEDAMI_DATA_DIR: options.dataDir,
      KEDAMI_ALLOWED_ORIGINS: options.allowedOrigin
    },
    stdio: ['ignore', 'inherit', 'inherit']
  })
  const stop = (): void => {
    if (child.exitCode === null) child.kill()
  }

  try {
    await Promise.race([waitForHealth(info), exited(child)])
  } catch (error) {
    stop()
    throw error
  }
  return { ...info, stop }
}

// Lets a server started by hand be used instead of spawning one.
function externalServer(): ServerInfo | null {
  const { KEDAMI_PORT, KEDAMI_TOKEN } = process.env
  if (!KEDAMI_PORT || !KEDAMI_TOKEN) return null
  return { port: Number(KEDAMI_PORT), token: KEDAMI_TOKEN }
}

function pythonPath(serverDir: string): string {
  if (process.env.KEDAMI_PYTHON) return process.env.KEDAMI_PYTHON
  return process.platform === 'win32'
    ? join(serverDir, '.venv', 'Scripts', 'python.exe')
    : join(serverDir, '.venv', 'bin', 'python')
}

function freePort(): Promise<number> {
  return new Promise((resolve, reject) => {
    const probe = createServer()
    probe.once('error', reject)
    probe.listen(0, '127.0.0.1', () => {
      const address = probe.address()
      const port = typeof address === 'object' && address ? address.port : 0
      probe.close(() => resolve(port))
    })
  })
}

async function waitForHealth({ port, token }: ServerInfo): Promise<void> {
  const deadline = Date.now() + HEALTH_TIMEOUT_MS
  while (Date.now() < deadline) {
    try {
      const response = await fetch(`http://127.0.0.1:${port}/health`, {
        headers: { Authorization: `Bearer ${token}` }
      })
      if (response.ok) return
    } catch {
      // Not listening yet.
    }
    await new Promise((resolve) => setTimeout(resolve, HEALTH_INTERVAL_MS))
  }
  throw new Error(`server did not become healthy on port ${port}`)
}

function exited(child: ChildProcess): Promise<never> {
  return new Promise((_, reject) => {
    child.once('error', reject)
    child.once('exit', (code) => reject(new Error(`server exited with code ${code}`)))
  })
}
