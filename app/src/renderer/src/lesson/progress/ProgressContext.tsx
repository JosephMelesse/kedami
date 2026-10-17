import { createContext, type ReactNode, useCallback, useContext, useMemo, useState } from 'react'
import {
  ApiError,
  checkResponse,
  flagTest,
  markDone,
  type ProgressRecord,
  revealHints,
  saveCode,
  submitCode,
  type TestFlag
} from '../../api'
import { type ProgressMap, progressKey, toProgressMap } from './state'

/** Each action resolves to an error message to show, or null on success. */
export interface Progress {
  map: ProgressMap
  record(blockId: string, partId: string | null): ProgressRecord | undefined
  check(blockId: string, partId: string | null, response: unknown): Promise<string | null>
  revealHint(blockId: string, partId: string | null, count: number): Promise<string | null>
  markDone(blockId: string, partId: string, done: boolean): Promise<string | null>
  /** The tests flagged as broken on a code part. */
  flags(blockId: string, partId: string): TestFlag[]
  saveCode(blockId: string, partId: string, code: string): Promise<string | null>
  submit(blockId: string, partId: string, code: string, passed: boolean): Promise<string | null>
  flag(
    blockId: string,
    partId: string,
    action: 'flag' | 'unflag' | 'clear',
    test?: { args: string; expected: string }
  ): Promise<string | null>
}

const ProgressContext = createContext<Progress | null>(null)

export function useProgress(): Progress {
  const progress = useContext(ProgressContext)
  if (!progress) throw new Error('useProgress needs a ProgressProvider')
  return progress
}

interface ProviderProps {
  lessonId: string
  initial: ProgressRecord[]
  initialFlags?: TestFlag[]
  children: ReactNode
}

export function ProgressProvider({ lessonId, initial, initialFlags = [], children }: ProviderProps) {
  const [map, setMap] = useState<ProgressMap>(() => toProgressMap(initial))
  const [flags, setFlags] = useState<TestFlag[]>(initialFlags)

  const store = useCallback((record: ProgressRecord) => {
    setMap((current) => new Map(current).set(progressKey(record.block_id, record.part_id), record))
  }, [])

  const run = useCallback(
    async (action: () => Promise<ProgressRecord>): Promise<string | null> => {
      try {
        store(await action())
        return null
      } catch (error) {
        return error instanceof ApiError ? error.message : 'Could not reach the server.'
      }
    },
    [store]
  )

  const value = useMemo<Progress>(
    () => ({
      map,
      record: (blockId, partId) => map.get(progressKey(blockId, partId)),
      check: (blockId, partId, response) =>
        run(async () => (await checkResponse(lessonId, blockId, partId, response)).progress),
      revealHint: (blockId, partId, count) => run(() => revealHints(lessonId, blockId, partId, count)),
      markDone: (blockId, partId, done) => run(() => markDone(lessonId, blockId, partId, done)),
      flags: (blockId, partId) => flags.filter((f) => f.block_id === blockId && f.part_id === partId),
      saveCode: (blockId, partId, code) => run(() => saveCode(lessonId, blockId, partId, code)),
      submit: (blockId, partId, code, passed) => run(() => submitCode(lessonId, blockId, partId, code, passed)),
      flag: async (blockId, partId, action, test) => {
        try {
          const partFlags = await flagTest(lessonId, blockId, partId, action, test)
          setFlags((current) => [
            ...current.filter((f) => !(f.block_id === blockId && f.part_id === partId)),
            ...partFlags
          ])
          return null
        } catch (error) {
          return error instanceof ApiError ? error.message : 'Could not reach the server.'
        }
      }
    }),
    [lessonId, map, run, flags]
  )

  return <ProgressContext.Provider value={value}>{children}</ProgressContext.Provider>
}
