import { contextBridge, ipcRenderer } from 'electron'
import type { KedamiApi } from './api'

// The token travels over IPC rather than the command line, where other local users could read it.
const api: KedamiApi = {
  serverConnection: () => ipcRenderer.invoke('kedami:server-connection')
}

contextBridge.exposeInMainWorld('kedami', api)
