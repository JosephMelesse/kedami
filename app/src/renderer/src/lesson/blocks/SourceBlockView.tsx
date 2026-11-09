import { Markdown } from '../Markdown'
import type { SourceBlock } from '../types'

export function pagesLabel(block: SourceBlock): string {
  const pages = block.first_page === block.last_page ? `p. ${block.first_page}` : `pp. ${block.first_page}-${block.last_page}`
  return `${block.file}, ${pages}`
}

// Reference text, word for word: the lesson's main reading, with no card.
export function SourceBlockView({ block }: { block: SourceBlock }) {
  return (
    <div className="source">
      <p className="source-label muted">{pagesLabel(block)}</p>
      <Markdown>{block.body}</Markdown>
    </div>
  )
}
