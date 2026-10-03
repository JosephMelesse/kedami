import { Markdown } from '../Markdown'
import type { ExplanationBlock } from '../types'

export function ExplanationBlockView({ block }: { block: ExplanationBlock }) {
  return <Markdown>{block.body}</Markdown>
}
