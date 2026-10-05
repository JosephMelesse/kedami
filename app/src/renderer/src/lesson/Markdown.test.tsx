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

  it('shows code in other languages as typed, without highlighting', () => {
    const code = render('```asm\nmov eax, 5\nadd eax, ebx\n```').querySelector('pre code')
    expect(code?.textContent).toBe('mov eax, 5\nadd eax, ebx\n')
    expect(code?.querySelector('span')).toBeNull()
  })

  it('still highlights Python', () => {
    expect(render('```python\ndef f():\n    return 1\n```').querySelector('pre code .hljs-keyword')).not.toBeNull()
  })
})
