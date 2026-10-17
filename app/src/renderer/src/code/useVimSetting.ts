// Whether the workspace editors use Vim motions, kept on this machine. See Workspace in
// architecture/code-problems.md.

import { useState } from 'react'

const KEY = 'kedami.editor.vim'

export function useVimSetting(): [boolean, (on: boolean) => void] {
  const [on, setOn] = useState(() => {
    try {
      return localStorage.getItem(KEY) === 'on'
    } catch {
      return false
    }
  })
  const set = (value: boolean): void => {
    setOn(value)
    try {
      localStorage.setItem(KEY, value ? 'on' : 'off')
    } catch {
      // Without storage, the choice lasts until the editor closes.
    }
  }
  return [on, set]
}
