import { AnswerField } from '../answers/AnswerField'
import { Markdown } from '../Markdown'
import { useProgress } from '../progress/ProgressContext'
import { partsDone } from '../progress/state'
import type { Part, ProblemBlock } from '../types'

export function ProblemBlockView({ block }: { block: ProblemBlock }) {
  const progress = useProgress()
  const multiPart = block.parts.length > 1

  return (
    <article className="card">
      <header className="card-header">
        <span className="eyebrow">{block.source_ref}</span>
        {multiPart && (
          <span className="part-count">
            {partsDone(block, progress.map)} of {block.parts.length} parts done
          </span>
        )}
      </header>
      {block.prompt && <Markdown>{block.prompt}</Markdown>}
      {block.parts.map((part) =>
        multiPart ? (
          <section key={part.id} className="part">
            <div className="part-prompt">
              <span className="part-label">{part.label}</span>
              <Markdown>{part.prompt}</Markdown>
            </div>
            <PartAnswer block={block} part={part} name={`${block.source_ref} ${part.label}`} />
          </section>
        ) : (
          // A single-part problem shows its prompt without the part label.
          <div key={part.id} className="part-single">
            <Markdown>{part.prompt}</Markdown>
            <PartAnswer block={block} part={part} name={block.source_ref} />
          </div>
        )
      )}
    </article>
  )
}

function PartAnswer({ block, part, name }: { block: ProblemBlock; part: Part; name: string }) {
  return (
    <AnswerField
      blockId={block.id}
      partId={part.id}
      name={name}
      answer={part.answer}
      hints={part.hints}
      verified={part.verified}
    />
  )
}
