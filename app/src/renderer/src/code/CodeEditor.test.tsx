import { EditorView } from '@codemirror/view'
import { tags } from '@lezer/highlight'
import { getCM, Vim } from '@replit/codemirror-vim'
import { act, useState } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { CodeEditor, highlight, vimModeLabel } from './CodeEditor'
import { useVimSetting } from './useVimSetting'

// jsdom doesn't lay text out, so CodeMirror's line measuring, which Vim's motions use, gets empty boxes.
Range.prototype.getClientRects ??= () => [] as unknown as DOMRectList
Range.prototype.getBoundingClientRect ??= () => new DOMRect()

let container: HTMLDivElement
let root: Root
let modes: (string | null)[]
let saved: string[]
let setVim: (on: boolean) => void

function Editor({ name, vim, initial = 'x = 1\ny = 2\n' }: { name: string; vim: boolean; initial?: string }) {
  const [on, setOn] = useState(vim)
  setVim = setOn
  return (
    <CodeEditor
      value={initial}
      onChange={() => {}}
      label={name}
      vimMode={on}
      onVimMode={(mode) => modes.push(mode)}
      onSave={() => saved.push(name)}
    />
  )
}

beforeEach(() => {
  container = document.createElement('div')
  document.body.append(container)
  root = createRoot(container)
  modes = []
  saved = []
  localStorage.clear()
})

afterEach(async () => {
  await act(async () => root.unmount())
  container.remove()
})

const views = () => [...container.querySelectorAll<HTMLElement>('.cm-editor')].map((e) => EditorView.findFromDOM(e)!)
const press = (view: EditorView, ...keys: string[]) =>
  act(async () => {
    for (const key of keys) Vim.handleKey(getCM(view)!, key, 'user')
  })

describe('Vim', () => {
  it('is off until turned on', async () => {
    await act(async () => root.render(<Editor name="a" vim={false} />))
    expect(getCM(views()[0])).toBeFalsy()
    expect(modes).toEqual([null])
  })

  it('reports its mode as the editor bar shows it', async () => {
    await act(async () => root.render(<Editor name="a" vim />))
    const [view] = views()
    expect(modes.at(-1)).toBe('-- NORMAL --')
    await press(view, 'i')
    expect(modes.at(-1)).toBe('-- INSERT --')
    await press(view, '<Esc>')
    expect(modes.at(-1)).toBe('-- NORMAL --')
    await press(view, 'V')
    expect(modes.at(-1)).toBe('-- VISUAL LINE --')
  })

  it('moves and edits with motions in normal mode', async () => {
    await act(async () => root.render(<Editor name="a" vim />))
    const [view] = views()
    // jsdom can't lay text out, so motions between lines aren't tested here; these need no layout.
    await press(view, 'd', 'd')
    expect(view.state.doc.toString()).toBe('y = 2\n')
    await press(view, 'u')
    expect(view.state.doc.toString()).toBe('x = 1\ny = 2\n')
  })

  it('saves the editor it was typed in with :w', async () => {
    await act(async () =>
      root.render(
        <>
          <Editor name="first" vim />
          <Editor name="second" vim />
        </>
      )
    )
    const [, second] = views()
    // Typed ':' opens Vim's prompt, which jsdom can't type into, so the command runs as typing it would.
    await act(async () => Vim.handleEx(getCM(second)! as Parameters<typeof Vim.handleEx>[0], 'w'))
    expect(saved).toEqual(['second'])
  })

  it('turns off again', async () => {
    await act(async () => root.render(<Editor name="a" vim />))
    await act(async () => setVim(false))
    expect(modes.at(-1)).toBeNull()
  })
})

describe('the Vim setting', () => {
  function Setting() {
    const [on, setOn] = useVimSetting()
    return (
      <button type="button" onClick={() => setOn(!on)}>
        {on ? 'on' : 'off'}
      </button>
    )
  }

  it('is kept on this machine', async () => {
    await act(async () => root.render(<Setting />))
    expect(container.textContent).toBe('off')
    await act(async () => container.querySelector('button')!.click())
    expect(localStorage.getItem('kedami.editor.vim')).toBe('on')
    await act(async () => root.unmount())
    root = createRoot(container)
    await act(async () => root.render(<Setting />))
    expect(container.textContent).toBe('on')
  })
})

describe('mode labels', () => {
  it.each([
    ['normal', undefined, '-- NORMAL --'],
    ['insert', undefined, '-- INSERT --'],
    ['visual', undefined, '-- VISUAL --'],
    ['visual', 'linewise', '-- VISUAL LINE --'],
    ['visual', 'blockwise', '-- VISUAL BLOCK --'],
    ['replace', undefined, '-- REPLACE --']
  ])('%s %s is %s', (mode, subMode, label) => {
    expect(vimModeLabel(mode, subMode)).toBe(label)
  })
})

describe('colors', () => {
  const colorOf = (tag: unknown) => highlight.specs.find((spec) => [spec.tag].flat().includes(tag as never))?.color

  it('colors code from the syntax tokens, as lesson code blocks are', () => {
    expect(colorOf(tags.keyword)).toBe('var(--syntax-keyword)')
    expect(colorOf(tags.string)).toBe('var(--syntax-string)')
    expect(colorOf(tags.number)).toBe('var(--syntax-number)')
    expect(colorOf(tags.bool)).toBe('var(--syntax-number)')
    expect(colorOf(tags.typeName)).toBe('var(--syntax-name)')
    expect(colorOf(tags.comment)).toBe('var(--text-muted)')
  })
})
