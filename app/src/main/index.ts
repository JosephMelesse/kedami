import { BrowserWindow, app, dialog, ipcMain, protocol, session, shell } from 'electron'
import { join, resolve } from 'node:path'
import type { MusicTrack, ServerConnection } from '../preload/api'
import { leetcodeProblemUrl } from './links'
import {
  addTrack,
  listTracks,
  MUSIC_EXTENSIONS,
  MUSIC_SCHEME,
  resolveTrack,
  trackNameFromUrl,
  trackResponse,
  trackUrl
} from './music'
import { isAllowedRequest } from './requests'
import { type ServerHandle, startServer } from './server'

const repoRoot = resolve(app.getAppPath(), '..')
const rendererUrl = process.env.ELECTRON_RENDERER_URL
const dataDir = process.env.KEDAMI_DATA_DIR ?? join(repoRoot, 'data')

// Streaming lets audio elements read tracks in ranges. This must happen before the app is ready.
protocol.registerSchemesAsPrivileged([
  { scheme: MUSIC_SCHEME, privileges: { standard: true, secure: true, stream: true } }
])

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
      dataDir,
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
  serveMusic(join(dataDir, 'music'))
  createWindow()
}

/** The renderer names tracks by file name; main copies them in, lists them, and serves them. */
function serveMusic(musicDir: string): void {
  const tracks = async (): Promise<MusicTrack[]> =>
    (await listTracks(musicDir)).map((name) => ({ name, url: trackUrl(name) }))

  protocol.handle(MUSIC_SCHEME, async (request) => {
    const path = await resolveTrack(musicDir, trackNameFromUrl(request.url))
    if (!path) return new Response('Not found', { status: 404 })
    return trackResponse(path, request.headers.get('range'))
  })
  ipcMain.handle('kedami:music-tracks', tracks)
  ipcMain.handle('kedami:music-add', async (event) => {
    const window = BrowserWindow.fromWebContents(event.sender)
    const extensions = [...MUSIC_EXTENSIONS, ...MUSIC_EXTENSIONS.map((ext) => ext.toUpperCase())]
    const options = {
      title: 'Add music',
      properties: ['openFile', 'multiSelections'] as Array<'openFile' | 'multiSelections'>,
      filters: [{ name: 'Audio', extensions }]
    }
    const picked = window ? await dialog.showOpenDialog(window, options) : await dialog.showOpenDialog(options)
    const added: string[] = []
    for (const path of picked.canceled ? [] : picked.filePaths) {
      added.push(await addTrack(musicDir, path))
    }
    return { tracks: await tracks(), added }
  })
}

app.whenReady().then(launch)

app.on('window-all-closed', () => app.quit())
app.on('will-quit', () => server?.stop())
for (const signal of ['SIGINT', 'SIGTERM'] as const) {
  process.on(signal, () => app.quit())
}
