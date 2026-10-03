import { renderToString } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { Markdown } from './Markdown'

function render(source: string): HTMLElement {
  const root = document.createElement('div')
  root.innerHTML = renderToString(<Markdown>{source}</Markdown>)
  return root
}

describe('Markdown', () => {
  it('renders tables with math in the cells', () => {
    const root = render('| Quadrant | $A_x$ |\n|---|---|\n| 1st | $+$ |\n| 2nd | $-$ |')
    expect([...root.querySelectorAll('th')].map((th) => th.textContent?.includes('Quadrant'))).toEqual([true, false])
    expect(root.querySelectorAll('tbody tr')).toHaveLength(2)
    expect(root.querySelectorAll('td .katex')).toHaveLength(2)
  })

  it('renders vector arrows', () => {
    expect(render('$\\vec{A}$').querySelector('.katex .accent svg')).not.toBeNull()
  })
})
