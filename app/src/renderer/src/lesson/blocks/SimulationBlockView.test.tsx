import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, type Mock, vi } from 'vitest'
import type { KedamiApi } from '../../../../preload/api'
import { AGENT_POLL_MS } from '../AgentCommand'
import { SimulationBlockView } from './SimulationBlockView'

const BLOCK = { type: 'simulation' as const, id: 'sim', code: '', caption: 'Drag the angle.', brief: 'Rotate a vector.' }

let container: HTMLDivElement
let root: Root
let fetchMock: Mock

beforeEach(() => {
  vi.useFakeTimers()
  container = document.createElement('div')
  document.body.append(container)
  root = createRoot(container)
  window.kedami = { serverConnection: async () => ({ baseUrl: 'http://127.0.0.1:1', token: 't' }) } as KedamiApi
  fetchMock = vi.fn()
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(async () => {
  await act(async () => root.unmount())
  container.remove()
  vi.unstubAllGlobals()
  vi.useRealTimers()
})

const reply = (code: string) =>
  fetchMock.mockResolvedValueOnce(new Response(JSON.stringify({ code, flagged: false, error: null })))
const button = (label: string) => [...container.querySelectorAll('button')].find((b) => b.textContent === label)

describe('a simulation Claude Code writes', () => {
  it('shows the command when asked for, then runs the code once it is saved', async () => {
    reply('')
    await act(async () => root.render(<SimulationBlockView block={BLOCK} lessonId="l1" />))
    await act(async () => button('Generate simulation')!.click())
    expect(container.querySelector('.agent-command code')?.textContent).toBe('/kedami:simulation l1 sim')

    reply('')
    await act(async () => vi.advanceTimersByTimeAsync(AGENT_POLL_MS))
    expect(container.querySelector('iframe')).toBeNull()

    reply('draw(); ready()')
    await act(async () => vi.advanceTimersByTimeAsync(AGENT_POLL_MS))
    expect(container.querySelector('.agent-command')).toBeNull()
    expect(container.querySelector('iframe.simulation-frame')).not.toBeNull()
    expect(button('Regenerate')).toBeDefined()
  })

  it('waits for code different from what is there when regenerating', async () => {
    reply('old(); ready()')
    await act(async () => root.render(<SimulationBlockView block={BLOCK} lessonId="l1" />))
    await act(async () => button('Regenerate')!.click())
    reply('old(); ready()')
    await act(async () => vi.advanceTimersByTimeAsync(AGENT_POLL_MS))
    expect(container.querySelector('.agent-command')).not.toBeNull()
    reply('new(); ready()')
    await act(async () => vi.advanceTimersByTimeAsync(AGENT_POLL_MS))
    expect(container.querySelector('.agent-command')).toBeNull()
  })
})
