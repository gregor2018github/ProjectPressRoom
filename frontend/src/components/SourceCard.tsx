import { useState } from 'react'
import { type Source, formatDate, patchSource, triggerFetch } from '../api/client'
import styles from './SourceCard.module.css'

function StatusBadge({ status }: { status: string | null }) {
  if (!status) return null
  return <span className={`${styles.badge} ${styles[status] ?? ''}`}>{status}</span>
}

interface Props {
  source: Source
  onChange: (updated: Source) => void
}

export default function SourceCard({ source, onChange }: Props) {
  const [fetching, setFetching] = useState(false)

  const handleToggle = async (active: boolean) => {
    try {
      const updated = await patchSource(source.id, { is_active: active })
      onChange(updated)
    } catch {
      // keep previous state on error
    }
  }

  const handleFetch = async () => {
    setFetching(true)
    try {
      await triggerFetch(source.id)
      // Refresh by re-fetching source list at parent; signal via onChange with same source
      onChange({ ...source })
    } finally {
      setFetching(false)
    }
  }

  return (
    <div className={`${styles.card} ${source.is_active ? '' : styles.inactive}`}>
      <div className={styles.top}>
        <div className={styles.names}>
          <h3 className={styles.name}>{source.name}</h3>
          <div className={styles.tags}>
            {source.category && <span className={styles.tag}>{source.category}</span>}
            {source.language && <span className={styles.tag}>{source.language}</span>}
          </div>
        </div>
        <label className={styles.toggle} title={source.is_active ? 'Disable source' : 'Enable source'}>
          <input
            type="checkbox"
            checked={source.is_active}
            onChange={e => void handleToggle(e.target.checked)}
          />
          <span>{source.is_active ? 'Active' : 'Paused'}</span>
        </label>
      </div>

      <div className={styles.meta}>
        <StatusBadge status={source.last_run_status} />
        {source.last_run_articles_new !== null && (
          <span className={styles.newCount}>+{source.last_run_articles_new} new</span>
        )}
        {source.last_run_finished_at && (
          <span className={styles.time}>{formatDate(source.last_run_finished_at)}</span>
        )}
        {!source.last_run_status && <span className={styles.never}>Never fetched</span>}
      </div>

      {source.last_error && (
        <p className={styles.error}>{source.last_error}</p>
      )}

      <button className={styles.fetchBtn} onClick={() => void handleFetch()} disabled={fetching}>
        {fetching ? 'Fetching…' : 'Fetch now'}
      </button>
    </div>
  )
}
