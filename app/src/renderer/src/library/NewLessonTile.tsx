// Creating a lesson needs the upload screen and pipeline (build step 3), so the tile is inactive until then.
export function NewLessonTile() {
  return (
    <button type="button" className="tile tile-new" disabled>
      <span className="tile-title">New lesson</span>
    </button>
  )
}
