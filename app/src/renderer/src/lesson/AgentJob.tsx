import { useEffect, useState } from 'react'
import { ApiError, getLessonJobs, type Job } from '../api'

// How often a screen waiting on a Claude Code job checks on it.
export const AGENT_POLL_MS = 3000

const isActive = (job: Job | null) => job !== null && (job.status === 'queued' || job.status === 'running')

/**
 * A Claude Code job for one thing in a lesson: start it, check on it every AGENT_POLL_MS, and call `onDone` once
 * it has saved. Starting the same thing again returns the job already running. See architecture/agent-mode.md,
 * Background jobs.
 */
export function useAgentJob(lessonId: string, onDone: () => Promise<unknown>) {
  const [job, setJob] = useState<Job | null>(null)
  const [error, setError] = useState<string | null>(null)
  const active = isActive(job)
  const jobId = job?.id

  useEffect(() => {
    if (!active || jobId === undefined) return
    let stopped = false
    const timer = setInterval(async () => {
      try {
        const latest = (await getLessonJobs(lessonId)).find((j) => j.id === jobId)
        if (stopped || !latest) return
        if (latest.status === 'done') {
          clearInterval(timer)
          await onDone()
          if (!stopped) setJob(null)
        } else {
          // Only a change of status replaces the job, so the timer keeps running while it waits.
          setJob((current) => (current?.status === latest.status ? current : latest))
        }
      } catch {
        // The next tick tries again.
      }
    }, AGENT_POLL_MS)
    return () => {
      stopped = true
      clearInterval(timer)
    }
  }, [lessonId, jobId, active, onDone])

  const start = async (run: () => Promise<Job>) => {
    setError(null)
    try {
      setJob(await run())
    } catch (failure) {
      setError(failure instanceof ApiError ? failure.message : 'Could not reach the server.')
    }
  }

  const ended = job !== null && (job.status === 'failed' || job.status === 'canceled')
  return {
    /** The job while it is queued or running. */
    job: active ? job : null,
    /** Why the last attempt didn't save: the server's refusal, or Claude Code's last message. */
    failure: error ?? (ended ? job.error ?? 'Claude Code stopped before saving it.' : null),
    start
  }
}

/** What the job is doing, in place of the button that started it. */
export function AgentJobProgress({ job, what }: { job: Job; what: string }) {
  return (
    <p className="muted agent-job">
      {job.status === 'queued'
        ? `Waiting for another job. Claude Code writes ${what} as soon as it finishes.`
        : `Claude Code is writing ${what}. It shows up here once it is saved.`}
    </p>
  )
}
