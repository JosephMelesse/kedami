// Pure progress logic. See architecture/completion-and-verification.md.
import type { ProgressRecord } from '../../api'
import type { Lesson, ProblemBlock } from '../types'

export type PartState = 'not_started' | 'in_progress' | 'wrong' | 'correct' | 'marked_done'

export type ProgressMap = ReadonlyMap<string, ProgressRecord>

export function progressKey(blockId: string, partId: string | null): string {
  return `${blockId}/${partId ?? ''}`
}

export function toProgressMap(records: ProgressRecord[]): ProgressMap {
  return new Map(records.map((record) => [progressKey(record.block_id, record.part_id), record]))
}

/** "In progress, wrong" is an in-progress part whose last submitted answer was wrong. */
export function partState(record: ProgressRecord | undefined): PartState {
  if (!record) return 'not_started'
  if (record.status === 'in_progress' && record.last_response !== null) return 'wrong'
  return record.status
}

export function isDone(state: PartState): boolean {
  return state === 'correct' || state === 'marked_done'
}

export function partsDone(block: ProblemBlock, progress: ProgressMap): number {
  return block.parts.filter((part) => isDone(partState(progress.get(progressKey(block.id, part.id))))).length
}

export function problemCounts(lesson: Lesson, progress: ProgressMap): { done: number; total: number } {
  const problems = lesson.sections.flatMap((section) =>
    section.blocks.filter((block): block is ProblemBlock => block.type === 'problem')
  )
  const done = problems.filter((block) => partsDone(block, progress) === block.parts.length).length
  return { done, total: problems.length }
}
