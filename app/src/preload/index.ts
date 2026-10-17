import { contextBridge, ipcRenderer } from 'electron'
import type { KedamiApi } from './api'

// The token travels over IPC rather than the command line, where other local users could read it.
const api: KedamiApi = {
  serverConnection: () => ipcRenderer.invoke('kedami:server-connection'),
  openLeetCode: (slug) => ipcRenderer.invoke('kedami:open-leetcode', slug),
  openPgExercises: (path) => ipcRenderer.invoke('kedami:open-pgexercises', path),
  musicTracks: () => ipcRenderer.invoke('kedami:music-tracks'),
  addMusic: () => ipcRenderer.invoke('kedami:music-add'),
  runnerFiles: () => ipcRenderer.invoke('kedami:runner-files')
}

contextBridge.exposeInMainWorld('kedami', api)
