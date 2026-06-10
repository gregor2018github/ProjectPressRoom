import { useEffect, useRef, useState } from 'react'
import { BrowserRouter, NavLink, Route, Routes, useLocation } from 'react-router-dom'
import styles from './App.module.css'
import { type Health, getHealth, shutdownApp } from './api/client'
import ArticlePage from './pages/ArticlePage'
import InboxPage from './pages/InboxPage'
import SetupPage from './pages/SetupPage'
import SourcesPage from './pages/SourcesPage'

type Theme = 'light' | 'dark'

function useTheme(): [Theme, () => void] {
  const [theme, setTheme] = useState<Theme>(() => {
    const stored = localStorage.getItem('pressroom-theme')
    if (stored === 'light' || stored === 'dark') return stored
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
  })

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    localStorage.setItem('pressroom-theme', theme)
  }, [theme])

  const toggle = () => setTheme(t => (t === 'light' ? 'dark' : 'light'))
  return [theme, toggle]
}

function useTextBrightness(): [number, (v: number) => void] {
  const [brightness, setBrightness] = useState<number>(() => {
    const stored = localStorage.getItem('pressroom-text-brightness')
    return stored ? Number(stored) : 96
  })

  useEffect(() => {
    document.documentElement.style.setProperty('--text-brightness', `${brightness}%`)
    localStorage.setItem('pressroom-text-brightness', String(brightness))
  }, [brightness])

  return [brightness, setBrightness]
}

function MainMenu({
  theme,
  onToggleTheme,
  brightness,
  onBrightnessChange,
}: {
  theme: Theme
  onToggleTheme: () => void
  brightness: number
  onBrightnessChange: (v: number) => void
}) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open])

  const handleShutdown = async () => {
    setOpen(false)
    await shutdownApp().catch(() => undefined)
    window.close()
  }

  return (
    <div className={styles.menuWrap} ref={ref}>
      <button
        className={styles.menuBtn}
        onClick={() => setOpen(o => !o)}
        title="Menu"
        aria-label="Main menu"
      >
        ⋮
      </button>
      {open && (
        <ul className={styles.dropdown}>
          <li>
            <button
              className={styles.dropItem}
              onClick={() => { onToggleTheme(); setOpen(false) }}
            >
              {theme === 'light' ? '🌙 Dark mode' : '☀️ Light mode'}
            </button>
          </li>
          {theme === 'dark' && (
            <li className={styles.sliderItem}>
              <div className={styles.sliderHeader}>
                <span>Text brightness</span>
                <span className={styles.sliderValue}>{brightness}%</span>
              </div>
              <input
                type="range"
                min={50}
                max={100}
                value={brightness}
                onChange={e => onBrightnessChange(Number(e.target.value))}
                className={styles.slider}
              />
            </li>
          )}
          <li className={styles.dropDivider} />
          <li>
            <button
              className={`${styles.dropItem} ${styles.danger}`}
              onClick={() => void handleShutdown()}
            >
              Close application
            </button>
          </li>
        </ul>
      )}
    </div>
  )
}

function Nav({
  health,
  theme,
  onToggleTheme,
  brightness,
  onBrightnessChange,
}: {
  health: Health | null
  theme: Theme
  onToggleTheme: () => void
  brightness: number
  onBrightnessChange: (v: number) => void
}) {
  return (
    <header className={styles.header}>
      <span className={styles.brand}>Pressroom</span>
      <nav className={styles.nav}>
        <NavLink to="/" end className={({ isActive }) => (isActive ? styles.active : '')}>
          Inbox
        </NavLink>
        <NavLink to="/sources" className={({ isActive }) => (isActive ? styles.active : '')}>
          Sources
        </NavLink>
        <NavLink to="/setup" className={({ isActive }) => (isActive ? styles.active : '')}>
          Setup
        </NavLink>
      </nav>
      {health !== null && (
        <span className={styles.pill}>{health.articles.toLocaleString()} articles</span>
      )}
      <MainMenu
        theme={theme}
        onToggleTheme={onToggleTheme}
        brightness={brightness}
        onBrightnessChange={onBrightnessChange}
      />
    </header>
  )
}

function AppShell() {
  const [health, setHealth] = useState<Health | null>(null)
  const [theme, toggleTheme] = useTheme()
  const [brightness, setBrightness] = useTextBrightness()
  const location = useLocation()

  useEffect(() => {
    getHealth()
      .then(setHealth)
      .catch(() => undefined)
  }, [location.pathname])

  return (
    <>
      <Nav
        health={health}
        theme={theme}
        onToggleTheme={toggleTheme}
        brightness={brightness}
        onBrightnessChange={setBrightness}
      />
      <main className={styles.main}>
        <Routes>
          <Route path="/" element={<InboxPage />} />
          <Route path="/sources" element={<SourcesPage />} />
          <Route path="/articles/:id" element={<ArticlePage />} />
          <Route path="/setup" element={<SetupPage />} />
        </Routes>
      </main>
    </>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <AppShell />
    </BrowserRouter>
  )
}
