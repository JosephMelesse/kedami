import { act } from 'react'
import { createRoot } from 'react-dom/client'
import { renderToString } from 'react-dom/server'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { PomodoroTimer } from './PomodoroTimer'

function render(): HTMLElement {
  const root = document.createElement('div')
  root.innerHTML = renderToString(<PomodoroTimer />)
  return root
}

describe('PomodoroTimer', () => {
  beforeEach(() => localStorage.clear())

  it('starts reset, with editable durations and only a Start button', () => {
    const root = render()
    const inputs = [...root.querySelectorAll<HTMLInputElement>('input')]
    expect(inputs.map((i) => [i.getAttribute('aria-label'), i.value])).toEqual([
      ['Study minutes', '25'],
      ['Rest minutes', '5']
    ])
    expect(root.querySelector('[role=timer]')).toBeNull()
    const buttons = [...root.querySelectorAll('.pomodoro-controls button')].map((b) => b.textContent)
    expect(buttons).toEqual(['Start'])
  })

  it('shows saved durations', () => {
    localStorage.setItem('kedami.pomodoro.durations', JSON.stringify({ study: 50, rest: 10 }))
    const root = render()
    expect([...root.querySelectorAll('input')].map((i) => i.value)).toEqual(['50', '10'])
    expect(root.querySelector('.pomodoro-toggle')?.textContent).toBe('50:00')
  })

  it('has a toggle showing the remaining time, for narrow windows', () => {
    const toggle = render().querySelector<HTMLButtonElement>('.pomodoro-toggle')!
    expect([toggle.textContent, toggle.getAttribute('aria-label')]).toEqual(['25:00', 'Pomodoro timer, 25:00'])
    expect(toggle.getAttribute('aria-expanded')).toBe('false')
  })

  it('opens the controls from the toggle and closes them on Escape or a click outside', async () => {
    const container = document.createElement('div')
    document.body.append(container)
    const root = createRoot(container)
    await act(async () => root.render(<PomodoroTimer />))
    const toggle = container.querySelector<HTMLButtonElement>('.pomodoro-toggle')!
    const controls = container.querySelector('.pomodoro-controls')!
    const isOpen = () => [toggle.getAttribute('aria-expanded'), controls.classList.contains('open')]

    await act(async () => toggle.click())
    expect(isOpen()).toEqual(['true', true])
    await act(async () =>
      controls.querySelector('input')!.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }))
    )
    expect(isOpen()).toEqual(['true', true])
    await act(async () => document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' })))
    expect(isOpen()).toEqual(['false', false])

    await act(async () => toggle.click())
    await act(async () => document.body.dispatchEvent(new MouseEvent('mousedown', { bubbles: true })))
    expect(isOpen()).toEqual(['false', false])

    await act(async () => root.unmount())
    container.remove()
  })

  describe('once started', () => {
    let container: HTMLDivElement
    let root: ReturnType<typeof createRoot>

    beforeEach(async () => {
      vi.useFakeTimers({ toFake: ['Date', 'setInterval', 'clearInterval'] })
      container = document.createElement('div')
      document.body.append(container)
      root = createRoot(container)
      await act(async () => root.render(<PomodoroTimer />))
    })

    afterEach(async () => {
      await act(async () => root.unmount())
      container.remove()
      vi.useRealTimers()
    })

    const buttons = () => [...container.querySelectorAll('button')].filter((b) => !b.matches('.pomodoro-toggle'))
    const click = (label: string) =>
      act(async () =>
        buttons()
          .find((b) => b.textContent === label)!
          .click()
      )
    const counter = () => container.querySelector<HTMLButtonElement>('.pomodoro-counter')

    it('shows only the phase and the remaining time while running', async () => {
      await click('Start')
      expect(container.querySelectorAll('input')).toHaveLength(0)
      expect(buttons()).toEqual([counter()])
      expect(counter()!.textContent).toBe('Study25:00')
      expect(counter()!.getAttribute('aria-label')).toBe('Pause timer, Study 25:00')

      await act(async () => vi.advanceTimersByTime(61_000))
      expect(container.querySelector('[role=timer]')?.textContent).toBe('23:59')
    })

    it('pauses and resumes when the counter is clicked, with Stop only while paused', async () => {
      await click('Start')
      await act(async () => vi.advanceTimersByTime(61_000))
      await act(async () => counter()!.click())

      expect(counter()!.classList.contains('paused')).toBe(true)
      expect(counter()!.textContent).toBe('Study23:59')
      expect(counter()!.getAttribute('aria-label')).toBe('Resume timer, Study 23:59')
      expect(buttons().map((b) => b.textContent)).toEqual(['Study23:59', 'Stop'])

      // Paused time stands still.
      await act(async () => vi.advanceTimersByTime(30_000))
      expect(counter()!.textContent).toBe('Study23:59')

      await act(async () => counter()!.click())
      expect(counter()!.classList.contains('paused')).toBe(false)
      expect(buttons()).toEqual([counter()])
      await act(async () => vi.advanceTimersByTime(1_000))
      expect(counter()!.textContent).toBe('Study23:58')
    })

    it('goes back to the inputs on Stop', async () => {
      await click('Start')
      await act(async () => counter()!.click())
      await click('Stop')
      expect(counter()).toBeNull()
      expect([...container.querySelectorAll('input')].map((i) => i.value)).toEqual(['25', '5'])
      expect(buttons().map((b) => b.textContent)).toEqual(['Start'])
    })

    it('moves to rest with the alarm when study ends', async () => {
      const play = vi.spyOn(HTMLMediaElement.prototype, 'play').mockResolvedValue()
      await click('Start')
      await act(async () => vi.advanceTimersByTime(25 * 60_000))
      expect(counter()!.textContent).toBe('Rest5:00')
      expect(play).toHaveBeenCalledTimes(1)
      play.mockRestore()
    })
  })
})
