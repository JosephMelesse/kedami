import { contextBridge, ipcRenderer } from 'electron'
import type { KedamiApi } from './api'

// The token travels over IPC rather than the command line, where other local users could read it.
const api: KedamiApi = {
  serverConnection: () => ipcRenderer.invoke('kedami:server-connection'),
  musicTracks: () => ipcRenderer.invoke('kedami:music-tracks'),
  addMusic: () => ipcRenderer.invoke('kedami:music-add'),
  showTerminal: (bounds) => ipcRenderer.send('kedami:terminal-show', bounds),
  hideTerminal: () => ipcRenderer.send('kedami:terminal-hide'),
  onTerminalToggle: (listener) => {
    const handler = () => listener()
    ipcRenderer.on('kedami:terminal-toggle', handler)
    return () => ipcRenderer.removeListener('kedami:terminal-toggle', handler)
  }
}

contextBridge.exposeInMainWorld('kedami', api)
