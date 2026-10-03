import { AnswerField } from '../answers/AnswerField'
import { Markdown } from '../Markdown'
import type { Part, ProblemBlock } from '../types'

export function ProblemBlockView({ block }: { block: ProblemBlock }) {
  const multiPart = block.parts.length > 1
  // Progress is wired up in build step 2; until then no part is done.
  const done = 0

  return (
    <article className="card">
      <header className="card-header">
        <span className="eyebrow">{block.source_ref}</span>
        {multiPart && (
          <span className="part-count">
            {done} of {block.parts.length} parts done
          </span>
        )}
      </header>
      {block.prompt && <Markdown>{block.prompt}</Markdown>}
      {block.parts.map((part) =>
        multiPart ? (
          <PartView key={part.id} part={part} />
        ) : (
          <SinglePartView key={part.id} part={part} />
        )
      )}
    </article>
  )
}

function PartView({ part }: { part: Part }) {
  return (
    <section className="part">
      <div className="part-prompt">
        <span className="part-label">{part.label}</span>
        <Markdown>{part.prompt}</Markdown>
      </div>
      <AnswerField answer={part.answer} verified={part.verified} />
    </section>
  )
}

// A single-part problem shows its prompt without the part label.
function SinglePartView({ part }: { part: Part }) {
  return (
    <>
      <Markdown>{part.prompt}</Markdown>
      <AnswerField answer={part.answer} verified={part.verified} />
    </>
  )
}
