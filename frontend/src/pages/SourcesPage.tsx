import { useEffect, useState } from 'react'
import { type DbStats, type Source, getSources, getStats, formatDate } from '../api/client'
import SourceCard from '../components/SourceCard'
import styles from './SourcesPage.module.css'

function fmtBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`
}

export default function SourcesPage() {
  const [sources, setSources] = useState<Source[]>([])
  const [loading, setLoading] = useState(true)
  const [dbStats, setDbStats] = useState<DbStats | null>(null)

  const load = () => {
    getSources()
      .then(setSources)
      .catch(() => undefined)
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    load()
    getStats().then(setDbStats).catch(() => undefined)
  }, [])

  const handleChange = () => {
    getSources().then(setSources).catch(() => undefined)
    getStats().then(setDbStats).catch(() => undefined)
  }

  if (loading) return <p className={styles.empty}>Loading…</p>

  if (sources.length === 0)
    return (
      <div className={styles.empty}>
        <p>No sources configured yet.</p>
        <p className={styles.hint}>
          Add sources to <code>config/sources.toml</code> and run{' '}
          <code>pressroom sources sync</code>.
        </p>
      </div>
    )

  return (
    <div>
      <h1 className={styles.heading}>Sources</h1>

      {dbStats && (
        <div className={styles.statsBar}>
          <div className={styles.statItem}>
            <span className={styles.statValue}>{dbStats.articles_total.toLocaleString()}</span>
            <span className={styles.statLabel}>articles</span>
          </div>
          <div className={styles.statDivider} />
          <div className={styles.statItem}>
            <span className={styles.statValue}>{dbStats.articles_unread.toLocaleString()}</span>
            <span className={styles.statLabel}>unread</span>
          </div>
          <div className={styles.statDivider} />
          <div className={styles.statItem}>
            <span className={styles.statValue}>{dbStats.articles_starred.toLocaleString()}</span>
            <span className={styles.statLabel}>starred</span>
          </div>
          <div className={styles.statDivider} />
          <div className={styles.statItem}>
            <span className={styles.statValue}>{fmtBytes(dbStats.db_size_bytes)}</span>
            <span className={styles.statLabel}>database</span>
          </div>
          <div className={styles.statDivider} />
          <div className={styles.statItem}>
            <span className={styles.statValue}>{dbStats.sources_active}/{dbStats.sources_total}</span>
            <span className={styles.statLabel}>sources active</span>
          </div>
          <div className={styles.statDivider} />
          <div className={styles.statItem}>
            <span className={styles.statValue}>{dbStats.fetch_runs_total.toLocaleString()}</span>
            <span className={styles.statLabel}>fetch runs</span>
          </div>
          {dbStats.newest_fetched_at && (
            <>
              <div className={styles.statDivider} />
              <div className={styles.statItem}>
                <span className={styles.statValue}>{formatDate(dbStats.newest_fetched_at)}</span>
                <span className={styles.statLabel}>last article</span>
              </div>
            </>
          )}
        </div>
      )}

      <div className={styles.grid}>
        {sources.map(s => (
          <SourceCard key={s.id} source={s} onChange={() => handleChange()} />
        ))}
      </div>
    </div>
  )
}
