import { useEffect, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import {
  type ArticleSearchHit,
  type SearchFilters,
  type Source,
  searchArticles,
  getSources,
  patchArticle,
  formatDate,
} from '../api/client'
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
  const [sources, setSources] = useState<Source[]>([])
  const [showFilters, setShowFilters] = useState(false)

  // Filter state — read from URL
  const srcParam = searchParams.get('src')
  const authorParam = searchParams.get('author') ?? ''
  const fromParam = searchParams.get('from') ?? ''
  const toParam = searchParams.get('to') ?? ''

  const activeFilterCount = [srcParam, authorParam, fromParam, toParam].filter(Boolean).length

  useEffect(() => {
    getSources()
      .then(list => {
        setSources(list)
        setSourceMap(new Map(list.map((s: Source) => [s.id, s.name])))
      })
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
    const filters: SearchFilters = {}
    if (srcParam) filters.source_id = Number(srcParam)
    if (authorParam) filters.author = authorParam
    if (fromParam) filters.from_date = fromParam
    if (toParam) filters.to_date = toParam
    searchArticles(q, SEARCH_LIMIT, filters)
      .then(setResults)
      .catch(() => setResults([]))
      .finally(() => setLoading(false))
  }, [q, srcParam, authorParam, fromParam, toParam])

  const buildParams = (overrides: Record<string, string>) => {
    const base: Record<string, string> = {}
    if (inputValue.trim()) base.q = inputValue.trim()
    if (srcParam) base.src = srcParam
    if (authorParam) base.author = authorParam
    if (fromParam) base.from = fromParam
    if (toParam) base.to = toParam
    return { ...base, ...overrides }
  }

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    const trimmed = inputValue.trim()
    if (!trimmed) return
    setSearchParams(buildParams({ q: trimmed }))
  }

  const setFilter = (key: string, value: string) => {
    const params = buildParams({})
    if (value) params[key] = value
    else delete params[key]
    setSearchParams(params)
  }

  const clearFilters = () => {
    const params: Record<string, string> = {}
    if (q) params.q = q
    setSearchParams(params)
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
        <button
          type="button"
          className={`${styles.filterToggle} ${showFilters ? styles.filterToggleActive : ''}`}
          onClick={() => setShowFilters(v => !v)}
        >
          Filters{activeFilterCount > 0 && <span className={styles.filterBadge}>{activeFilterCount}</span>}
        </button>
      </form>

      {showFilters && (
        <div className={styles.filterBar}>
          <label className={styles.filterField}>
            <span className={styles.filterLabel}>Source</span>
            <select
              className={styles.filterSelect}
              value={srcParam ?? ''}
              onChange={e => setFilter('src', e.target.value)}
            >
              <option value="">All sources</option>
              {sources.map(s => (
                <option key={s.id} value={String(s.id)}>{s.name}</option>
              ))}
            </select>
          </label>

          <label className={styles.filterField}>
            <span className={styles.filterLabel}>Author</span>
            <input
              className={styles.filterInput}
              type="text"
              placeholder="Any author"
              value={authorParam}
              onChange={e => setFilter('author', e.target.value)}
            />
          </label>

          <label className={styles.filterField}>
            <span className={styles.filterLabel}>From</span>
            <input
              className={styles.filterInput}
              type="date"
              value={fromParam}
              onChange={e => setFilter('from', e.target.value)}
            />
          </label>

          <label className={styles.filterField}>
            <span className={styles.filterLabel}>To</span>
            <input
              className={styles.filterInput}
              type="date"
              value={toParam}
              onChange={e => setFilter('to', e.target.value)}
            />
          </label>

          {activeFilterCount > 0 && (
            <button type="button" className={styles.clearBtn} onClick={clearFilters}>
              Clear filters
            </button>
          )}
        </div>
      )}

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
            {activeFilterCount > 0 && <span className={styles.filterNote}> · {activeFilterCount} filter{activeFilterCount !== 1 ? 's' : ''} active</span>}
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
                    {hit.author && (
                      <span className={styles.hitAuthor}>{hit.author}</span>
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
