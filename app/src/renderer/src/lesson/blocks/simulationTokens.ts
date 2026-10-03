// The design token values a simulation frame receives, read from the app's own CSS.

const TOKEN_VARIABLES = {
  bg: '--bg',
  surface: '--surface',
  surfaceRaised: '--surface-raised',
  border: '--border',
  text: '--text',
  textMuted: '--text-muted',
  accent: '--accent',
  correct: '--correct',
  retry: '--retry',
  inProgress: '--in-progress'
} as const

export type SimulationTokens = Record<keyof typeof TOKEN_VARIABLES | 'font', string>

export function simulationTokens(root: Element = document.documentElement): SimulationTokens {
  const style = getComputedStyle(root)
  const values = Object.fromEntries(
    Object.entries(TOKEN_VARIABLES).map(([name, variable]) => [name, style.getPropertyValue(variable).trim()])
  )
  return { ...values, font: getComputedStyle(document.body).fontFamily } as SimulationTokens
}
