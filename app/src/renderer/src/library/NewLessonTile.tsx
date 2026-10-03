export function NewLessonTile({ onClick }: { onClick: () => void }) {
  return (
    <button type="button" className="tile tile-new" onClick={onClick}>
      <span className="tile-title">New lesson</span>
    </button>
  )
}
