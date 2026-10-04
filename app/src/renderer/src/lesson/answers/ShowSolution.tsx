import katex from 'katex'
import { type ReactNode, useState } from 'react'
import { ApiError, getSolution, type SolutionResponse, type SolutionSteps } from '../../api'
import { ConfirmDialog } from '../../ConfirmDialog'

interface ShowSolutionProps {
  lessonId: string
  blockId: string
  partId: string
  name: string
}

type Status = 'hidden' | 'confirming' | 'writing' | 'shown'

/** A part's step-by-step solution, written the first time it is asked for, after a confirmation. */
export function ShowSolution({ lessonId, blockId, partId, name }: ShowSolutionProps) {
  const [status, setStatus] = useState<Status>('hidden')
  const [result, setResult] = useState<SolutionResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = async () => {
    setStatus('writing')
    setError(null)
    try {
      setResult(await getSolution(lessonId, blockId, partId))
      setStatus('shown')
    } catch (failure) {
      setError(failure instanceof ApiError ? failure.message : 'Could not reach the server.')
      setStatus('hidden')
    }
  }

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
          disabled={status === 'writing'}
          // Once seen, a solution opens again without asking.
          onClick={() => setStatus(result ? 'shown' : 'confirming')}
        >
          {status === 'writing' ? 'Writing solution...' : 'Show solution'}
        </button>
      )}
      {error && <p className="answer-error">{error}</p>}
      {status === 'confirming' && (
        <ConfirmDialog
          title={`Show the solution to ${name}?`}
          body="This shows every step and the final answer. The part still needs a correct answer or mark done."
          confirmLabel="Show solution"
          onCancel={() => setStatus('hidden')}
          onConfirm={load}
        />
      )}
      {status === 'shown' && result && <SolutionView solution={result.solution} matches={result.matches} />}
    </div>
  )
}

function SolutionView({ solution, matches }: { solution: SolutionSteps; matches: boolean | null }) {
  return (
    <div className="solution-steps">
      {matches === false && <span className="status-label">Doesn't match the stored answer</span>}
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
    </div>
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
