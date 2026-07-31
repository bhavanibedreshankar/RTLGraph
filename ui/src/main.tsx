import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import Landing from './Landing.tsx'

const isApp = window.location.pathname.startsWith('/app')

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    {isApp ? <App /> : <Landing />}
  </StrictMode>,
)
