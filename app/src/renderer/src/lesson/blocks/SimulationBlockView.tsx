import { useCallback, useEffect, useRef, useState } from 'react'
import { getSimulation, reportSimulation } from '../../api'
import { AgentCommand, useAgentPoll } from '../AgentCommand'
import { Markdown } from '../Markdown'
import type { SimulationBlock } from '../types'
import { simulationTokens } from './simulationTokens'

// A simulation must report ready this soon after its frame loads, with no errors.
const READY_MS = 4000

// unwritten: the code is written only when the student asks for it.
// waiting: the student asked, and the command for Claude Code is showing until new code is saved.
type Status = 'loading' | 'unwritten' | 'running' | 'ready' | 'failed' | 'waiting'

export function SimulationBlockView({ block, lessonId }: { block: SimulationBlock; lessonId: string }) {
  const [code, setCode] = useState<string | null>(null)
  const [flagged, setFlagged] = useState(false)
  const [status, setStatus] = useState<Status>('loading')
  const [message, setMessage] = useState<string | null>(null)
  // Bumped to remount the frame with new code.
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    let cancelled = false
    getSimulation(lessonId, block.id)
      .then((state) => {
        if (cancelled) return
        setCode(state.code)
        setFlagged(state.flagged)
        setStatus(state.code ? 'running' : 'unwritten')
      })
      .catch((error: Error) => {
        if (cancelled) return
        setMessage(error.message)
        setStatus('failed')
      })
    return () => {
      cancelled = true
    }
  }, [lessonId, block.id])

  const finish = useCallback(
    (ok: boolean, error: string | null) => {
      setStatus(ok ? 'ready' : 'failed')
      // Record a failure, and clear one once the simulation works again.
      if (!ok || flagged) {
        setFlagged(!ok)
        reportSimulation(lessonId, block.id, ok, error).catch(() => {})
      }
    },
    [lessonId, block.id, flagged]
  )

  // New code from Claude Code replaces whatever was there, so waiting ends when the stored code changes.
  const checkForCode = useCallback(async () => {
    const state = await getSimulation(lessonId, block.id)
    if (!state.code || state.code === code) return false
    setCode(state.code)
    setFlagged(false)
    setMessage(null)
    setAttempt((n) => n + 1)
    setStatus('running')
    return true
  }, [lessonId, block.id, code])

  useAgentPoll(status === 'waiting', checkForCode)

  const showFrame = Boolean(code) && (status === 'running' || status === 'ready')
  const written = Boolean(code)

  return (
    <figure className="card simulation">
      {showFrame && <SimulationFrame key={attempt} code={code!} title={block.caption} onDone={finish} />}
      {status === 'loading' && <div className="plot-placeholder">Loading simulation</div>}
      {status === 'failed' && (
        <p className="muted">
          This simulation didn&apos;t load.{message ? ` ${message}` : ''}
        </p>
      )}
      {status !== 'failed' && (
        <figcaption>
          <Markdown inline>{block.caption}</Markdown>
        </figcaption>
      )}
      {status === 'waiting' ? (
        <AgentCommand what="this simulation" command={`/kedami:simulation ${lessonId} ${block.id}`} />
      ) : (
        <div>
          {written ? (
            <button type="button" className="button" disabled={status === 'loading'} onClick={() => setStatus('waiting')}>
              Regenerate
            </button>
          ) : (
            <button
              type="button"
              className="button button-primary"
              disabled={status === 'loading'}
              onClick={() => setStatus('waiting')}
            >
              Generate simulation
            </button>
          )}
        </div>
      )}
    </figure>
  )
}

interface FrameProps {
  code: string
  title: string
  onDone: (ok: boolean, error: string | null) => void
}

/** Runs the code in a sandboxed frame and reports once: ready, an error, or a timeout. */
function SimulationFrame({ code, title, onDone }: FrameProps) {
  const frame = useRef<HTMLIFrameElement>(null)
  const [height, setHeight] = useState(320)
  const done = useRef(false)

  useEffect(() => {
    const settle = (ok: boolean, error: string | null) => {
      if (done.current) return
      done.current = true
      onDone(ok, error)
    }
    const timer = setTimeout(() => settle(false, `No ready signal within ${READY_MS / 1000} seconds.`), READY_MS)
    const listen = (event: MessageEvent) => {
      // The frame's origin is opaque ("null"), so it is recognized by its window.
      if (event.source !== frame.current?.contentWindow) return
      const data = event.data ?? {}
      if (data.type === 'loaded') {
        frame.current?.contentWindow?.postMessage({ type: 'run', code, tokens: simulationTokens() }, '*')
      } else if (data.type === 'ready') {
        clearTimeout(timer)
        settle(true, null)
      } else if (data.type === 'error') {
        clearTimeout(timer)
        settle(false, String(data.message).slice(0, 500))
      }
      if (typeof data.height === 'number' && data.height > 0) setHeight(Math.min(data.height, 1200))
    }
    window.addEventListener('message', listen)
    return () => {
      clearTimeout(timer)
      window.removeEventListener('message', listen)
    }
  }, [code, onDone])

  return (
    <iframe
      ref={frame}
      className="simulation-frame"
      src="simulation.html"
      sandbox="allow-scripts"
      referrerPolicy="no-referrer"
      title={title}
      style={{ height }}
    />
  )
}
