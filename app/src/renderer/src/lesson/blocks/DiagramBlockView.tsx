import DOMPurify from 'dompurify'
import { useMemo } from 'react'
import { Markdown } from '../Markdown'
import type { DiagramBlock } from '../types'

// Diagram SVG is model-written, so it is sanitized before it reaches the DOM.
// Style elements are dropped because their rules would apply to the whole page.
export function sanitizeSvg(svg: string): string {
  return DOMPurify.sanitize(svg, {
    USE_PROFILES: { svg: true, svgFilters: true },
    FORBID_TAGS: ['style', 'foreignObject']
  })
}

export function DiagramBlockView({ block }: { block: DiagramBlock }) {
  const html = useMemo(() => sanitizeSvg(block.svg), [block.svg])
  return (
    <figure className="card">
      <div className="diagram-svg" dangerouslySetInnerHTML={{ __html: html }} />
      <figcaption>
        <Markdown inline>{block.caption}</Markdown>
      </figcaption>
    </figure>
  )
}
