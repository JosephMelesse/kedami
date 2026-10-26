import { type DragEvent, type FormEvent, useEffect, useRef, useState } from 'react'
import { ApiError, createLesson, getJobs, type MaterialRole, type NewFile } from '../api'
import type { Lesson } from '../lesson/types'
import { SUBJECT_LABELS } from '../subjects'
import { ACCEPT, kindOf } from './files'

// Claude Code builds math, physics, and general lessons. See architecture/agent-mode.md.
const SUBJECTS: Lesson['subject'][] = ['math', 'physics', 'general']

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
  // Null until the server says; a lesson can't be built without Claude Code.
  const [claude, setClaude] = useState<boolean | null>(null)
  const hasProblemSet = files.some((f) => f.role === 'problem_set')
  const ready = subject !== null && hasProblemSet && !pending && claude !== false

  useEffect(() => {
    let current = true
    getJobs().then(
      (queue) => current && setClaude(queue.claude),
      () => {}
    )
    return () => {
      current = false
    }
  }, [])

  const add = (list: FileList | null) => {
    if (!list) return
    const incoming = [...list]
    setRejected(incoming.filter((f) => kindOf(f.name) === null).map((f) => f.name))
    setFiles((current) => {
      let problemSet = current.some((f) => f.role === 'problem_set')
      const added = incoming
        .filter((f) => kindOf(f.name) !== null)
        .map((file): NewFile => {
          // The first file is assumed to be the problem set; later ones, reference material.
          const role: MaterialRole = problemSet ? 'reference' : 'problem_set'
          problemSet = true
          return { file, role }
        })
      return [...current, ...added]
    })
  }

  const update = (index: number, role: MaterialRole) =>
    setFiles((current) => current.map((f, i) => (i === index ? { ...f, role } : f)))

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
            Add the problem set and any reference material. Claude Code turns them into one lesson as soon as you
            create it, on your own Claude plan.
          </p>
        </header>
        <fieldset className="field">
          <legend className="field-label">Subject</legend>
          <div className="subject-options">
            {SUBJECTS.map((value) => (
              <label key={value} className="option">
                <input type="radio" name="subject" checked={subject === value} onChange={() => setSubject(value)} />
                {SUBJECT_LABELS[value]}
              </label>
            ))}
          </div>
        </fieldset>
        <FileDrop onFiles={add} />
        {rejected.length > 0 && <p className="answer-error">Not supported, so not added: {rejected.join(', ')}</p>}
        {files.length > 0 && (
          <FileList files={files} onChange={update} onRemove={(i) => setFiles(files.filter((_, j) => j !== i))} />
        )}
        {files.length > 0 && !hasProblemSet && <p className="answer-error">Tag at least one file as a problem set.</p>}
        {error && <p className="answer-error">{error}</p>}
        {claude === false && (
          <p className="answer-error">
            Claude Code isn't installed. Install it from code.claude.com and log in once in the Terminal panel, then
            open this screen again.
          </p>
        )}
        <div className="answer-actions">
          <button type="submit" className="button button-primary" disabled={!ready}>
            Create lesson
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
  onChange: (index: number, role: MaterialRole) => void
  onRemove: (index: number) => void
}

function FileList({ files, onChange, onRemove }: FileListProps) {
  return (
    <ul className="file-list">
      {files.map(({ file, role }, index) => (
        <li key={`${file.name}-${index}`} className="file-row">
          <span className="file-name">{file.name}</span>
          <select
            className="text-input"
            aria-label={`Role of ${file.name}`}
            value={role}
            onChange={(event) => onChange(index, event.target.value as MaterialRole)}
          >
            <option value="problem_set">Problem set</option>
            <option value="reference">Reference</option>
          </select>
          <button type="button" className="link-button" onClick={() => onRemove(index)}>
            Remove
          </button>
        </li>
      ))}
    </ul>
  )
}
