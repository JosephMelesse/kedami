import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, type Mock, vi } from 'vitest'
import type { KedamiApi } from '../../../../preload/api'
import type { SolutionResponse } from '../../api'
import { ShowSolution } from './ShowSolution'

const PHYSICS: SolutionResponse = {
  solution: {
    format: 'physics',
    given: ['v_0 = 10\\,\\mathrm{m/s}'],
    required: ['v_x'],
    steps: ['v_x = v_0 \\cos\\theta', '\\boxed{v_x = 8.66\\,\\mathrm{m/s}}']
  },
  matches: true
}

const MATH: SolutionResponse = {
  solution: { format: 'math', method: 'Integration by parts', steps: ['\\int x e^x\\,dx', '\\boxed{(x - 1)e^x + C}'] },
  matches: true
}

const GENERAL: SolutionResponse = {
  solution: {
    format: 'general',
    steps: ['The x87 FPU has eight data registers.', 'Each holds an extended-precision value of $80$ bits.', '**80** bits']
  },
  matches: true
}

let container: HTMLDivElement
let root: Root
let fetchMock: Mock

beforeEach(() => {
  container = document.createElement('div')
  document.body.append(container)
  root = createRoot(container)
  window.kedami = { serverConnection: async () => ({ baseUrl: 'http://127.0.0.1:1', token: 't' }) } as KedamiApi
  fetchMock = vi.fn()
  vi.stubGlobal('fetch', fetchMock)
  // jsdom's dialog may lack showModal; the dialog only needs to be in the DOM here.
  HTMLDialogElement.prototype.showModal ??= function (this: HTMLDialogElement) {
    this.open = true
  }
})

afterEach(async () => {
  await act(async () => root.unmount())
  container.remove()
  vi.unstubAllGlobals()
})

function reply(body: unknown, status = 200) {
  fetchMock.mockResolvedValueOnce(new Response(JSON.stringify(body), { status }))
}

async function mount() {
  await act(async () => root.render(<ShowSolution lessonId="l1" blockId="ps1-1" partId="a" name="PS1 #1 (a)" />))
}

const button = (label: string) =>
  [...container.querySelectorAll('button')].find((b) => b.textContent === label) as HTMLButtonElement | undefined
const click = (label: string) => act(async () => button(label)!.click())
const confirm = () => act(async () => container.querySelector<HTMLButtonElement>('dialog .button-primary')!.click())
const labels = () => [...container.querySelectorAll('.solution-label')].map((l) => l.textContent)
const lines = () => [...container.querySelectorAll('.solution-line')]

describe('ShowSolution', () => {
  it('asks before showing, and writes nothing until confirmed', async () => {
    await mount()
    await click('Show solution')
    expect(container.querySelector('dialog h2')?.textContent).toBe('Show the solution to PS1 #1 (a)?')
    expect(fetchMock).not.toHaveBeenCalled()
    await click('Cancel')
    expect(container.querySelector('dialog')).toBeNull()
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('shows a physics solution as Given, Required, and Solution, each line as display math', async () => {
    reply(PHYSICS)
    await mount()
    await click('Show solution')
    await confirm()

    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('http://127.0.0.1:1/lessons/l1/blocks/ps1-1/solution')
    expect([init.method, JSON.parse(init.body)]).toEqual(['POST', { part_id: 'a' }])
    expect(labels()).toEqual(['Given', 'Required', 'Solution'])
    expect(lines()).toHaveLength(4)
    expect(lines().every((line) => line.querySelector('.katex-display'))).toBe(true)
    expect(container.textContent).not.toContain("Doesn't match")
  })

  it('shows a math solution as the method, then the working', async () => {
    reply(MATH)
    await mount()
    await click('Show solution')
    await confirm()
    expect(labels()).toEqual(['Method', 'Solution'])
    expect(container.querySelector('.solution-method')?.textContent).toBe('Integration by parts')
    expect(lines()).toHaveLength(2)
  })

  it('shows a general solution as Markdown lines, then the answer', async () => {
    reply(GENERAL)
    await mount()
    await click('Show solution')
    await confirm()
    expect(labels()).toEqual(['Solution', 'Answer'])
    expect(lines()).toHaveLength(3)
    expect(lines().some((line) => line.querySelector('.katex-display'))).toBe(false)
    expect(lines()[1].querySelector('.katex')).not.toBeNull()
    expect(container.querySelector('.solution-answer strong')?.textContent).toBe('80')
  })

  it('shows a one-line general solution as just the answer', async () => {
    reply({ ...GENERAL, solution: { format: 'general', steps: ['Carry flag (CF)'] } })
    await mount()
    await click('Show solution')
    await confirm()
    expect(labels()).toEqual(['Answer'])
    expect(container.querySelector('.solution-answer')?.textContent).toBe('Carry flag (CF)')
  })

  it('renders general Markdown without raw HTML', async () => {
    reply({ ...GENERAL, solution: { format: 'general', steps: ['<img src=x onerror=alert(1)>', 'x'] } })
    await mount()
    await click('Show solution')
    await confirm()
    expect(container.querySelector('.solution-steps img')).toBeNull()
  })

  it('hides and shows again without asking or fetching again', async () => {
    reply(PHYSICS)
    await mount()
    await click('Show solution')
    await confirm()
    await click('Hide solution')
    expect(container.querySelector('.solution-steps')).toBeNull()
    await click('Show solution')
    expect(container.querySelector('dialog')).toBeNull()
    expect(container.querySelector('.solution-steps')).not.toBeNull()
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('labels a solution that does not match the stored answer', async () => {
    reply({ ...PHYSICS, matches: false })
    await mount()
    await click('Show solution')
    await confirm()
    expect(container.querySelector('.solution-steps .status-label')?.textContent).toBe(
      "Doesn't match the stored answer"
    )
  })

  it('waits while the solution is written', async () => {
    let finish: (response: Response) => void = () => {}
    fetchMock.mockReturnValueOnce(new Promise<Response>((resolve) => (finish = resolve)))
    await mount()
    await click('Show solution')
    await confirm()
    expect(button('Writing solution...')?.disabled).toBe(true)
    await act(async () => finish(new Response(JSON.stringify(PHYSICS))))
    expect(button('Hide solution')).toBeDefined()
  })

  it('reports a failure and lets the student try again', async () => {
    reply({ detail: 'Overloaded' }, 502)
    await mount()
    await click('Show solution')
    await confirm()
    expect(container.querySelector('.answer-error')?.textContent).toBe('Overloaded')
    expect(container.querySelector('.solution-steps')).toBeNull()

    reply(PHYSICS)
    await click('Show solution')
    await confirm()
    expect(container.querySelector('.answer-error')).toBeNull()
    expect(labels()).toEqual(['Given', 'Required', 'Solution'])
  })

  it('renders model LaTeX as math, never as markup', async () => {
    reply({
      ...MATH,
      solution: { ...MATH.solution, steps: ['<img src=x onerror=alert(1)>', '\\href{javascript:alert(1)}{x}'] }
    })
    await mount()
    await click('Show solution')
    await confirm()
    expect(container.querySelector('.solution-steps img')).toBeNull()
    expect(container.querySelector('.solution-steps a')).toBeNull()
  })
})
