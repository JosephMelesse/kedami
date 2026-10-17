import { QuerySummary } from '../../code/QuerySummary'
import { AnswerField } from '../answers/AnswerField'
import { Markdown } from '../Markdown'
import type { CheckpointBlock } from '../types'

export function CheckpointBlockView({ block }: { block: CheckpointBlock }) {
  return (
    <article className="card">
      <span className="eyebrow">Checkpoint</span>
      <Markdown>{block.prompt}</Markdown>
      {block.answer.kind === 'query' ? (
        // Solved in the SQL workspace.
        <QuerySummary
          blockId={block.id}
          partId={null}
          answer={block.answer}
          verified={block.verified}
          name="this checkpoint"
        />
      ) : (
        <AnswerField
          blockId={block.id}
          partId={null}
          name="this checkpoint"
          answer={block.answer}
          hints={block.hints}
          verified={block.verified}
        />
      )}
    </article>
  )
}
