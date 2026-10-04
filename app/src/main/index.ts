import { BrowserWindow, app, dialog, ipcMain, session, shell } from 'electron'
import { join, resolve } from 'node:path'
import type { ServerConnection } from '../preload/api'
import { leetcodeProblemUrl } from './links'
import { isAllowedRequest } from './requests'
import { type ServerHandle, startServer } from './server'

const repoRoot = resolve(app.getAppPath(), '..')
const rendererUrl = process.env.ELECTRON_RENDERER_URL

let server: ServerHandle | null = null

function createWindow(): void {
  const window = new BrowserWindow({
    width: 1100,
    height: 820,
    show: false,
    autoHideMenuBar: true,
    // ፩ (U+1369, Ethiopic digit one), rendered from Noto Sans Ethiopic in the design token colors.
    icon: join(app.getAppPath(), 'resources', 'icon.png'),
    webPreferences: {
      preload: join(__dirname, '../preload/index.js'),
      sandbox: true,
      contextIsolation: true,
      nodeIntegration: false,
      // Keep the Pomodoro timer's ticks on time while the window is hidden, so the alarm isn't late.
      backgroundThrottling: false
    }
  })

  window.once('ready-to-show', () => window.show())
  // The renderer never navigates away or opens windows; links in lesson content stay inert.
  window.webContents.on('will-navigate', (event) => event.preventDefault())
  window.webContents.setWindowOpenHandler(() => ({ action: 'deny' }))

  if (rendererUrl) {
    window.loadURL(rendererUrl)
  } else {
    window.loadFile(join(__dirname, '../renderer/index.html'))
  }
}

async function launch(): Promise<void> {
  session.defaultSession.webRequest.onBeforeRequest((details, callback) => {
    callback({ cancel: !isAllowedRequest(details.url) })
  })
  try {
    server = await startServer({
      serverDir: join(repoRoot, 'server'),
      dataDir: process.env.KEDAMI_DATA_DIR ?? join(repoRoot, 'data'),
      // A page loaded from file:// sends the origin "null".
      allowedOrigin: rendererUrl ? new URL(rendererUrl).origin : 'null'
    })
  } catch (error) {
    dialog.showErrorBox('Kedami could not start its server', String(error))
    app.quit()
    return
  }
  const connection: ServerConnection = { baseUrl: `http://127.0.0.1:${server.port}`, token: server.token }
  ipcMain.handle('kedami:server-connection', () => connection)
  // The renderer can only ask for a LeetCode problem by slug; main builds and checks the URL.
  ipcMain.handle('kedami:open-leetcode', async (_event, slug: unknown) => {
    const url = leetcodeProblemUrl(slug)
    if (!url) throw new Error('Not a LeetCode problem.')
    await shell.openExternal(url)
  })
  createWindow()
}

app.whenReady().then(launch)

app.on('window-all-closed', () => app.quit())
app.on('will-quit', () => server?.stop())
for (const signal of ['SIGINT', 'SIGTERM'] as const) {
  process.on(signal, () => app.quit())
}
