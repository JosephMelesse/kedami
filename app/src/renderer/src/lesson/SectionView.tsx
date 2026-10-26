import { Fragment, type ReactNode } from 'react'
import { BlockView } from './BlockView'
import { FinishLine } from './days/FinishLine'
import { SelectControl, useIsSelected } from './selection/Selection'
import type { Section } from './types'

interface SectionViewProps {
  section: Section
  lessonId: string
  /** The day each finish line ends, by the block that follows it. The lesson draws the one before the first block. */
  lineBefore?: ReadonlyMap<string, number>
}

export function SectionView({ section, lessonId, lineBefore }: SectionViewProps) {
  const target = { sectionId: section.id }
  return (
    <section className="lesson-section" data-selected={useIsSelected(target)}>
      <header className="selectable">
        <h2>{section.title}</h2>
        <p className="muted">{section.goal}</p>
        <SelectControl target={target} name={`the section ${section.title}`} />
      </header>
      {section.blocks.map((block, index) => {
        const day = index > 0 ? lineBefore?.get(block.id) : undefined
        return (
          <Fragment key={block.id}>
            {day && <FinishLine day={day} />}
            <SelectableBlock blockId={block.id}>
              <BlockView block={block} lessonId={lessonId} />
            </SelectableBlock>
          </Fragment>
        )
      })}
    </section>
  )
}

function SelectableBlock({ blockId, children }: { blockId: string; children: ReactNode }) {
  const target = { blockId }
  return (
    <div className="selectable" data-block-id={blockId} data-selected={useIsSelected(target)}>
      {children}
      <SelectControl target={target} name="this block" />
    </div>
  )
}
