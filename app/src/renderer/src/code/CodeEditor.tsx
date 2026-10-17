// The workspace's Python editor: CodeMirror, styled from the design tokens like Python code blocks.

import { defaultKeymap, history, historyKeymap } from '@codemirror/commands'
import { python } from '@codemirror/lang-python'
import { SQLite, sql } from '@codemirror/lang-sql'
import { HighlightStyle, indentOnInput, indentUnit, syntaxHighlighting } from '@codemirror/language'
import { EditorState } from '@codemirror/state'
import { drawSelection, EditorView, keymap, lineNumbers } from '@codemirror/view'
import { tags } from '@lezer/highlight'
import { useEffect, useRef } from 'react'

const INDENT = '    '

// Neutral, as Python code blocks are: keywords in medium weight, strings and comments muted.
const highlight = HighlightStyle.define([
  { tag: tags.keyword, fontWeight: '500' },
  { tag: [tags.string, tags.special(tags.string)], color: 'var(--text-muted)' },
  { tag: tags.comment, color: 'var(--text-muted)', fontStyle: 'italic' }
])

const theme = EditorView.theme(
  {
    '&': { height: '100%', backgroundColor: 'var(--surface-raised)', color: 'var(--text)', fontSize: '14px' },
    '&.cm-focused': { outline: 'none' },
    '.cm-scroller': { fontFamily: "'JetBrains Mono', monospace", fontVariantLigatures: 'none', lineHeight: '1.6' },
    '.cm-content': { caretColor: 'var(--text)', padding: '8px 0' },
    '.cm-cursor': { borderLeftColor: 'var(--text)' },
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

interface CodeEditorProps {
  value: string
  onChange: (value: string) => void
  label: string
  language?: 'python' | 'sql'
}

export function CodeEditor({ value, onChange, label, language = 'python' }: CodeEditorProps) {
  const host = useRef<HTMLDivElement>(null)
  const view = useRef<EditorView | null>(null)
  const changed = useRef(onChange)
  changed.current = onChange

  useEffect(() => {
    if (!host.current) return
    const editor = new EditorView({
      parent: host.current,
      state: EditorState.create({
        doc: value,
        extensions: [
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
            if (update.docChanged) changed.current(update.state.doc.toString())
          })
        ]
      })
    })
    view.current = editor
    return () => {
      editor.destroy()
      view.current = null
    }
    // The editor is made once; later values arrive through the effect below.
  }, [])

  // A value set from outside, such as Reset, replaces the text.
  useEffect(() => {
    const editor = view.current
    if (editor && editor.state.doc.toString() !== value) {
      editor.dispatch({ changes: { from: 0, to: editor.state.doc.length, insert: value } })
    }
  }, [value])

  return <div ref={host} className="code-editor" />
}
