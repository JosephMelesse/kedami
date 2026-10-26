import { createContext, type ReactNode, useCallback, useContext, useEffect, useState } from 'react'
import { getSelection, saveSelection, type Selection } from '../../api'

// Selecting a block or section points Claude Code at it: it asks the server what is selected when the student
// refers to "this" in the Terminal panel. See architecture/agent-mode.md, Selecting a block.

/** A section, or a block, of the lesson on screen. */
export type Target = { sectionId: string; blockId?: never } | { blockId: string; sectionId?: never }

interface SelectionState {
  isSelected: (target: Target) => boolean
  toggle: (target: Target) => void
}

const SelectionContext = createContext<SelectionState | null>(null)

/** Holds the app's one selection for a lesson screen. Without it, as in tests, nothing can be selected. */
export function SelectionProvider({ lessonId, children }: { lessonId: string; children: ReactNode }) {
  const [selected, setSelected] = useState<Selection | null>(null)

  useEffect(() => {
    let current = true
    getSelection().then(
      (selection) => current && setSelected(selection),
      () => {}
    )
    return () => {
      current = false
    }
  }, [])

  const isSelected = useCallback(
    (target: Target) =>
      selected?.lesson_id === lessonId &&
      selected.section_id === (target.sectionId ?? null) &&
      selected.block_id === (target.blockId ?? null),
    [selected, lessonId]
  )

  const toggle = useCallback(
    (target: Target) => {
      const next = isSelected(target)
        ? null
        : { lesson_id: lessonId, section_id: target.sectionId ?? null, block_id: target.blockId ?? null }
      // Shown at once; the server's answer replaces it, and a failure puts back what it holds.
      setSelected(next)
      saveSelection(next).then(setSelected, () => getSelection().then(setSelected, () => {}))
    },
    [isSelected, lessonId]
  )

  return <SelectionContext.Provider value={{ isSelected, toggle }}>{children}</SelectionContext.Provider>
}

/** Whether a target is selected, for its border. False without a provider. */
export function useIsSelected(target: Target): boolean {
  return useContext(SelectionContext)?.isSelected(target) ?? false
}

/** The Select control: shown on hover and focus, and kept showing "Selected" while it is. */
export function SelectControl({ target, name }: { target: Target; name: string }) {
  const state = useContext(SelectionContext)
  if (!state) return null
  const selected = state.isSelected(target)
  return (
    <button
      type="button"
      className="select-control"
      aria-pressed={selected}
      aria-label={selected ? `Clear the selection of ${name}` : `Select ${name} for Claude Code`}
      onClick={() => state.toggle(target)}
    >
      {selected ? 'Selected' : 'Select'}
    </button>
  )
}
