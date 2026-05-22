import { useEffect, useRef, useState } from 'react'
import { BrowserRouter, NavLink, Route, Routes, useLocation } from 'react-router-dom'
import styles from './App.module.css'
import { type Health, getHealth, shutdownApp } from './api/client'
import ArticlePage from './pages/ArticlePage'
import InboxPage from './pages/InboxPage'
import SearchPage from './pages/SearchPage'
import SetupPage from './pages/SetupPage'
import SourcesPage from './pages/SourcesPage'

function MainMenu() {
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
            <button className={`${styles.dropItem} ${styles.danger}`} onClick={() => void handleShutdown()}>
              Close application
            </button>
          </li>
        </ul>
      )}
    </div>
  )
}

function Nav({ health }: { health: Health | null }) {
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
        <NavLink to="/search" className={({ isActive }) => (isActive ? styles.active : '')}>
          Search
        </NavLink>
        <NavLink to="/setup" className={({ isActive }) => (isActive ? styles.active : '')}>
          Setup
        </NavLink>
      </nav>
      {health !== null && (
        <span className={styles.pill}>{health.articles.toLocaleString()} articles</span>
      )}
      <MainMenu />
    </header>
  )
}

function AppShell() {
  const [health, setHealth] = useState<Health | null>(null)
  const location = useLocation()

  useEffect(() => {
    getHealth()
      .then(setHealth)
      .catch(() => undefined)
  }, [location.pathname])

  return (
    <>
      <Nav health={health} />
      <main className={styles.main}>
        <Routes>
          <Route path="/" element={<InboxPage />} />
          <Route path="/sources" element={<SourcesPage />} />
          <Route path="/articles/:id" element={<ArticlePage />} />
          <Route path="/search" element={<SearchPage />} />
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
