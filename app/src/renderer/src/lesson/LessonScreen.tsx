import { useEffect, useState } from 'react'
import { ApiError, getLesson, getProgress, type LessonResponse, type ProgressRecord, saveDays, type TestFlag } from '../api'
import { CodeRunnerProvider } from '../code/RunnerContext'
import { type QueryTarget, SqlWorkspace } from '../code/SqlWorkspace'
import { OpenWorkspace, Workspace } from '../code/Workspace'
import { RerunDialog } from '../generating/RerunDialog'
import { boundaries, lessonEnd, MAX_DAYS, splitDays } from './days/days'
import { DaysDialog } from './days/DaysDialog'
import { LessonView } from './LessonView'
import { ProgressProvider } from './progress/ProgressContext'
import type { CodeAnswer, Lesson, Part, ProblemBlock, QueryAnswer } from './types'

type State =
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'unavailable'; message: string }
  | { status: 'ready'; lesson: Lesson; progress: ProgressRecord[]; flags: TestFlag[]; response: LessonResponse }

const UNAVAILABLE = {
  generating: 'This lesson is still being generated.',
  failed: 'This lesson failed to generate.'
}

interface LessonScreenProps {
  lessonId: string
  onBack: () => void
  onRerun: (lessonId: string) => void
}

export function LessonScreen({ lessonId, onBack, onRerun }: LessonScreenProps) {
  const [state, setState] = useState<State>({ status: 'loading' })
  const [rerunning, setRerunning] = useState(false)
  const [splitting, setSplitting] = useState(false)
  const [workspace, setWorkspace] = useState<{ blockId: string; partId: string | null } | null>(null)
  const open =
    state.status === 'ready' && workspace ? findWorkspace(lessonId, state.lesson, workspace.blockId, workspace.partId) : null

  // The page underneath can't scroll while the workspace covers it, so it comes back where it was.
  useEffect(() => {
    if (!open) return
    document.documentElement.classList.add('in-workspace')
    return () => document.documentElement.classList.remove('in-workspace')
  }, [open])

  useEffect(() => {
    let cancelled = false
    setState({ status: 'loading' })
    load(lessonId)
      .then((next) => !cancelled && setState(next))
      .catch((error: Error) => !cancelled && setState({ status: 'error', message: error.message }))
    return () => {
      cancelled = true
    }
  }, [lessonId])

  const canRerun = state.status === 'ready' && state.response.rerun_stages.length > 0

  // Cuts the lesson as it is laid out now; the saved lines then stay with their blocks.
  const split = async (days: number): Promise<string | null> => {
    const root = document.querySelector<HTMLElement>('.lesson')
    const end = root ? lessonEnd(root) : null
    const starts = root && end !== null ? splitDays(boundaries(root), end, days) : []
    try {
      await saveDays(lessonId, starts)
    } catch (err) {
      return err instanceof ApiError ? err.message : 'Could not reach the server.'
    }
    setState((current) =>
      current.status === 'ready' ? { ...current, response: { ...current.response, day_starts: starts } } : current
    )
    setSplitting(false)
    return null
  }

  const screen = (
    <>
      <nav className="screen-nav lesson-nav">
        <button type="button" className="link-button" onClick={onBack}>
          Library
        </button>
        <div className="lesson-actions">
          {state.status === 'ready' && (
            <button type="button" className="button" onClick={() => setSplitting(true)}>
              Days
            </button>
          )}
          {canRerun && (
            <button type="button" className="button" onClick={() => setRerunning(true)}>
              Rerun
            </button>
          )}
        </div>
      </nav>
      {state.status === 'loading' && <p className="screen-message">Loading lesson</p>}
      {state.status === 'error' && <p className="screen-message">Could not load the lesson: {state.message}</p>}
      {state.status === 'unavailable' && <p className="screen-message">{state.message}</p>}
      {state.status === 'ready' && (
        <>
          {state.response.error && <p className="notice">{state.response.error}</p>}
          <OpenWorkspace.Provider value={(blockId, partId) => setWorkspace({ blockId, partId })}>
            <LessonView
              lesson={state.lesson}
              readingBlock={state.response.reading_block}
              dayStarts={state.response.day_starts}
            />
          </OpenWorkspace.Provider>
          {splitting && (
            <DaysDialog
              current={state.response.day_starts.length + 1}
              max={Math.min(MAX_DAYS, state.lesson.sections.reduce((count, s) => count + s.blocks.length, 0))}
              onSplit={split}
              onCancel={() => setSplitting(false)}
            />
          )}
          {rerunning && (
            <RerunDialog
              lessonId={lessonId}
              status={state.response}
              onCancel={() => setRerunning(false)}
              onStarted={() => onRerun(lessonId)}
            />
          )}
        </>
      )}
    </>
  )
  if (state.status !== 'ready') return screen

  // The workspace covers the lesson, which stays mounted underneath, inert, and keeps its place.
  return (
    <CodeRunnerProvider enabled={hasCodeParts(state.lesson)}>
      <ProgressProvider key={lessonId} lessonId={lessonId} initial={state.progress} initialFlags={state.flags}>
        <div inert={open !== null}>{screen}</div>
        {open?.kind === 'code' && (
          <Workspace
            key={`${open.block.id}/${open.part.id}`}
            block={open.block}
            part={open.part}
            onBack={() => setWorkspace(null)}
          />
        )}
        {open?.kind === 'query' && (
          <SqlWorkspace
            key={`${open.target.blockId}/${open.target.partId ?? ''}`}
            target={open.target}
            onBack={() => setWorkspace(null)}
          />
        )}
      </ProgressProvider>
    </CodeRunnerProvider>
  )
}

