import { type FormEvent, useEffect, useRef, useState } from 'react'
import { ApiError, type ListProblem, parsePlaceholderList, type PlannedLesson } from '../api'
import { DueLabel } from './DueLabel'

interface PlaceholderDialogProps {
  /** Creates them, all or none. Resolves to an error message to show, or null when done. */
  onCreate: (planned: PlannedLesson[]) => Promise<string | null>
  onCancel: () => void
}

/** Plans one lesson, or a pasted list of them. Mount it to open it. See Placeholder lessons in architecture/ui.md. */
export function PlaceholderDialog({ onCreate, onCancel }: PlaceholderDialogProps) {
  const ref = useRef<HTMLDialogElement>(null)
  const [pasting, setPasting] = useState(false)
  const [name, setName] = useState('')
  const [date, setDate] = useState('')
  const [text, setText] = useState('')
  // What Preview found in the text as it is now. Changing the text clears it, so only what was seen is created.
  const [preview, setPreview] = useState<PlannedLesson[] | null>(null)
  const [problems, setProblems] = useState<ListProblem[]>([])
  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState(false)

  useEffect(() => {
    if (ref.current && !ref.current.open) ref.current.showModal()
  }, [])

  const create = async (planned: PlannedLesson[]) => {
    if (pending) return
    setPending(true)
    const message = await onCreate(planned)
    setPending(false)
    setError(message)
  }

  const showPreview = async () => {
    if (pending) return
    setPending(true)
    setError(null)
    try {
      const found = await parsePlaceholderList(text)
      setPreview(found.placeholders)
      setProblems(found.problems)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not reach the server.')
    }
    setPending(false)
  }

  const submit = (event: FormEvent) => {
    event.preventDefault()
    if (pasting) {
      if (preview && preview.length > 0) create(preview)
    } else if (name.trim()) {
      create([{ name: name.trim(), due_date: date || null }])
    }
  }

  return (
    <dialog
      ref={ref}
      className="dialog"
      onCancel={(event) => {
        event.preventDefault()
        onCancel()
      }}
    >
      <form className="dialog-form" onSubmit={submit}>
        <h2>New placeholder</h2>
        {pasting ? (
          <>
            <textarea
              className="text-input"
              aria-label="List of placeholders"
              placeholder={'Week 1\nWeek 2 | 2026-12-01'}
              rows={6}
              maxLength={100_000}
              value={text}
              onChange={(event) => {
                setText(event.target.value)
                setPreview(null)
                setProblems([])
              }}
              autoFocus
            />
            {problems.length > 0 && (
              <ul className="placeholder-problems">
                {problems.map((problem, index) => (
                  <li key={index} className="answer-error">
                    {problem.line > 0 ? `Line ${problem.line}: ${problem.reason}` : problem.reason}
                  </li>
                ))}
              </ul>
            )}
            {preview && preview.length > 0 && (
              <ul className="placeholder-preview" aria-label="Placeholders to create">
                {preview.map((planned, index) => (
                  <li key={index}>
                    <span>{planned.name}</span>
                    <DueLabel date={planned.due_date} overdue={false} />
                  </li>
                ))}
              </ul>
            )}
          </>
        ) : (
          <>
            <input
              className="text-input"
              aria-label="Name"
              placeholder="Name"
              maxLength={120}
              value={name}
              onChange={(event) => setName(event.target.value)}
              autoFocus
            />
            <input
              type="date"
              className="text-input"
              aria-label="Due date (optional)"
              value={date}
              onChange={(event) => setDate(event.target.value)}
            />
          </>
        )}
        {error && <p className="answer-error">{error}</p>}
        <div className="dialog-actions">
          {!pasting && (
            <button type="button" className="button dialog-action-start" onClick={() => setPasting(true)}>
              Paste a list
            </button>
          )}
          <button type="button" className="button" onClick={onCancel}>
            Cancel
          </button>
          {pasting && (
            <button type="button" className="button" disabled={!text.trim() || pending} onClick={showPreview}>
              Preview
            </button>
          )}
          {pasting ? (
            <button type="submit" className="button button-primary" disabled={!preview?.length || pending}>
              {preview?.length ? `Create ${preview.length}` : 'Create'}
            </button>
          ) : (
            <button type="submit" className="button button-primary" disabled={!name.trim() || pending}>
              Create
            </button>
          )}
        </div>
      </form>
    </dialog>
  )
}
