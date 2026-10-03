import '@fontsource/inter/400.css'
import '@fontsource/inter/500.css'
import 'katex/dist/katex.min.css'
import './styles/tokens.css'
import './styles/base.css'
import './lesson/lesson.css'
import './library/library.css'
import './generating/generating.css'

import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { App } from './App'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>
)
