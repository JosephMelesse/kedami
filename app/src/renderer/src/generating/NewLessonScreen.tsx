import { type DragEvent, type FormEvent, useRef, useState } from 'react'
import { ApiError, createLesson, type MaterialRole, type NewFile } from '../api'
import type { Lesson } from '../lesson/types'
import { SUBJECT_LABELS } from '../subjects'
import { ACCEPT, canForce, kindOf } from './files'

const SUBJECTS = Object.entries(SUBJECT_LABELS).map(([value, label]) => ({ value: value as Lesson['subject'], label }))

interface NewLessonProps {
  /** The folder the lesson starts in, or null for the home page. */
  folderId: number | null
  onCreated: (lessonId: string) => void
  onBack: () => void
}

export function NewLessonScreen({ folderId, onCreated, onBack }: NewLessonProps) {
  const [subject, setSubject] = useState<Lesson['subject'] | null>(null)
  const [files, setFiles] = useState<NewFile[]>([])
  const [rejected, setRejected] = useState<string[]>([])
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const hasProblemSet = files.some((f) => f.role === 'problem_set')
  const ready = subject !== null && hasProblemSet && !pending

  const add = (list: FileList | null) => {
    if (!list) return
    const incoming = [...list]
    setRejected(incoming.filter((f) => !kindOf(f.name)).map((f) => f.name))
    setFiles((current) => {
      let problemSet = current.some((f) => f.role === 'problem_set')
      const added = incoming
        .filter((f) => kindOf(f.name))
        .map((file): NewFile => {
          // The first file is assumed to be the problem set; later ones, reference material.
          const role: MaterialRole = problemSet ? 'reference' : 'problem_set'
          problemSet = true
          return { file, role, force: false }
        })
      return [...current, ...added]
    })
  }

  const update = (index: number, change: Partial<NewFile>) =>
    setFiles((current) => current.map((f, i) => (i === index ? { ...f, ...change } : f)))

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (!ready) return
    setPending(true)
    setError(null)
    try {
      onCreated(await createLesson(subject, files, folderId))
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not reach the server.')
      setPending(false)
    }
  }

  return (
    <>
      <nav className="screen-nav">
        <button type="button" className="link-button" onClick={onBack}>
          Library
        </button>
      </nav>
      <form className="form-screen" onSubmit={submit}>
        <header className="lesson-header">
          <h1>New lesson</h1>
          <p className="muted">
            Add the problem set and any reference material. Kedami turns them into one lesson.
          </p>
        </header>
        <fieldset className="field">
          <legend className="field-label">Subject</legend>
          <div className="subject-options">
            {SUBJECTS.map((option) => (
              <label key={option.value} className="option">
                <input
                  type="radio"
                  name="subject"
                  checked={subject === option.value}
                  onChange={() => setSubject(option.value)}
                />
                {option.label}
              </label>
            ))}
          </div>
        </fieldset>
        {subject === 'computer_science' && (
          <p className="muted">
            For the problem set, list the LeetCode problems one per line with number and title, such as
            &quot;1. Two Sum&quot;. You solve them on LeetCode and mark them done here.
          </p>
        )}
        <FileDrop onFiles={add} />
        {rejected.length > 0 && (
          <p className="answer-error">Not supported, so not added: {rejected.join(', ')}</p>
        )}
        {files.length > 0 && <FileList files={files} onChange={update} onRemove={(i) => setFiles(files.filter((_, j) => j !== i))} />}
        {files.length > 0 && !hasProblemSet && <p className="answer-error">Tag at least one file as a problem set.</p>}
        {error && <p className="answer-error">{error}</p>}
        <div className="answer-actions">
          <button type="submit" className="button button-primary" disabled={!ready}>
            Generate lesson
          </button>
        </div>
      </form>
    </>
  )
}

function FileDrop({ onFiles }: { onFiles: (files: FileList | null) => void }) {
  const input = useRef<HTMLInputElement>(null)
  const [over, setOver] = useState(false)
  const drop = (event: DragEvent) => {
    event.preventDefault()
    setOver(false)
    onFiles(event.dataTransfer.files)
  }
  return (
    <div
      className="file-drop"
      data-over={over}
      onDragOver={(event) => {
        event.preventDefault()
        setOver(true)
      }}
      onDragLeave={() => setOver(false)}
      onDrop={drop}
    >
      <p>Drop PDFs, images, or text files here</p>
      <button type="button" className="button" onClick={() => input.current?.click()}>
        Choose files
      </button>
      <input
        ref={input}
        type="file"
        multiple
        accept={ACCEPT}
        hidden
        onChange={(event) => {
          onFiles(event.target.files)
          event.target.value = ''
        }}
      />
    </div>
  )
}

interface FileListProps {
  files: NewFile[]
  onChange: (index: number, change: Partial<NewFile>) => void
  onRemove: (index: number) => void
}

export function FileList({ files, onChange, onRemove }: FileListProps) {
  return (
    <ul className="file-list">
      {files.map(({ file, role, force }, index) => (
        <li key={`${file.name}-${index}`} className="file-row">
          <span className="file-name">{file.name}</span>
          <select
            className="text-input"
            aria-label={`Role of ${file.name}`}
            value={role}
            onChange={(event) => onChange(index, { role: event.target.value as MaterialRole })}
          >
            <option value="problem_set">Problem set</option>
            <option value="reference">Reference</option>
          </select>
          <label className="option" title={canForce(file.name) ? undefined : 'Text files are read as they are'}>
            <input
              type="checkbox"
              checked={force && canForce(file.name)}
              disabled={!canForce(file.name)}
              onChange={(event) => onChange(index, { force: event.target.checked })}
            />
            Force transcription
          </label>
          <button type="button" className="link-button" onClick={() => onRemove(index)}>
            Remove
          </button>
        </li>
      ))}
    </ul>
  )
}
