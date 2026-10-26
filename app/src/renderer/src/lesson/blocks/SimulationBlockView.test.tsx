import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { KedamiApi } from '../../../../preload/api'
import type { Job } from '../../api'
import { AGENT_POLL_MS } from '../AgentJob'
import { SimulationBlockView } from './SimulationBlockView'

const BLOCK = { type: 'simulation' as const, id: 'sim', code: '', caption: 'Drag the angle.', brief: 'Rotate a vector.' }

// What the stand-in server holds: the stored code, the jobs, and how it answers a request for a new one.
let server: { code: string; jobs: Job[]; refuse: string | null; requests: string[] }
let container: HTMLDivElement
let root: Root

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status })

beforeEach(() => {
  vi.useFakeTimers()
  container = document.createElement('div')
  document.body.append(container)
  root = createRoot(container)
  server = { code: '', jobs: [], refuse: null, requests: [] }
  window.kedami = { serverConnection: async () => ({ baseUrl: 'http://127.0.0.1:1', token: 't' }) } as KedamiApi
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init: RequestInit) => {
      const path = new URL(url).pathname
      server.requests.push(`${init.method} ${path}`)
      if (path === '/lessons/l1/blocks/sim/simulation') return json({ code: server.code, flagged: false, error: null })
      if (path === '/lessons/l1/jobs') return json({ jobs: server.jobs })
      if (path === '/lessons/l1/blocks/sim/simulation-job') {
        if (server.refuse) return json({ detail: server.refuse }, 409)
        const job: Job = { id: 7, kind: 'simulation', lesson_id: 'l1', block_id: 'sim', part_id: null, status: 'queued', error: null }
        server.jobs = [job]
        return json(job)
      }
      throw new Error(`unexpected ${path}`)
    })
  )
})

afterEach(async () => {
  await act(async () => root.unmount())
  container.remove()
  vi.unstubAllGlobals()
  vi.useRealTimers()
})

const button = (label: string) => [...container.querySelectorAll('button')].find((b) => b.textContent === label)
const progress = () => container.querySelector('.agent-job')?.textContent ?? null
const tick = () => act(async () => vi.advanceTimersByTimeAsync(AGENT_POLL_MS))
const moveJob = (status: Job['status'], error: string | null = null) => {
  server.jobs = server.jobs.map((job) => ({ ...job, status, error }))
}

async function mount() {
  await act(async () => root.render(<SimulationBlockView block={BLOCK} lessonId="l1" />))
}

describe('a simulation a Claude Code job writes', () => {
  it('starts a job when asked for, shows what it is doing, then runs the code once saved', async () => {
    await mount()
    await act(async () => button('Generate simulation')!.click())
    expect(server.requests).toContain('POST /lessons/l1/blocks/sim/simulation-job')
    expect(progress()).toContain('Waiting for another job')
    expect(button('Generate simulation')).toBeUndefined()

    moveJob('running')
    await tick()
    expect(progress()).toContain('Claude Code is writing this simulation')
    expect(container.querySelector('iframe')).toBeNull()

    server.code = 'draw(); ready()'
    moveJob('done')
    await tick()
    expect(progress()).toBeNull()
    expect(container.querySelector('iframe.simulation-frame')).not.toBeNull()
    expect(button('Regenerate')).toBeDefined()
  })

  it('swaps in the new code when a regenerate job is done', async () => {
    server.code = 'old(); ready()'
    await mount()
    await act(async () => button('Regenerate')!.click())
    expect(progress()).not.toBeNull()
    server.code = 'new(); ready()'
    moveJob('done')
    await tick()
    expect(progress()).toBeNull()
    expect(container.querySelector('iframe.simulation-frame')).not.toBeNull()
  })

  it("shows why a job failed, in Claude Code's words, and offers the button again", async () => {
    await mount()
    await act(async () => button('Generate simulation')!.click())
    moveJob('failed', 'Claude Code ran longer than 20 minutes and was stopped.')
    await tick()
    expect(container.querySelector('.answer-error')?.textContent).toBe(
      'Claude Code ran longer than 20 minutes and was stopped.'
    )
    expect(button('Generate simulation')).toBeDefined()
    expect(progress()).toBeNull()
  })

  it("shows the server's reason when it refuses, such as Claude Code not being installed", async () => {
    server.refuse = "Claude Code isn't installed. Install it from code.claude.com and log in once in the Terminal panel."
    await mount()
    await act(async () => button('Generate simulation')!.click())
    expect(container.querySelector('.answer-error')?.textContent).toContain("Claude Code isn't installed")
    expect(button('Generate simulation')).toBeDefined()
  })
})
