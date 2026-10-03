import { useState } from 'react'
import { Markdown } from '../Markdown'
import type { WorkedExampleBlock } from '../types'

export function WorkedExampleBlockView({ block }: { block: WorkedExampleBlock }) {
  const [shown, setShown] = useState(0)
  const total = block.steps.length

  return (
    <article className="card">
      <span className="eyebrow">Worked example</span>
      <Markdown>{block.prompt}</Markdown>
      {shown > 0 && (
        <ol className="steps">
          {block.steps.slice(0, shown).map((step, index) => (
            <li key={index} className="fade-in">
              <Markdown>{step}</Markdown>
            </li>
          ))}
        </ol>
      )}
      {shown < total && (
        <button type="button" className="button steps-control" onClick={() => setShown(shown + 1)}>
          Show step {shown + 1} of {total}
        </button>
      )}
    </article>
  )
}
