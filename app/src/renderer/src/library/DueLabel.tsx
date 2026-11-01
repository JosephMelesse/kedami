/**
 * A YYYY-MM-DD date as "Nov 3", with the year when it isn't the current one. Built from its parts, since
 * `new Date('2026-11-03')` reads as UTC midnight and shows as Nov 2 west of Greenwich.
 */
export function formatDue(date: string, now: Date = new Date()): string {
  const [year, month, day] = date.split('-').map(Number)
  const options: Intl.DateTimeFormatOptions = { month: 'short', day: 'numeric' }
  if (year !== now.getFullYear()) options.year = 'numeric'
  return new Date(year, month - 1, day).toLocaleDateString('en-US', options)
}

interface DueLabelProps {
  date: string | null
  overdue: boolean
  prefix?: string
}

/** A due date, with a short Overdue label once it has passed. See Deadlines in architecture/ui.md. */
export function DueLabel({ date, overdue, prefix = 'Due' }: DueLabelProps) {
  if (date === null) return null
  return (
    <span className="due-label">
      <span>
        {prefix} {formatDue(date)}
      </span>
      {overdue && <span className="due-overdue">Overdue</span>}
    </span>
  )
}
