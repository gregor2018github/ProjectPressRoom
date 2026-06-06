import { useEffect, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import {
  type ArticleSearchHit,
  type SearchFilters,
  type Source,
  searchArticles,
  getSources,
  getAuthors,
  patchArticle,
  formatDate,
} from '../api/client'
import styles from './SearchPage.module.css'

const LIMIT_OPTIONS = [50, 100, 200] as const

export default function SearchPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const navigate = useNavigate()
  const inputRef = useRef<HTMLInputElement>(null)

  const q = searchParams.get('q') ?? ''
  const [inputValue, setInputValue] = useState(q)
  const [results, setResults] = useState<ArticleSearchHit[]>([])
  const [loading, setLoading] = useState(false)
  const [searched, setSearched] = useState(false)
  const [sources, setSources] = useState<Source[]>([])
  const [sourceMap, setSourceMap] = useState<Map<number, string>>(new Map())
  const [authors, setAuthors] = useState<string[]>([])

  // Filter state — read from URL
  const srcParam      = searchParams.get('src') ?? ''
  const authorParam   = searchParams.get('author') ?? ''
  const fromParam     = searchParams.get('from') ?? ''
  const toParam       = searchParams.get('to') ?? ''
  const unreadParam   = searchParams.get('unread') === '1'
  const starredParam  = searchParams.get('starred') === '1'
  const scrapedParam  = searchParams.get('scraped') === '1'
  const limitParam    = Number(searchParams.get('limit') ?? '50') as typeof LIMIT_OPTIONS[number]
  const limit         = LIMIT_OPTIONS.includes(limitParam as 50) ? limitParam : 50

  const activeFilterCount = [srcParam, authorParam, fromParam, toParam,
    unreadParam, starredParam, scrapedParam].filter(Boolean).length

  // Load sources + authors for dropdowns
  useEffect(() => {
    getSources()
      .then(list => {
        setSources(list)
        setSourceMap(new Map(list.map((s: Source) => [s.id, s.name])))
      })
      .catch(() => undefined)
    getAuthors().then(setAuthors).catch(() => undefined)
  }, [])

  // Re-run search whenever URL params change
  useEffect(() => {
    const hasFilters = Boolean(srcParam || authorParam || fromParam || toParam || unreadParam || starredParam || scrapedParam)
    if (!q && !hasFilters) {
      setResults([])
      setSearched(false)
      return
    }
    setLoading(true)
    setSearched(true)
    const filters: SearchFilters = {}
    if (srcParam)     filters.source_id  = Number(srcParam)
    if (authorParam)  filters.author     = authorParam
    if (fromParam)    filters.from_date  = fromParam
    if (toParam)      filters.to_date    = toParam
    if (unreadParam)  filters.is_unread  = true
    if (starredParam) filters.is_starred = true
    if (scrapedParam) filters.has_scraped = true
    searchArticles(q, limit, filters)
      .then(setResults)
      .catch(() => setResults([]))
      .finally(() => setLoading(false))
  }, [q, srcParam, authorParam, fromParam, toParam, unreadParam, starredParam, scrapedParam, limit])

  // Press "/" to focus the search box
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === '/' && document.activeElement?.tagName !== 'INPUT' &&
          document.activeElement?.tagName !== 'TEXTAREA') {
        e.preventDefault()
        inputRef.current?.focus()
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [])

  const buildParams = (overrides: Record<string, string>) => {
    const base: Record<string, string> = {}
    if (inputValue.trim()) base.q = inputValue.trim()
    if (srcParam)    base.src     = srcParam
    if (authorParam) base.author  = authorParam
    if (fromParam)   base.from    = fromParam
    if (toParam)     base.to      = toParam
    if (unreadParam)  base.unread  = '1'
    if (starredParam) base.starred = '1'
    if (scrapedParam) base.scraped = '1'
    if (limit !== 50) base.limit  = String(limit)
    return { ...base, ...overrides }
  }

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    setSearchParams(buildParams({}))
  }

  const setFilter = (key: string, value: string) => {
    const params = buildParams({})
    if (value) params[key] = value
    else delete params[key]
    setSearchParams(params)
  }

  const toggleFlag = (key: string, current: boolean) =>
    setFilter(key, current ? '' : '1')

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
      {/* Search bar */}
      <form className={styles.form} onSubmit={submit}>
        <input
          ref={inputRef}
          className={styles.input}
          type="search"
          placeholder="Search articles… (press / to focus)"
          value={inputValue}
          onChange={e => setInputValue(e.target.value)}
          autoFocus
        />
        <button className={styles.btn} type="submit" disabled={!inputValue.trim() && activeFilterCount === 0}>
          Search
        </button>
      </form>

      {/* Filter bar — always visible */}
      <div className={styles.filterBar}>
        <div className={styles.filterFields}>
          <label className={styles.filterField}>
            <span className={styles.filterLabel}>Source</span>
            <select
              className={styles.filterSelect}
              value={srcParam}
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
              list="author-list"
              placeholder="Any author"
              value={authorParam}
              onChange={e => setFilter('author', e.target.value)}
            />
            <datalist id="author-list">
              {authors.map(a => <option key={a} value={a} />)}
            </datalist>
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
        </div>

        <div className={styles.filterDivider} />

        <div className={styles.filterChips}>
          <button
            type="button"
            className={`${styles.chip} ${unreadParam ? styles.chipActive : ''}`}
            onClick={() => toggleFlag('unread', unreadParam)}
            title="Show unread articles only"
          >
            Unread
          </button>
          <button
            type="button"
            className={`${styles.chip} ${starredParam ? styles.chipActive : ''}`}
            onClick={() => toggleFlag('starred', starredParam)}
            title="Show starred articles only"
          >
            ★ Starred
          </button>
          <button
            type="button"
            className={`${styles.chip} ${scrapedParam ? styles.chipActive : ''}`}
            onClick={() => toggleFlag('scraped', scrapedParam)}
            title="Show articles with fetched full text only"
          >
            ● Full text
          </button>

          <label className={styles.filterField}>
            <span className={styles.filterLabel}>Results</span>
            <select
              className={styles.filterSelect}
              value={String(limit)}
              onChange={e => setFilter('limit', e.target.value === '50' ? '' : e.target.value)}
            >
              {LIMIT_OPTIONS.map(n => <option key={n} value={String(n)}>{n}</option>)}
            </select>
          </label>

          {activeFilterCount > 0 && (
            <button type="button" className={styles.clearBtn} onClick={clearFilters}>
              Clear ({activeFilterCount})
            </button>
          )}
        </div>
      </div>

      {/* Status line */}
      {loading && <p className={styles.state}>Searching…</p>}

      {!loading && searched && results.length === 0 && (
        <p className={styles.state}>No results for &ldquo;{q}&rdquo;.</p>
      )}

      {!loading && !searched && (
        <p className={styles.hint}>Type a query above and press Search or Enter.</p>
      )}

      {!loading && results.length > 0 && (
        <>
          <p className={styles.count}>
            {results.length === limit
              ? `First ${limit} results for “${q}”`
              : `${results.length} result${results.length !== 1 ? 's' : ''} for “${q}”`}
            {activeFilterCount > 0 && (
              <span className={styles.filterNote}> &middot; {activeFilterCount} filter{activeFilterCount !== 1 ? 's' : ''} active</span>
            )}
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
                    {hit.scraped_at && (
                      <span className={styles.hitScraped} title={`Full article fetched ${formatDate(hit.scraped_at)}`}>
                        ● full text
                      </span>
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
