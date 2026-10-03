import { type FormEvent, useState } from 'react'
import { ApiError, createLesson } from '../api'
import type { Lesson } from '../lesson/types'

const SUBJECTS: { value: Lesson['subject']; label: string }[] = [
  { value: 'math', label: 'Math' },
  { value: 'physics', label: 'Physics' }
]

interface NewLessonProps {
  onCreated: (lessonId: string) => void
  onBack: () => void
}

// Pasted text for build step 3; file upload replaces it in step 5.
export function NewLessonScreen({ onCreated, onBack }: NewLessonProps) {
  const [subject, setSubject] = useState<Lesson['subject'] | null>(null)
  const [problemSet, setProblemSet] = useState('')
  const [reference, setReference] = useState('')
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const ready = subject !== null && problemSet.trim() !== '' && !pending

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (!ready) return
    setPending(true)
    setError(null)
    try {
      onCreated(await createLesson(subject, problemSet, reference))
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
          <p className="muted">Paste the problem set and any reference material. Kedami turns them into one lesson.</p>
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
        <label className="field">
          <span className="field-label">Problem set</span>
          <textarea
            className="text-input"
            rows={12}
            value={problemSet}
            onChange={(event) => setProblemSet(event.target.value)}
          />
        </label>
        <label className="field">
          <span className="field-label">
            Reference material <span className="muted">(optional)</span>
          </span>
          <textarea
            className="text-input"
            rows={12}
            value={reference}
            onChange={(event) => setReference(event.target.value)}
          />
        </label>
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
