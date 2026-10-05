import { act } from 'react'
import { createRoot } from 'react-dom/client'
import { describe, expect, it } from 'vitest'
import { RestScreen } from './RestScreen'

describe('RestScreen', () => {
  it('shows a 404 with the time left, and stops the page scrolling while shown', async () => {
    const container = document.createElement('div')
    document.body.append(container)
    const root = createRoot(container)
    const resting = () => document.documentElement.classList.contains('resting')

    await act(async () => root.render(<RestScreen time="4:59" />))
    expect(container.querySelector('h1')?.textContent).toBe('404')
    expect(container.querySelector('p')?.textContent).toBe('You can go back to studying in 4:59')
    expect(resting()).toBe(true)

    await act(async () => root.render(<RestScreen time="4:58" />))
    expect(container.querySelector('.rest-time')?.textContent).toBe('4:58')

    await act(async () => root.unmount())
    expect(resting()).toBe(false)
    container.remove()
  })
})
