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
    const [start, reset] = root.querySelectorAll<HTMLButtonElement>('button')
    expect([start.textContent, reset.textContent, reset.disabled]).toEqual(['Start', 'Reset', true])
  })

  it('shows saved durations', () => {
    localStorage.setItem('kedami.pomodoro.durations', JSON.stringify({ study: 50, rest: 10 }))
    expect(render().querySelector('[role=timer]')?.textContent).toBe('50:00')
  })
})
