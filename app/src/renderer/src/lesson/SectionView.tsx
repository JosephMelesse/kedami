import { Fragment } from 'react'
import { BlockView } from './BlockView'
import { FinishLine } from './days/FinishLine'
import type { Section } from './types'

interface SectionViewProps {
  section: Section
  lessonId: string
  /** The day each finish line ends, by the block that follows it. The lesson draws the one before the first block. */
  lineBefore?: ReadonlyMap<string, number>
}

export function SectionView({ section, lessonId, lineBefore }: SectionViewProps) {
  return (
    <section className="lesson-section">
      <header>
        <h2>{section.title}</h2>
        <p className="muted">{section.goal}</p>
      </header>
      {section.blocks.map((block, index) => {
        const day = index > 0 ? lineBefore?.get(block.id) : undefined
        return (
          <Fragment key={block.id}>
            {day && <FinishLine day={day} />}
            <div data-block-id={block.id}>
              <BlockView block={block} lessonId={lessonId} />
            </div>
          </Fragment>
        )
      })}
    </section>
  )
}