function codeParts(lesson: Lesson): { block: ProblemBlock; part: Part & { answer: CodeAnswer } }[] {
  return lesson.sections.flatMap((section) =>
    section.blocks.flatMap((block) =>
      block.type === 'problem'
        ? block.parts
            .filter((part): part is Part & { answer: CodeAnswer } => part.answer.kind === 'code')
            .map((part) => ({ block, part }))
        : []
    )
  )
}

function hasCodeParts(lesson: Lesson): boolean {
  return codeParts(lesson).length > 0
}

type OpenTarget =
  | { kind: 'code'; block: ProblemBlock; part: Part & { answer: CodeAnswer } }
  | { kind: 'query'; target: QueryTarget }

/** What the workspace opens for: a code part, or a query part or checkpoint (partId null). */
function findWorkspace(lessonId: string, lesson: Lesson, blockId: string, partId: string | null): OpenTarget | null {
  const block = lesson.sections.flatMap((section) => section.blocks).find((b) => b.id === blockId)
  if (block?.type === 'checkpoint' && partId === null && block.answer.kind === 'query') {
    const answer: QueryAnswer = block.answer
    const title = answer.exercise ? 'Practice' : 'Checkpoint'
    return { kind: 'query', target: { lessonId, blockId, partId, title, prompt: block.prompt, answer, hints: block.hints } }
  }
  if (block?.type !== 'problem') return null
  const part = block.parts.find((p) => p.id === partId)
  if (!part) return null
  if (part.answer.kind === 'code') return { kind: 'code', block, part: part as Part & { answer: CodeAnswer } }
  if (part.answer.kind === 'query') {
    const title = block.parts.length > 1 ? `${block.source_ref} ${part.label}` : block.source_ref
    const prompt = [block.prompt, part.prompt].filter(Boolean).join('\n\n')
    const target = { lessonId, blockId, partId: part.id, title, prompt, answer: part.answer, hints: part.hints }
    return { kind: 'query', target }
  }
  return null
}

async function load(lessonId: string): Promise<State> {
  const body = await getLesson(lessonId)
  if (body.status !== 'ready' || !body.lesson) {
    return { status: 'unavailable', message: UNAVAILABLE[body.status === 'failed' ? 'failed' : 'generating'] }
  }
  const { progress, flags } = await getProgress(lessonId)
  return { status: 'ready', lesson: body.lesson, progress, flags, response: body }
}
