// The terminal view's preload. Main accepts terminal messages only from this view's webContents.
import { contextBridge, ipcRenderer } from 'electron'
import type { TerminalApi } from './terminal-api'

const api: TerminalApi = {
  state: () => ipcRenderer.invoke('terminal:state'),
  start: (kind, cols, rows) => ipcRenderer.invoke('terminal:start', kind, cols, rows),
  input: (data) => ipcRenderer.send('terminal:input', data),
  resize: (cols, rows) => ipcRenderer.send('terminal:resize', cols, rows),
  onData: (listener) => {
    ipcRenderer.on('terminal:data', (_event, data: string) => listener(data))
  },
  onExit: (listener) => {
    ipcRenderer.on('terminal:exit', (_event, code: number) => listener(code))
  },
  onShown: (listener) => {
    ipcRenderer.on('terminal:shown', () => listener())
  }
}

contextBridge.exposeInMainWorld('terminal', api)
