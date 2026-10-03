import { AnswerField } from '../answers/AnswerField'
import { Markdown } from '../Markdown'
import type { CheckpointBlock } from '../types'

export function CheckpointBlockView({ block }: { block: CheckpointBlock }) {
  return (
    <article className="card">
      <span className="eyebrow">Checkpoint</span>
      <Markdown>{block.prompt}</Markdown>
      <AnswerField answer={block.answer} verified={block.verified} />
    </article>
  )
}
