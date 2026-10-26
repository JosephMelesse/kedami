import katex from 'katex'
import { type ReactNode, useCallback, useState } from 'react'
import { ApiError, getSolution, type SolutionResponse, type SolutionSteps, startSolutionJob } from '../../api'
import { ConfirmDialog } from '../../ConfirmDialog'
import { AgentJobProgress, useAgentJob } from '../AgentJob'
import { Markdown } from '../Markdown'

interface ShowSolutionProps {
  lessonId: string
  blockId: string
  partId: string
  name: string
}

type Status = 'hidden' | 'confirming' | 'loading' | 'shown'

/** A part's step-by-step solution, after a confirmation. A Claude Code job writes it the first time it is asked for. */
export function ShowSolution({ lessonId, blockId, partId, name }: ShowSolutionProps) {
  const [status, setStatus] = useState<Status>('hidden')
  const [result, setResult] = useState<SolutionResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  const fetchSolution = useCallback(async () => {
    const response = await getSolution(lessonId, blockId, partId)
    if (!response.solution) return false
    setResult(response)
    setStatus('shown')
    return true
  }, [lessonId, blockId, partId])

  const writing = useAgentJob(lessonId, fetchSolution)

  const load = async () => {
    setStatus('loading')
    setError(null)
    try {
      if (await fetchSolution()) return
      // None is stored yet, so Claude Code writes it; the job shows it once saved.
      await writing.start(() => startSolutionJob(lessonId, blockId, partId))
      setStatus('hidden')
    } catch (failure) {
      setError(failure instanceof ApiError ? failure.message : 'Could not reach the server.')
      setStatus('hidden')
    }
  }
  const problem = error ?? writing.failure

  return (
    <div className="solution">
      {status === 'shown' ? (
        <button type="button" className="button" onClick={() => setStatus('hidden')}>
          Hide solution
        </button>
      ) : (
        <button
          type="button"
          className="button"
          disabled={status === 'loading' || writing.job !== null}
          // Once seen, a solution opens again without asking.
          onClick={() => setStatus(result ? 'shown' : 'confirming')}
        >
          Show solution
        </button>
      )}
      {writing.job && <AgentJobProgress job={writing.job} what="this solution" />}
      {problem && <p className="answer-error">{problem}</p>}
      {status === 'confirming' && (
        <ConfirmDialog
          title={`Show the solution to ${name}?`}
          body="This shows every step and the final answer. The part still needs a correct answer or mark done."
          confirmLabel="Show solution"
          onCancel={() => setStatus('hidden')}
          onConfirm={load}
        />
      )}
      {status === 'shown' && result?.solution && <SolutionView solution={result.solution} matches={result.matches} />}
    </div>
  )
}

function SolutionView({ solution, matches }: { solution: SolutionSteps; matches: boolean | null }) {
  return (
    <div className="solution-steps">
      {matches === false && <span className="status-label">Doesn't match the stored answer</span>}
      {solution.format === 'general' ? <GeneralSteps steps={solution.steps} /> : <MathSteps solution={solution} />}
    </div>
  )
}

/** Left-aligned Markdown lines, with the last one shown as the answer. */
function GeneralSteps({ steps }: { steps: string[] }) {
  const reasoning = steps.slice(0, -1)
  return (
    <>
      {reasoning.length > 0 && (
        <SolutionPart label="Solution">
          {reasoning.map((line, index) => (
            <div key={index} className="solution-line solution-text">
              <Markdown>{line}</Markdown>
            </div>
          ))}
        </SolutionPart>
      )}
      <SolutionPart label="Answer">
        <div className="solution-line solution-text solution-answer">
          <Markdown>{steps[steps.length - 1]}</Markdown>
        </div>
      </SolutionPart>
    </>
  )
}

function MathSteps({ solution }: { solution: Exclude<SolutionSteps, { format: 'general' }> }) {
  return (
    <>
      {solution.format === 'math' ? (
        <SolutionPart label="Method">
          <p className="solution-method">{solution.method}</p>
        </SolutionPart>
      ) : (
        <>
          <SolutionPart label="Given">
            <MathLines lines={solution.given} />
          </SolutionPart>
          <SolutionPart label="Required">
            <MathLines lines={solution.required} />
          </SolutionPart>
        </>
      )}
      <SolutionPart label="Solution">
        <MathLines lines={solution.steps} />
      </SolutionPart>
    </>
  )
}

function SolutionPart({ label, children }: { label: string; children: ReactNode }) {
  return (
    <section className="solution-part">
      <h4 className="solution-label">{label}</h4>
      {children}
    </section>
  )
}

/** Each line as centered display math. KaTeX escapes its input, and trust stays off, so no markup gets through. */
function MathLines({ lines }: { lines: string[] }) {
  return (
    <>
      {lines.map((line, index) => (
        <div
          key={index}
          className="solution-line"
          dangerouslySetInnerHTML={{ __html: katex.renderToString(line, { displayMode: true, throwOnError: false }) }}
        />
      ))}
    </>
  )
}
