import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  type FetchRun,
  type Health,
  type Source,
  type SyncResult,
  getHealth,
  getSources,
  syncSources,
  triggerFetch,
} from '../api/client'
import styles from './SetupPage.module.css'

interface FetchRow {
  source: Source
  run: FetchRun | null
  status: 'idle' | 'running' | 'done' | 'error'
}

export default function SetupPage() {
  const [health, setHealth] = useState<Health | null>(null)
  const [syncing, setSyncing] = useState(false)
  const [syncResult, setSyncResult] = useState<SyncResult | null>(null)
  const [syncError, setSyncError] = useState<string | null>(null)
  const [fetchRows, setFetchRows] = useState<FetchRow[]>([])
  const [fetching, setFetching] = useState(false)
  const [fetchDone, setFetchDone] = useState(false)

  useEffect(() => {
    getHealth()
      .then(setHealth)
      .catch(() => undefined)
  }, [])

  const reloadHealth = () =>
    getHealth()
      .then(setHealth)
      .catch(() => undefined)

  const handleSync = async () => {
    setSyncing(true)
    setSyncError(null)
    setSyncResult(null)
    try {
      const result = await syncSources()
      setSyncResult(result)
      setFetchRows(
        result.sources
          .filter(s => s.is_active)
          .map(s => ({ source: s, run: null, status: 'idle' as const })),
      )
    } catch (err) {
      setSyncError(err instanceof Error ? err.message : 'Sync failed')
    } finally {
      setSyncing(false)
      void reloadHealth()
    }
  }

  const handleFetchAll = async () => {
    setFetching(true)
    setFetchDone(false)

    let rows = fetchRows
    if (rows.length === 0) {
      const sources = await getSources().catch(() => [] as Source[])
      const active = sources.filter(s => s.is_active)
      rows = active.map(s => ({ source: s, run: null, status: 'idle' as const }))
      setFetchRows(rows)
    }

    for (let i = 0; i < rows.length; i++) {
      setFetchRows(prev =>
        prev.map((r, idx) => (idx === i ? { ...r, status: 'running' } : r)),
      )
      const run = await triggerFetch(rows[i].source.id).catch(() => null)
      const status: FetchRow['status'] =
        run?.status === 'ok' || run?.status === 'not_modified' ? 'done' : 'error'
      setFetchRows(prev =>
        prev.map((r, idx) => (idx === i ? { ...r, run, status } : r)),
      )
    }

    setFetching(false)
    setFetchDone(true)
    void reloadHealth()
  }

  const allFetchDone = fetchRows.length > 0 && fetchRows.every(r => r.status === 'done' || r.status === 'error')

  return (
    <div className={styles.page}>
      <h1 className={styles.heading}>Setup</h1>

      {/* Health summary */}
      {health && (
        <div className={styles.healthBar}>
          <span className={styles.healthStat}>{health.articles.toLocaleString()} articles</span>
          <span className={styles.healthDot} />
          <span className={styles.healthStat}>
            {syncResult ? `${syncResult.sources.length} sources` : 'ready'}
          </span>
        </div>
      )}

      {/* Step 1 — Sync */}
      <section className={styles.card}>
        <div className={styles.cardHeader}>
          <span className={styles.step}>1</span>
          <div>
            <h2 className={styles.cardTitle}>Sync sources</h2>
            <p className={styles.cardDesc}>
              Loads <code>config/sources.toml</code> into the database. Safe to re-run — existing
              sources are updated without losing your settings.
            </p>
          </div>
        </div>

        <button className={styles.btn} onClick={() => void handleSync()} disabled={syncing}>
          {syncing ? 'Syncing…' : 'Sync now'}
        </button>

        {syncError && <p className={styles.error}>{syncError}</p>}

        {syncResult && (
          <p className={styles.success}>
            ✓ {syncResult.synced} source{syncResult.synced !== 1 ? 's' : ''} synced
            {syncResult.sources.length > 0 && (
              <span className={styles.sourceList}>
                {' '}({syncResult.sources.map(s => s.name).join(', ')})
              </span>
            )}
          </p>
        )}
      </section>

      {/* Step 2 — Fetch */}
      <section className={styles.card}>
        <div className={styles.cardHeader}>
          <span className={styles.step}>2</span>
          <div>
            <h2 className={styles.cardTitle}>Fetch all articles</h2>
            <p className={styles.cardDesc}>
              Pulls fresh articles from every active source. Each feed runs in sequence — results
              appear as they complete.
            </p>
          </div>
        </div>

        <button
          className={styles.btn}
          onClick={() => void handleFetchAll()}
          disabled={fetching}
        >
          {fetching ? 'Fetching…' : fetchDone ? 'Fetch again' : 'Fetch all'}
        </button>

        {fetchRows.length > 0 && (
          <ul className={styles.fetchList}>
            {fetchRows.map(row => (
              <li key={row.source.id} className={`${styles.fetchRow} ${styles[row.status]}`}>
                <span className={styles.fetchIcon}>
                  {row.status === 'idle' && '○'}
                  {row.status === 'running' && '…'}
                  {row.status === 'done' && '✓'}
                  {row.status === 'error' && '✗'}
                </span>
                <span className={styles.fetchName}>{row.source.name}</span>
                {row.run && row.status === 'done' && (
                  <span className={styles.fetchStats}>
                    {row.run.articles_new} new · {row.run.articles_duplicate} dup
                  </span>
                )}
                {row.run && row.status === 'error' && (
                  <span className={styles.fetchError}>{row.run.error_message ?? 'error'}</span>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* Step 3 — Done */}
      {(fetchDone || allFetchDone) && (
        <section className={`${styles.card} ${styles.doneCard}`}>
          <div className={styles.cardHeader}>
            <span className={`${styles.step} ${styles.stepDone}`}>✓</span>
            <div>
              <h2 className={styles.cardTitle}>You're all set</h2>
              <p className={styles.cardDesc}>
                Articles are in the database.{' '}
                {health && <strong>{health.articles.toLocaleString()} total.</strong>}
              </p>
            </div>
          </div>
          <Link to="/" className={styles.btnLink}>
            Go to Inbox →
          </Link>
        </section>
      )}
    </div>
  )
}
