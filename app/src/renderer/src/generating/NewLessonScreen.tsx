import { type DragEvent, type FormEvent, useRef, useState } from 'react'
import { ApiError, createLesson, type MaterialRole, type NewFile, type Recommendation } from '../api'
import type { Lesson } from '../lesson/types'
import { SUBJECT_LABELS } from '../subjects'
import { ChapterPicker } from './ChapterPicker'
import { type DatabaseChoice, DatabaseSlot, pickDatabase } from './DatabaseSlot'
import { ACCEPT, canForce, DATABASE_ACCEPT, isDatabaseFile, kindOf } from './files'
import { type Pick, problemList } from './picks'
import { ProblemPicker } from './ProblemPicker'
import { recommendedList } from './recommended'

const SUBJECTS = Object.entries(SUBJECT_LABELS).map(([value, label]) => ({ value: value as Lesson['subject'], label }))

// Computer science domains, which decide how a lesson is built.
const DOMAINS: { value: NonNullable<Lesson['domain']>; label: string }[] = [
  { value: 'dsa', label: 'Data structures and algorithms' },
  { value: 'sql', label: 'SQL' }
]

interface NewLessonProps {
  /** The folder the lesson starts in, or null for the home page. */
  folderId: number | null
  onCreated: (lessonId: string) => void
  onBack: () => void
}

