export function AppHeader({ onHome }: { onHome: () => void }) {
  return (
    <header className="app-header">
      <button type="button" className="app-name" onClick={onHome}>
        Kedami
      </button>
    </header>
  )
}
