import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError, getSimulation, regenerateSimulation, reportSimulation } from '../../api'
import { Markdown } from '../Markdown'
import type { SimulationBlock } from '../types'
import { simulationTokens } from './simulationTokens'

// A simulation must report ready this soon after its frame loads, with no errors.
const READY_MS = 4000

type Status = 'loading' | 'running' | 'ready' | 'failed' | 'regenerating'

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
        setStatus('running')
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

  const regenerate = async () => {
    setStatus('regenerating')
    setMessage(null)
    try {
      const state = await regenerateSimulation(lessonId, block.id)
      setCode(state.code)
      setFlagged(false)
      setAttempt((n) => n + 1)
      setStatus('running')
    } catch (error) {
      setMessage(error instanceof ApiError ? error.message : 'Could not reach the server.')
      setStatus('failed')
    }
  }

  const showFrame = code !== null && (status === 'running' || status === 'ready')

  return (
    <figure className="card simulation">
      {showFrame && <SimulationFrame key={attempt} code={code} title={block.caption} onDone={finish} />}
      {status === 'loading' && <div className="plot-placeholder">Loading simulation</div>}
      {status === 'regenerating' && <div className="plot-placeholder">Writing a new simulation</div>}
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
      <div>
        <button type="button" className="button" disabled={status === 'regenerating' || status === 'loading'} onClick={regenerate}>
          Regenerate
        </button>
      </div>
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
