import { useEffect, useId, useState } from 'react'
import { ApiError, listSqlChapters, type Recommendation, recommendProblems, type SqlChapter } from '../api'

// Mirrors MIN_COUNT, MAX_COUNT, and DEFAULT_COUNT in server/kedami_server/recommend.py.
const MIN_COUNT = 1
const MAX_COUNT = 10
const DEFAULT_COUNT = 5

interface ChapterPickerProps {
  chapter: number | null
  problems: Recommendation[]
  onChange: (chapter: number | null, problems: Recommendation[]) => void
}

/** Learn a chapter: pick one chapter and a number of problems, and the server recommends them. */
export function ChapterPicker({ chapter, problems, onChange }: ChapterPickerProps) {
  const [chapters, setChapters] = useState<SqlChapter[] | null>(null)
  const [imported, setImported] = useState(true)
  const [chosen, setChosen] = useState<number>(chapter ?? 1)
  const [count, setCount] = useState(DEFAULT_COUNT)
  // How many times Recommend again was pressed for this chapter, so each set is different.
  const [round, setRound] = useState(0)
  const [available, setAvailable] = useState<number | null>(null)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const chapterId = useId()
  const countId = useId()

  useEffect(() => {
    listSqlChapters().then(
      (reply) => {
        setChapters(reply.chapters)
        setImported(reply.imported)
      },
      () => setError('Could not load the chapters.')
    )
  }, [])

  const choose = (number: number) => {
    setChosen(number)
    setRound(0)
    setAvailable(null)
    onChange(null, [])
  }

  const recommend = async () => {
    // A list for this chapter is already shown, so this is Recommend again.
    const next = chapter === chosen && problems.length > 0 ? round + 1 : 0
    setPending(true)
    setError(null)
    try {
      const reply = await recommendProblems(chosen, count, next)
      setRound(next)
      setAvailable(reply.available)
      onChange(chosen, reply.problems)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not reach the server.')
    } finally {
      setPending(false)
    }
  }

  const current = chapters?.find((c) => c.number === chosen)
  const again = chapter === chosen && problems.length > 0

  return (
    <div className="chapter-picker">
      <div className="chapter-controls">
        <label className="field" htmlFor={chapterId}>
          <span className="field-label">Chapter</span>
          <select
            id={chapterId}
            className="text-input"
            value={chosen}
            disabled={chapters === null}
            onChange={(event) => choose(Number(event.target.value))}
          >
            {(chapters ?? []).map((c) => (
              <option key={c.number} value={c.number}>
                {c.number}. {c.name} ({c.available} {c.available === 1 ? 'problem' : 'problems'})
              </option>
            ))}
          </select>
        </label>
        <label className="field" htmlFor={countId}>
          <span className="field-label">Problems</span>
          <input
            id={countId}
            className="text-input chapter-count"
            type="number"
            min={MIN_COUNT}
            max={MAX_COUNT}
            value={count}
            onChange={(event) =>
              setCount(Math.min(MAX_COUNT, Math.max(MIN_COUNT, Number(event.target.value) || MIN_COUNT)))
            }
          />
        </label>
        <button
          type="button"
          className="button"
          disabled={pending || chapters === null || current?.available === 0}
          onClick={recommend}
        >
          {again ? 'Recommend again' : 'Recommend problems'}
        </button>
      </div>
      {current?.available === 0 && current.source === 'spider' && (
        <p className="muted">
          {imported
            ? 'The Spider bank has no problems for this chapter.'
            : 'Nothing to recommend yet: this chapter recommends Spider exercises, and none are imported.'}
        </p>
      )}
      {available !== null && available < count && problems.length > 0 && (
        <p className="muted">
          This chapter has {available} {available === 1 ? 'problem' : 'problems'}.
        </p>
      )}
      {error && <p className="answer-error">{error}</p>}
      {problems.length > 0 && (
        <ol className="recommended-list">
          {problems.map((problem, index) => (
            <li key={`${problem.source}:${problem.id}`} className="file-row recommended-row">
              <span>{problem.text}</span>
              <span className="muted">{problem.database ?? 'Solved on pgexercises'}</span>
              <button
                type="button"
                className="link-button"
                onClick={() => onChange(chapter, problems.filter((_, i) => i !== index))}
              >
                Remove
              </button>
            </li>
          ))}
        </ol>
      )}
      <p className="muted">
        Explanations come from the book Structured Query Language (Wikibooks), and examples use its people database.
      </p>
    </div>
  )
}
