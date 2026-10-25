import { useEffect, useState } from 'react'

// How often a screen waiting on Claude Code asks the server whether it has written the thing yet.
export const AGENT_POLL_MS = 3000

/**
 * A command for the student to run in Claude Code, with a Copy button. Kedami never types it into the terminal
 * itself; see architecture/agent-mode.md.
 */
export function AgentCommand({ what, command }: { what: string; command: string }) {
  const [copied, setCopied] = useState(false)
  const copy = () => {
    navigator.clipboard.writeText(command).then(
      () => setCopied(true),
      () => {}
    )
  }
  return (
    <div className="agent-command">
      <p className="muted">
        Claude Code writes {what}. In the Terminal panel (Ctrl+`), start Claude Code and run this. It shows up here
        once it is saved.
      </p>
      <div className="agent-command-line">
        <code>{command}</code>
        <button type="button" className="button" onClick={copy}>
          {copied ? 'Copied' : 'Copy'}
        </button>
      </div>
    </div>
  )
}

/** Calls `check` every AGENT_POLL_MS while `waiting`, until it reports done. */
export function useAgentPoll(waiting: boolean, check: () => Promise<boolean>): void {
  useEffect(() => {
    if (!waiting) return
    let stopped = false
    const timer = setInterval(async () => {
      try {
        if ((await check()) && !stopped) clearInterval(timer)
      } catch {
        // The next tick tries again.
      }
    }, AGENT_POLL_MS)
    return () => {
      stopped = true
      clearInterval(timer)
    }
  }, [waiting, check])
}
