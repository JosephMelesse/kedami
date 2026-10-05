/** A rule between blocks where a day ends. Day progress measures it by `data-finish-line`. */
export function FinishLine({ day }: { day: number }) {
  return (
    <div className="finish-line" data-finish-line>
      End of day {day}
    </div>
  )
}
