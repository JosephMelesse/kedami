import { CheckpointBlockView } from './blocks/CheckpointBlockView'
import { DiagramBlockView } from './blocks/DiagramBlockView'
import { ExplanationBlockView } from './blocks/ExplanationBlockView'
import { PlotBlockView } from './blocks/PlotBlockView'
import { ProblemBlockView } from './blocks/ProblemBlockView'
import { SimulationBlockView } from './blocks/SimulationBlockView'
import { WorkedExampleBlockView } from './blocks/WorkedExampleBlockView'
import type { Blocks } from './types'

type Block = Blocks[number]

export function BlockView({ block, lessonId }: { block: Block; lessonId: string }) {
  switch (block.type) {
    case 'explanation':
      return <ExplanationBlockView block={block} />
    case 'worked_example':
      return <WorkedExampleBlockView block={block} />
    case 'plot':
      return <PlotBlockView block={block} lessonId={lessonId} />
    case 'diagram':
      return <DiagramBlockView block={block} />
    case 'checkpoint':
      return <CheckpointBlockView block={block} />
    case 'problem':
      return <ProblemBlockView block={block} lessonId={lessonId} />
    case 'simulation':
      return <SimulationBlockView block={block} lessonId={lessonId} />
  }
}
