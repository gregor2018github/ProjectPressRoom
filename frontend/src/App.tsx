import { useEffect, useState } from 'react'
import { BrowserRouter, NavLink, Route, Routes } from 'react-router-dom'
import styles from './App.module.css'
import { type Health, getHealth } from './api/client'
import ArticlePage from './pages/ArticlePage'
import InboxPage from './pages/InboxPage'
import SearchPage from './pages/SearchPage'
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
      </nav>
      {health !== null && (
        <span className={styles.pill}>{health.articles.toLocaleString()} articles</span>
      )}
    </header>
  )
}

export default function App() {
  const [health, setHealth] = useState<Health | null>(null)

  useEffect(() => {
    getHealth()
      .then(setHealth)
      .catch(() => undefined)
  }, [])

  return (
    <BrowserRouter>
      <Nav health={health} />
      <main className={styles.main}>
        <Routes>
          <Route path="/" element={<InboxPage />} />
          <Route path="/sources" element={<SourcesPage />} />
          <Route path="/articles/:id" element={<ArticlePage />} />
          <Route path="/search" element={<SearchPage />} />
        </Routes>
      </main>
    </BrowserRouter>
  )
}
