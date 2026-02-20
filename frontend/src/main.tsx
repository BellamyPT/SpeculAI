/**
 * Application entry point.
 * Wraps App in BrowserRouter for client-side routing.
 * StrictMode is enabled for development warnings.
 */

import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import '@/index.css'
import { App } from '@/App'

const rootElement = document.getElementById('root')

if (!rootElement) {
  throw new Error(
    'Root element #root not found. Ensure index.html contains <div id="root"></div>.'
  )
}

createRoot(rootElement).render(
  <StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </StrictMode>
)
