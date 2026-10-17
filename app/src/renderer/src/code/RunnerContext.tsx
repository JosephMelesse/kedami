import { createContext, type ReactNode, useContext, useEffect, useRef, useState } from 'react'
import type { CodeRunner } from './runner/client'
import { mountRunner } from './runner/mount'

export type RunnerStatus = 'none' | 'starting' | 'ready' | 'failed'

export interface RunnerState {
  status: RunnerStatus
  /** Why Python couldn't start, when it failed. */
  message: string | null
  runner: CodeRunner | null
}

const RunnerContext = createContext<RunnerState>({ status: 'none', message: null, runner: null })

export function useCodeRunner(): RunnerState {
  return useContext(RunnerContext)
}

interface ProviderProps {
  /** Start the runner: true for a lesson with code parts, so the first Run doesn't wait for Pyodide. */
  enabled: boolean
  /** Mounts the runner's frame; tests stand in for it. */
  mount?: (container: HTMLElement) => CodeRunner
  children: ReactNode
}

export function CodeRunnerProvider({ enabled, mount = mountRunner, children }: ProviderProps) {
  const container = useRef<HTMLDivElement>(null)
  const [state, setState] = useState<RunnerState>({ status: 'none', message: null, runner: null })

  useEffect(() => {
    if (!enabled || !container.current) return
    const runner = mount(container.current)
    let current = true
    setState({ status: 'starting', message: null, runner })
    runner.ready.then(
      () => current && setState({ status: 'ready', message: null, runner }),
      (error: Error) => current && setState({ status: 'failed', message: error.message, runner: null })
    )
    return () => {
      current = false
      runner.dispose()
      setState({ status: 'none', message: null, runner: null })
    }
  }, [enabled, mount])

  return (
    <RunnerContext.Provider value={state}>
      <div ref={container} hidden />
      {children}
    </RunnerContext.Provider>
  )
}
