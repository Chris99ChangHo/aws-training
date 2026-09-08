import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import '@cloudscape-design/global-styles/index.css'
import { applyMode, Mode } from '@cloudscape-design/global-styles'
import './index.css'
import App from './App.jsx'

// 초기 색상 모드는 OS 설정(prefers-color-scheme)을 따른다. 앱 안의
// 라이트/다크 토글 버튼(App.jsx)을 누르면 이후로는 그 선택이 우선한다.
const darkModeQuery = window.matchMedia('(prefers-color-scheme: dark)')
applyMode(darkModeQuery.matches ? Mode.Dark : Mode.Light)

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
