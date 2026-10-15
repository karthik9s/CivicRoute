import React from 'react'
import { createRoot } from 'react-dom/client'
import '@fontsource-variable/noto-sans' // self-hosted fonts (keeps the strict CSP: font-src 'self')
import '@fontsource/noto-sans-devanagari/400.css'
import '@fontsource/noto-sans-devanagari/700.css'
import '@fontsource/noto-sans-telugu/400.css'
import '@fontsource/noto-sans-telugu/700.css'
import App from './App.jsx'
import './styles.css'
import './extras.css'

createRoot(document.getElementById('root')).render(<App />)
