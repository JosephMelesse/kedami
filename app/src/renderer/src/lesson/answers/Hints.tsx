import { Markdown } from '../Markdown'

/** Hints revealed so far, gentle first. There is no full-solution reveal. */
export function Hints({ hints, used }: { hints: string[]; used: number }) {
  if (used === 0) return null
  return (
    <ol className="hints">
      {hints.slice(0, used).map((hint, index) => (
        <li key={index} className="fade-in">
          <span className="eyebrow">Hint {index + 1}</span>
          <Markdown>{hint}</Markdown>
        </li>
      ))}
    </ol>
  )
}
