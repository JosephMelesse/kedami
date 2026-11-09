import { Markdown } from '../Markdown'
import type { ExplanationBlock } from '../types'

export function ExplanationBlockView({ block, added }: { block: ExplanationBlock; added: boolean }) {
  if (!added) return <Markdown>{block.body}</Markdown>
  return (
    <div className="added">
      <span className="eyebrow">Added</span>
      <Markdown>{block.body}</Markdown>
    </div>
  )
}
