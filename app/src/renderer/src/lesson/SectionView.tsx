import { BlockView } from './BlockView'
import type { Section } from './types'

export function SectionView({ section, lessonId }: { section: Section; lessonId: string }) {
  return (
    <section className="lesson-section">
      <header>
        <h2>{section.title}</h2>
        <p className="muted">{section.goal}</p>
      </header>
      {section.blocks.map((block) => (
        <div key={block.id} data-block-id={block.id}>
          <BlockView block={block} lessonId={lessonId} />
        </div>
      ))}
    </section>
  )
}
