// The editor bar's Vim checkbox, with the current Vim mode while it is on.

interface VimControlProps {
  on: boolean
  onChange: (on: boolean) => void
  /** Such as "-- INSERT --"; null while Vim is off. */
  mode: string | null
}

export function VimControl({ on, onChange, mode }: VimControlProps) {
  return (
    <span className="vim-control">
      <label className="option">
        <input type="checkbox" checked={on} onChange={(event) => onChange(event.target.checked)} />
        Vim
      </label>
      {on && mode && (
        <span className="vim-mode" aria-live="polite">
          {mode}
        </span>
      )}
    </span>
  )
}
