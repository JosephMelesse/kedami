import { CheckpointBlockView } from './blocks/CheckpointBlockView'
import { DiagramBlockView } from './blocks/DiagramBlockView'
import { ExplanationBlockView } from './blocks/ExplanationBlockView'
import { PlotBlockView } from './blocks/PlotBlockView'
import { ProblemBlockView } from './blocks/ProblemBlockView'
import { SimulationBlockView } from './blocks/SimulationBlockView'
import { SourceBlockView } from './blocks/SourceBlockView'
import { WorkedExampleBlockView } from './blocks/WorkedExampleBlockView'
import type { Blocks } from './types'

type Block = Blocks[number]

interface BlockViewProps {
  block: Block
  lessonId: string
  /** Whether the lesson has source blocks, so what the model wrote is labeled as added. */
  labelAdded: boolean
}

export function BlockView({ block, lessonId, labelAdded }: BlockViewProps) {
  switch (block.type) {
    case 'source':
      return <SourceBlockView block={block} />
    case 'explanation':
      return <ExplanationBlockView block={block} added={labelAdded} />
    case 'worked_example':
      return <WorkedExampleBlockView block={block} />
    case 'plot':
      return <PlotBlockView block={block} lessonId={lessonId} />
    case 'diagram':
      return <DiagramBlockView block={block} added={labelAdded} />
    case 'checkpoint':
      return <CheckpointBlockView block={block} />
    case 'problem':
      return <ProblemBlockView block={block} lessonId={lessonId} />
    case 'simulation':
      return <SimulationBlockView block={block} lessonId={lessonId} />
  }
}
