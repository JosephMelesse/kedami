import { useRef } from 'react'
import { ApiError, type CheckedDatabase, checkDatabase } from '../api'
import { DATABASE_ACCEPT } from './files'

/** A picked course database and what the server found when it checked it. */
export interface DatabaseChoice {
  file: File
  check: { state: 'checking' } | { state: 'ok'; database: CheckedDatabase } | { state: 'refused'; reason: string }
}

/** Checks a database file as soon as it is picked; `onChange` is called when the check starts and when it ends. */
export async function pickDatabase(file: File, onChange: (choice: DatabaseChoice) => void): Promise<void> {
  onChange({ file, check: { state: 'checking' } })
  try {
    onChange({
      file,
      check: { state: 'ok', database: await checkDatabase(file) }
    })
  } catch (err) {
    const reason = err instanceof ApiError ? err.message : 'Could not reach the server.'
    onChange({ file, check: { state: 'refused', reason } })
  }
}

interface DatabaseSlotProps {
  choice: DatabaseChoice | null
  onPick: (file: File) => void
  onRemove: () => void
}

/** The Course database slot of an uploaded SQL problem set. */
export function DatabaseSlot({ choice, onPick, onRemove }: DatabaseSlotProps) {
  const input = useRef<HTMLInputElement>(null)
  return (
    <div className="field database-slot">
      <span className="field-label">Course database</span>
      {choice ? (
        <div className="file-row database-row">
          <span className="file-name">{choice.file.name}</span>
          {choice.check.state === 'checking' && <span className="muted">Checking...</span>}
          {choice.check.state === 'ok' && (
            <span className="muted">
              {choice.check.database.tables
                .map((t) => `${t.name} (${t.count} ${t.count === 1 ? 'row' : 'rows'})`)
                .join(', ')}
            </span>
          )}
          {choice.check.state === 'refused' && <span className="answer-error">{choice.check.reason}</span>}
          <button type="button" className="link-button" onClick={onRemove}>
            Remove
          </button>
        </div>
      ) : (
        <div>
          <button type="button" className="button" onClick={() => input.current?.click()}>
            Choose
          </button>
        </div>
      )}
      <input
        ref={input}
        type="file"
        accept={DATABASE_ACCEPT}
        hidden
        aria-label="Course database"
        onChange={(event) => {
          const file = event.target.files?.[0]
          if (file) onPick(file)
          event.target.value = ''
        }}
      />
      <p className="muted">
        Homework queries are checked against it. Without it, they are self checks. Practice comes from Spider either
        way.
      </p>
    </div>
  )
}
