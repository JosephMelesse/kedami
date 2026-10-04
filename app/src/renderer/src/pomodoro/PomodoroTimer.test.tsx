import { act } from 'react'
import { createRoot } from 'react-dom/client'
import { renderToString } from 'react-dom/server'
import { beforeEach, describe, expect, it } from 'vitest'
import { PomodoroTimer } from './PomodoroTimer'

function render(): HTMLElement {
  const root = document.createElement('div')
  root.innerHTML = renderToString(<PomodoroTimer />)
  return root
}

describe('PomodoroTimer', () => {
  beforeEach(() => localStorage.clear())

  it('starts reset, with editable durations and the full study time', () => {
    const root = render()
    const inputs = [...root.querySelectorAll<HTMLInputElement>('input')]
    expect(inputs.map((i) => [i.getAttribute('aria-label'), i.value])).toEqual([
      ['Study minutes', '25'],
      ['Rest minutes', '5']
    ])
    expect(root.querySelector('[role=timer]')?.textContent).toBe('25:00')
    const [start, reset] = root.querySelectorAll<HTMLButtonElement>('.pomodoro-controls button')
    expect([start.textContent, reset.textContent, reset.disabled]).toEqual(['Start', 'Reset', true])
  })

  it('shows saved durations', () => {
    localStorage.setItem('kedami.pomodoro.durations', JSON.stringify({ study: 50, rest: 10 }))
    expect(render().querySelector('[role=timer]')?.textContent).toBe('50:00')
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
})
