import { useEffect, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { type ArticleSearchHit, type Source, searchArticles, getSources, patchArticle, formatDate } from '../api/client'
import styles from './SearchPage.module.css'

const SEARCH_LIMIT = 50

export default function SearchPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const navigate = useNavigate()
  const inputRef = useRef<HTMLInputElement>(null)

  const q = searchParams.get('q') ?? ''
  const [inputValue, setInputValue] = useState(q)
  const [results, setResults] = useState<ArticleSearchHit[]>([])
  const [loading, setLoading] = useState(false)
  const [searched, setSearched] = useState(false)
  const [sourceMap, setSourceMap] = useState<Map<number, string>>(new Map())

  useEffect(() => {
    getSources()
      .then(sources => setSourceMap(new Map(sources.map((s: Source) => [s.id, s.name]))))
      .catch(() => undefined)
  }, [])

  useEffect(() => {
    if (!q) {
      setResults([])
      setSearched(false)
      return
    }
    setLoading(true)
    setSearched(true)
    searchArticles(q, SEARCH_LIMIT)
      .then(setResults)
      .catch(() => setResults([]))
      .finally(() => setLoading(false))
  }, [q])

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    const trimmed = inputValue.trim()
    if (!trimmed) return
    setSearchParams({ q: trimmed })
  }

  const handleClick = async (hit: ArticleSearchHit) => {
    if (!hit.is_read && hit.id != null) {
      await patchArticle(hit.id, { is_read: true }).catch(() => null)
    }
    navigate(`/articles/${hit.id}`, { state: { from: '/search?' + searchParams.toString() } })
  }

  const handleStar = async (hit: ArticleSearchHit, starred: boolean) => {
    if (hit.id == null) return
    const updated = await patchArticle(hit.id, { is_starred: starred }).catch(() => null)
    if (updated) {
      setResults(prev => prev.map(r => (r.id === updated.id ? { ...r, ...updated } : r)))
    }
  }

  return (
    <div>
      <form className={styles.form} onSubmit={submit}>
        <input
          ref={inputRef}
          className={styles.input}
          type="search"
          placeholder="Search articles…"
          value={inputValue}
          onChange={e => setInputValue(e.target.value)}
          autoFocus
        />
        <button className={styles.btn} type="submit" disabled={!inputValue.trim()}>
          Search
        </button>
      </form>

      {loading && <p className={styles.state}>Searching…</p>}

      {!loading && searched && results.length === 0 && (
        <p className={styles.state}>No results for &ldquo;{q}&rdquo;.</p>
      )}

      {!loading && results.length > 0 && (
        <>
          <p className={styles.count}>
            {results.length === SEARCH_LIMIT
              ? `Showing first ${SEARCH_LIMIT} results for "${q}"`
              : `${results.length} result${results.length !== 1 ? 's' : ''} for "${q}"`}
          </p>
          <div className={styles.list}>
            {results.map(hit => (
              <div
                key={hit.id}
                className={`${styles.hit} ${hit.is_read ? styles.read : ''}`}
                role="button"
                tabIndex={0}
                onClick={() => void handleClick(hit)}
                onKeyDown={e => e.key === 'Enter' && void handleClick(hit)}
              >
                <div className={styles.hitBody}>
                  <div className={styles.hitMeta}>
                    {sourceMap.get(hit.source_id) && (
                      <span className={styles.hitSource}>{sourceMap.get(hit.source_id)}</span>
                    )}
                    {hit.published_at && (
                      <span className={styles.hitDate}>{formatDate(hit.published_at)}</span>
                    )}
                  </div>
                  <h3 className={styles.hitTitle}>{hit.title}</h3>
                  <p
                    className={styles.snippet}
                    dangerouslySetInnerHTML={{ __html: hit.snippet }}
                  />
                </div>
                <button
                  className={`${styles.star} ${hit.is_starred ? styles.starred : ''}`}
                  title={hit.is_starred ? 'Unstar' : 'Star'}
                  onClick={e => {
                    e.stopPropagation()
                    void handleStar(hit, !hit.is_starred)
                  }}
                >
                  {hit.is_starred ? '★' : '☆'}
                </button>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
