import { useEffect, useState } from 'react'
import { BrowserRouter, NavLink, Route, Routes, useLocation } from 'react-router-dom'
import styles from './App.module.css'
import { type Health, getHealth } from './api/client'
import ArticlePage from './pages/ArticlePage'
import InboxPage from './pages/InboxPage'
import SearchPage from './pages/SearchPage'
import SetupPage from './pages/SetupPage'
import SourcesPage from './pages/SourcesPage'

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
