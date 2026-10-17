// The workspace editor: CodeMirror, in Python or SQL, colored from the syntax tokens like code blocks in
// lessons, with Vim motions when turned on. See Workspace in architecture/code-problems.md.

import { defaultKeymap, history, historyKeymap } from '@codemirror/commands'
import { python } from '@codemirror/lang-python'
import { SQLite, sql } from '@codemirror/lang-sql'
import { HighlightStyle, indentOnInput, indentUnit, syntaxHighlighting } from '@codemirror/language'
import { Compartment, EditorState } from '@codemirror/state'
import { drawSelection, EditorView, keymap, lineNumbers } from '@codemirror/view'
import { tags } from '@lezer/highlight'
import { getCM, Vim, vim } from '@replit/codemirror-vim'
import { useEffect, useRef } from 'react'

const INDENT = '    '

// The same colors as code blocks in lessons; see Consistency in architecture/ui.md.
export const highlight = HighlightStyle.define([
  {
    tag: [tags.keyword, tags.controlKeyword, tags.operatorKeyword, tags.definitionKeyword, tags.moduleKeyword, tags.self],
    color: 'var(--syntax-keyword)'
  },
  { tag: [tags.string, tags.special(tags.string), tags.docString], color: 'var(--syntax-string)' },
  { tag: [tags.number, tags.bool, tags.null, tags.atom], color: 'var(--syntax-number)' },
  {
    tag: [
      tags.function(tags.variableName),
      tags.function(tags.definition(tags.variableName)),
      tags.definition(tags.className),
      tags.className,
      tags.standard(tags.variableName),
      tags.typeName
    ],
    color: 'var(--syntax-name)'
  },
  { tag: [tags.comment, tags.lineComment, tags.blockComment], color: 'var(--text-muted)', fontStyle: 'italic' }
])

const theme = EditorView.theme(
  {
    '&': { height: '100%', backgroundColor: 'var(--surface-raised)', color: 'var(--text)', fontSize: '14px' },
    '&.cm-focused': { outline: 'none' },
    '.cm-scroller': { fontFamily: "'JetBrains Mono', monospace", fontVariantLigatures: 'none', lineHeight: '1.6' },
    '.cm-content': { caretColor: 'var(--text)', padding: '8px 0' },
    '.cm-cursor': { borderLeftColor: 'var(--text)' },
    // Vim's normal-mode block cursor. The Vim extension colors it a fixed red at its highest precedence, which
    // would read as feedback, so these select it more closely to win.
    '& .cm-vimCursorLayer .cm-fat-cursor': { background: 'var(--text-muted)', color: 'var(--surface-raised)' },
    '&:not(.cm-focused) .cm-vimCursorLayer .cm-fat-cursor': {
      background: 'none',
      outline: '1px solid var(--text-muted)'
    },
    '.cm-gutters': { backgroundColor: 'var(--surface-raised)', color: 'var(--text-muted)', border: 'none' },
    '.cm-activeLineGutter': { backgroundColor: 'transparent', color: 'var(--text)' },
    '&.cm-focused .cm-selectionBackground, .cm-selectionBackground': { backgroundColor: 'var(--border)' }
  },
  { dark: true }
)

/** Tab inserts four spaces, or indents the selected lines. */
const tabKeys = keymap.of([
  {
    key: 'Tab',
    run: (view) => {
      const { state } = view
      if (state.selection.ranges.some((range) => !range.empty)) return false
      view.dispatch(state.replaceSelection(INDENT))
      return true
    }
  }
])

// `:w` saves at once. Vim's ex commands are shared by every editor, so each finds its own save here.
const saves = new WeakMap<EditorView, () => void>()
Vim.defineEx('write', 'w', (cm: { cm6: EditorView }) => saves.get(cm.cm6)?.())

/** How the editor bar shows a Vim mode, such as "-- INSERT --". */
export function vimModeLabel(mode: string, subMode?: string): string {
  const name = mode === 'visual' && subMode ? `visual ${subMode === 'linewise' ? 'line' : 'block'}` : mode
  return `-- ${name.toUpperCase()} --`
}

interface CodeEditorProps {
  value: string
  onChange: (value: string) => void
  label: string
  language?: 'python' | 'sql'
  /** Vim motions, with the mode reported to `onVimMode` and `:w` calling `onSave`. */
  vimMode?: boolean
  onVimMode?: (label: string | null) => void
  onSave?: () => void
}

export function CodeEditor({
  value,
  onChange,
  label,
  language = 'python',
  vimMode = false,
  onVimMode,
  onSave
}: CodeEditorProps) {
  const host = useRef<HTMLDivElement>(null)
  const view = useRef<EditorView | null>(null)
  const vimSlot = useRef(new Compartment())
  const callbacks = useRef({ onChange, onVimMode, onSave })
  callbacks.current = { onChange, onVimMode, onSave }

  useEffect(() => {
    if (!host.current) return
    const editor = new EditorView({
      parent: host.current,
      state: EditorState.create({
        doc: value,
        extensions: [
          // Vim goes first, so its keys come before the editor's own.
          vimSlot.current.of([]),
          lineNumbers(),
          history(),
          drawSelection(),
          indentOnInput(),
          indentUnit.of(INDENT),
          EditorState.tabSize.of(4),
          // Queries are often one long line, so SQL wraps; Python keeps its lines as written.
          ...(language === 'sql' ? [sql({ dialect: SQLite }), EditorView.lineWrapping] : [python()]),
          syntaxHighlighting(highlight),
          theme,
          tabKeys,
          keymap.of([...defaultKeymap, ...historyKeymap]),
          EditorView.contentAttributes.of({ 'aria-label': label }),
          EditorView.updateListener.of((update) => {
            if (update.docChanged) callbacks.current.onChange(update.state.doc.toString())
          })
        ]
      })
    })
    view.current = editor
    saves.set(editor, () => callbacks.current.onSave?.())
    return () => {
      editor.destroy()
      view.current = null
    }
    // The editor is made once; later values and Vim arrive through the effects below.
  }, [])

  // A value set from outside, such as Reset, replaces the text.
  useEffect(() => {
    const editor = view.current
    if (editor && editor.state.doc.toString() !== value) {
      editor.dispatch({ changes: { from: 0, to: editor.state.doc.length, insert: value } })
    }
  }, [value])

  useEffect(() => {
    const editor = view.current
    if (!editor) return
    editor.dispatch({ effects: vimSlot.current.reconfigure(vimMode ? vim() : []) })
    if (!vimMode) {
      callbacks.current.onVimMode?.(null)
      return
    }
    callbacks.current.onVimMode?.(vimModeLabel('normal'))
    const cm = getCM(editor)
    const report = (event: { mode: string; subMode?: string }) =>
      callbacks.current.onVimMode?.(vimModeLabel(event.mode, event.subMode))
    cm?.on('vim-mode-change', report)
    return () => cm?.off('vim-mode-change', report)
  }, [vimMode])

  return <div ref={host} className="code-editor" />
}