export function NewLessonScreen({ folderId, onCreated, onBack }: NewLessonProps) {
  const [subject, setSubject] = useState<Lesson['subject'] | null>(null)
  const [domain, setDomain] = useState<Lesson['domain']>(null)
  const [picks, setPicks] = useState<Pick[]>([])
  // A SQL lesson learns a chapter, by default, or takes an uploaded problem set.
  const [sqlHow, setSqlHow] = useState<'chapter' | 'upload'>('chapter')
  const [chapter, setChapter] = useState<number | null>(null)
  const [recommended, setRecommended] = useState<Recommendation[]>([])
  const [database, setDatabase] = useState<DatabaseChoice | null>(null)
  // The database file last picked, so a check that ends after another pick or a removal is ignored.
  const databaseFile = useRef<File | null>(null)
  const [files, setFiles] = useState<NewFile[]>([])
  const [rejected, setRejected] = useState<string[]>([])
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const hasProblemSet = files.some((f) => f.role === 'problem_set')
  // A DSA lesson's problem set is the picked problems, so its files are reference material.
  const dsa = subject === 'computer_science' && domain === 'dsa'
  const sql = subject === 'computer_science' && domain === 'sql'
  const learnChapter = sql && sqlHow === 'chapter'
  // An uploaded SQL problem set can take its course's database, in a slot of its own.
  const takesDatabase = sql && sqlHow === 'upload'
  const databaseReady = !takesDatabase || database === null || database.check.state === 'ok'
  const hasProblems = dsa ? picks.length > 0 : learnChapter ? chapter !== null && recommended.length > 0 : hasProblemSet
  const ready = subject !== null && hasProblems && databaseReady && !pending

  const chooseSubject = (value: Lesson['subject']) => {
    setSubject(value)
    // DSA is chosen until the student picks another domain.
    setDomain(value === 'computer_science' ? 'dsa' : null)
  }

  const chooseDatabase = (file: File) => {
    databaseFile.current = file
    pickDatabase(file, (choice) => {
      if (databaseFile.current === choice.file) setDatabase(choice)
    })
  }

  const removeDatabase = () => {
    databaseFile.current = null
    setDatabase(null)
  }

  const add = (list: FileList | null) => {
    if (!list) return
    const incoming = [...list]
    // A database file dropped among the material moves to the database slot.
    const dropped = takesDatabase ? incoming.filter((f) => isDatabaseFile(f.name)) : []
    if (dropped.length > 0) chooseDatabase(dropped[dropped.length - 1])
    const material = incoming.filter((f) => !dropped.includes(f))
    setRejected(material.filter((f) => kindOf(f.name) === null).map((f) => f.name))
    setFiles((current) => {
      let problemSet = current.some((f) => f.role === 'problem_set')
      const added = material
        .filter((f) => kindOf(f.name) !== null)
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
    let sent: NewFile[] = files
    if (dsa) {
      const problems = new File([problemList(picks)], 'problems.md', { type: 'text/markdown' })
      sent = [{ file: problems, role: 'problem_set', force: false }, ...files.map((f) => ({ ...f, role: 'reference' as const }))]
    } else if (learnChapter) {
      // Nothing is uploaded: the server adds the chapter's pages of the book and its example database.
      const problems = new File([recommendedList(recommended)], 'problems.md', { type: 'text/markdown' })
      sent = [{ file: problems, role: 'problem_set', force: false }]
    } else if (takesDatabase && database) {
      sent = [...files, { file: database.file, role: 'database', force: false }]
    }
    try {
      onCreated(await createLesson(subject, sent, folderId, domain, learnChapter ? chapter : null))
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
            {dsa
              ? 'Pick the LeetCode problems and add any reference material. Kedami turns them into one lesson.'
              : learnChapter
                ? 'Pick a chapter and its problems. Kedami turns them into one lesson.'
                : 'Add the problem set and any reference material. Kedami turns them into one lesson.'}
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
                  onChange={() => chooseSubject(option.value)}
                />
                {option.label}
              </label>
            ))}
          </div>
        </fieldset>
        {subject === 'computer_science' && (
          <fieldset className="field">
            <legend className="field-label">Domain</legend>
            <div className="subject-options">
              {DOMAINS.map((option) => (
                <label key={option.value} className="option">
                  <input
                    type="radio"
                    name="domain"
                    checked={domain === option.value}
                    onChange={() => setDomain(option.value)}
                  />
                  {option.label}
                </label>
              ))}
            </div>
          </fieldset>
        )}
        {dsa && (
          <div className="field">
            <span className="field-label">Problems</span>
            <ProblemPicker picks={picks} onChange={setPicks} />
          </div>
        )}
        {sql && (
          <fieldset className="field">
            <legend className="field-label">How</legend>
            <div className="subject-options">
              <label className="option">
                <input type="radio" name="sql-how" checked={sqlHow === 'chapter'} onChange={() => setSqlHow('chapter')} />
                Learn a chapter
              </label>
              <label className="option">
                <input type="radio" name="sql-how" checked={sqlHow === 'upload'} onChange={() => setSqlHow('upload')} />
                Upload a problem set
              </label>
            </div>
          </fieldset>
        )}
        {learnChapter ? (
          <ChapterPicker
            chapter={chapter}
            problems={recommended}
            onChange={(number, problems) => {
              setChapter(number)
              setRecommended(problems)
            }}
          />
        ) : (
          <>
            <FileDrop
              onFiles={add}
              accept={takesDatabase ? `${ACCEPT},${DATABASE_ACCEPT}` : ACCEPT}
              label={dsa ? 'Drop reference PDFs, images, or text files here' : undefined}
            />
            {rejected.length > 0 && (
              <p className="answer-error">Not supported, so not added: {rejected.join(', ')}</p>
            )}
            {files.length > 0 && (
              <FileList
                files={files}
                referenceOnly={dsa}
                onChange={update}
                onRemove={(i) => setFiles(files.filter((_, j) => j !== i))}
              />
            )}
            {!dsa && files.length > 0 && !hasProblemSet && (
              <p className="answer-error">Tag at least one file as a problem set.</p>
            )}
            {takesDatabase && <DatabaseSlot choice={database} onPick={chooseDatabase} onRemove={removeDatabase} />}
          </>
        )}
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

interface FileDropProps {
  onFiles: (files: FileList | null) => void
  accept: string
  label?: string
}

function FileDrop({ onFiles, accept, label }: FileDropProps) {
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
      <p>{label ?? 'Drop PDFs, images, or text files here'}</p>
      <button type="button" className="button" onClick={() => input.current?.click()}>
        Choose files
      </button>
      <input
        ref={input}
        type="file"
        multiple
        accept={accept}
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
  /** Hides the role choice: every file is reference material. */
  referenceOnly?: boolean
  onChange: (index: number, change: Partial<NewFile>) => void
  onRemove: (index: number) => void
}

export function FileList({ files, referenceOnly = false, onChange, onRemove }: FileListProps) {
  return (
    <ul className="file-list">
      {files.map(({ file, role, force }, index) => (
        <li key={`${file.name}-${index}`} className="file-row">
          <span className="file-name">{file.name}</span>
          {referenceOnly ? (
            <span className="muted">Reference</span>
          ) : (
            <select
              className="text-input"
              aria-label={`Role of ${file.name}`}
              value={role}
              onChange={(event) => onChange(index, { role: event.target.value as MaterialRole })}
            >
              <option value="problem_set">Problem set</option>
              <option value="reference">Reference</option>
            </select>
          )}
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
