import { useEffect, useState } from 'react'
import { type Source, getSources } from '../api/client'
import SourceCard from '../components/SourceCard'
import styles from './SourcesPage.module.css'

export default function SourcesPage() {
  const [sources, setSources] = useState<Source[]>([])
  const [loading, setLoading] = useState(true)

  const load = () => {
    getSources()
      .then(setSources)
      .catch(() => undefined)
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    load()
  }, [])

  const handleChange = () => {
    getSources()
      .then(setSources)
      .catch(() => undefined)
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
      <div className={styles.grid}>
        {sources.map(s => (
          <SourceCard key={s.id} source={s} onChange={() => handleChange()} />
        ))}
      </div>
    </div>
  )
}
