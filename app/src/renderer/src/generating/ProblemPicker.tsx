// The DSA problem picker: search the imported LeetCode problems and collect them as bubbles.
// See Picking problems in architecture/code-problems.md.

import { type ClipboardEvent, type KeyboardEvent, useCallback, useEffect, useId, useRef, useState } from 'react'
import { type LeetCodeMatch, searchLeetCode } from '../api'
import { bareNumber, leetcodeSlug, numberAndTitle, type Pick, pieces } from './picks'

const SEARCH_DELAY_MS = 120

type Resolved = { pick: Pick } | { message: string } | { unresolved: string }

interface ProblemPickerProps {
  picks: Pick[]
  onChange: (picks: Pick[]) => void
  /** Searches the imported problems; tests stand in for the server. */
  search?: (query: string) => Promise<{ problems: LeetCodeMatch[]; imported: boolean }>
}

export function ProblemPicker({ picks, onChange, search: searchServer = searchLeetCode }: ProblemPickerProps) {
  const listId = useId()
  const [text, setText] = useState('')
  const [found, setFound] = useState<{ query: string; matches: LeetCodeMatch[] }>({ query: '', matches: [] })
  const [highlight, setHighlight] = useState(0)
  const [message, setMessage] = useState<string | null>(null)
  // Null until the first search says; false when nothing has been imported.
  const [imported, setImported] = useState<boolean | null>(null)
  const sequence = useRef(0)
  const search = useCallback(
    async (query: string): Promise<LeetCodeMatch[]> => {
      const result = await searchServer(query)
      setImported(result.imported)
      return result.problems
    },
    [searchServer]
  )
  // Picks made in one go, such as a paste, see each other before the parent re-renders.
  const current = useRef(picks)
  current.current = picks

  const query = text.trim()
  const matches = found.query === query ? found.matches : []

  useEffect(() => {
    const id = ++sequence.current
    if (!query) return
    const timer = setTimeout(() => {
      search(query).then(
        (result) => id === sequence.current && (setFound({ query, matches: result }), setHighlight(0)),
        () => id === sequence.current && setFound({ query, matches: [] })
      )
    }, SEARCH_DELAY_MS)
    return () => clearTimeout(timer)
  }, [query, search])

  const add = (pick: Pick): boolean => {
    if (current.current.some((p) => p.number === pick.number)) {
      setMessage(`#${pick.number} is already picked.`)
      return false
    }
    current.current = [...current.current, pick]
    onChange(current.current)
    return true
  }

  // A typed or pasted piece: a number, a number with a title, or the exact title of an imported problem.
  const resolve = async (piece: string): Promise<Resolved> => {
    const named = numberAndTitle(piece)
    const number = bareNumber(piece) ?? named?.number ?? null
    if (number !== null) {
      if (current.current.some((p) => p.number === number)) return { message: `#${number} is already picked.` }
      const match = (await search(String(number))).find((m) => m.number === number)
      if (match && named && leetcodeSlug(named.title) !== match.slug) {
        return { message: `#${number} is ${match.title}, not ${named.title}.` }
      }
      if (match) return { pick: toPick(match) }
      if (named) return { pick: { number, title: named.title, difficulty: null } }
      return {
        message: `#${number} isn't in the imported problems. Type its title after the number to solve it on LeetCode.`
      }
    }
    const exact = (await search(piece)).find((m) => m.slug === leetcodeSlug(piece))
    return exact ? { pick: toPick(exact) } : { unresolved: piece }
  }

  const choose = (match: LeetCodeMatch): void => {
    if (add(toPick(match))) {
      setText('')
      setMessage(null)
    }
  }

  // Enter, Tab, or a comma: the highlighted match, or else the text read as a number or title.
  const commit = async (): Promise<void> => {
    if (!query) return
    const number = bareNumber(query)
    const match = matches[highlight]
    // A bare number picks only that problem, unless another was chosen with the arrow keys.
    if (match && (number === null || match.number === number || highlight > 0)) return choose(match)
    const resolved = await resolve(query)
    if ('pick' in resolved) {
      if (add(resolved.pick)) {
        setText('')
        setMessage(null)
      }
    } else if ('message' in resolved) setMessage(resolved.message)
    else if (imported !== false) setMessage(`No imported problem matches "${query}".`)
  }

  const keyDown = (event: KeyboardEvent<HTMLInputElement>): void => {
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      if (matches.length === 0) return
      event.preventDefault()
      const step = event.key === 'ArrowDown' ? 1 : -1
      setHighlight((h) => (h + step + matches.length) % matches.length)
    } else if (event.key === 'Enter' || event.key === ',' || (event.key === 'Tab' && matches.length > 0)) {
      event.preventDefault()
      void commit()
    } else if (event.key === 'Backspace' && text === '' && picks.length > 0) {
      onChange(picks.slice(0, -1))
    } else if (event.key === 'Escape') {
      setFound({ query: '', matches: [] })
    }
  }

  const paste = async (event: ClipboardEvent<HTMLInputElement>): Promise<void> => {
    const pasted = event.clipboardData.getData('text')
    if (!/[,\n]/.test(pasted)) return
    event.preventDefault()
    const left: string[] = []
    const messages: string[] = []
    for (const piece of pieces(pasted)) {
      const resolved = await resolve(piece)
      if ('pick' in resolved) {
        if (!add(resolved.pick)) messages.push(`#${resolved.pick.number} is already picked.`)
      } else if ('message' in resolved) messages.push(resolved.message)
      else left.push(piece)
    }
    setText([text.trim(), ...left].filter(Boolean).join(', '))
    setMessage(messages.length > 0 ? messages.join(' ') : null)
  }

  return (
    <div className="problem-picker">
      <div className="picker-box">
        {picks.map((pick, index) => (
          <span key={pick.number} className="pick" data-leetcode-only={pick.difficulty === null}>
            <span>
              #{pick.number} {pick.title}
            </span>
            <span className="muted">{pick.difficulty ?? 'Solved on LeetCode'}</span>
            <button
              type="button"
              className="pick-remove"
              aria-label={`Remove #${pick.number} ${pick.title}`}
              onClick={() => onChange(picks.filter((_, i) => i !== index))}
            >
              ×
            </button>
          </span>
        ))}
        <input
          className="picker-input"
          role="combobox"
          aria-label="LeetCode problems"
          aria-expanded={matches.length > 0}
          aria-controls={listId}
          aria-activedescendant={matches.length > 0 ? `${listId}-${highlight}` : undefined}
          placeholder={picks.length === 0 ? 'Type a problem number or name, such as 1 or two sum' : ''}
          value={text}
          onChange={(event) => {
            setText(event.target.value)
            setMessage(null)
          }}
          onKeyDown={keyDown}
          onPaste={paste}
        />
      </div>
      {matches.length > 0 && (
        <ul id={listId} className="picker-matches" role="listbox" aria-label="Matching problems">
          {matches.map((match, index) => (
            <li
              key={match.number}
              id={`${listId}-${index}`}
              role="option"
              aria-selected={index === highlight}
              className="picker-match"
              // Picked on mouse down, so the input keeps its focus.
              onMouseDown={(event) => {
                event.preventDefault()
                choose(match)
              }}
            >
              <span>
                #{match.number} {match.title}
              </span>
              <span className="muted">{match.difficulty}</span>
            </li>
          ))}
        </ul>
      )}
      {imported === false && (
        <p className="muted">
          No LeetCode problems are imported, so search finds nothing. Import LeetCodeDataset to search it (see
          architecture/code-problems.md), or type each problem&apos;s number and title, such as 875 Koko Eating
          Bananas, to solve it on LeetCode.
        </p>
      )}
      {message && <p className="answer-error">{message}</p>}
    </div>
  )
}

function toPick(match: LeetCodeMatch): Pick {
  return { number: match.number, title: match.title, difficulty: match.difficulty }
}
