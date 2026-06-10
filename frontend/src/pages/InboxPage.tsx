import { useCallback, useEffect, useRef, useState } from 'react'
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import {
  type Article,
  type ArticleSearchHit,
  type SearchFilters,
  type Source,
  formatDate,
  getArticles,
  getAuthors,
  getSources,
  patchArticle,
  searchArticles,
} from '../api/client'
import ArticleRow from '../components/ArticleRow'
import styles from './InboxPage.module.css'

const PAGE_SIZE = 25
const LIMIT_OPTIONS = [50, 100, 200] as const
type Limit = (typeof LIMIT_OPTIONS)[number]

export default function InboxPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const [searchParams, setSearchParams] = useSearchParams()

  // ── Inbox params ──────────────────────────────────────────────────────────
  const page       = parseInt(searchParams.get('page') ?? '1', 10)
  const sourceId   = searchParams.get('source') ? Number(searchParams.get('source')) : undefined
  const language   = searchParams.get('lang') ?? undefined
  const fromDate   = searchParams.get('from') ?? undefined
  const toDate     = searchParams.get('to') ?? undefined
  const unreadOnly = searchParams.get('unread') === '1'

  // ── Search params (separate namespace: sfrom/sto/sunread to avoid collision) ──
  const q            = searchParams.get('q') ?? ''
  const srcParam     = searchParams.get('src') ?? ''
  const authorParam  = searchParams.get('author') ?? ''
  const fromParam    = searchParams.get('sfrom') ?? ''
  const toParam      = searchParams.get('sto') ?? ''
  const unreadParam  = searchParams.get('sunread') === '1'
  const starredParam = searchParams.get('starred') === '1'
  const scrapedParam = searchParams.get('scraped') === '1'
  const limitNum     = Number(searchParams.get('limit') ?? '50')
  const limit        = (LIMIT_OPTIONS.includes(limitNum as Limit) ? limitNum : 50) as Limit

  const activeFilterCount = [srcParam, authorParam, fromParam, toParam,
    unreadParam, starredParam, scrapedParam].filter(Boolean).length

  // ── UI state ───────────────────────────────────────────────────────────────
  const [searchOpen, setSearchOpen] = useState(() => !!q)
  const [inputValue, setInputValue] = useState(q)
  const searchInputRef = useRef<HTMLInputElement>(null)

  // ── Shared data ───────────────────────────────────────────────────────────
  const [sources, setSources] = useState<Source[]>([])
  const [sourceMap, setSourceMap] = useState<Map<number, string>>(new Map())
  const [authors, setAuthors] = useState<string[]>([])

  // ── Inbox data ────────────────────────────────────────────────────────────
  const [articles, setArticles] = useState<Article[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)

  // ── Search data ───────────────────────────────────────────────────────────
  const [results, setResults] = useState<ArticleSearchHit[]>([])
  const [searchLoading, setSearchLoading] = useState(false)
  const [searched, setSearched] = useState(!!q)

  useEffect(() => {
    getSources()
      .then(list => {
        setSources(list)
        setSourceMap(new Map(list.map((s: Source) => [s.id, s.name])))
      })
      .catch(() => undefined)
    getAuthors().then(setAuthors).catch(() => undefined)
  }, [])

  // Sync open state when q appears in URL (e.g. back navigation)
  useEffect(() => {
    if (q && !searchOpen) { setSearchOpen(true); setInputValue(q) }
  }, [q]) // eslint-disable-line react-hooks/exhaustive-deps

  // Focus search input whenever panel opens
  useEffect(() => {
    if (searchOpen) setTimeout(() => searchInputRef.current?.focus(), 30)
  }, [searchOpen])

  // '/' shortcut: open panel if closed, otherwise refocus input
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key !== '/' ||
          document.activeElement?.tagName === 'INPUT' ||
          document.activeElement?.tagName === 'TEXTAREA') return
      e.preventDefault()
      if (!searchOpen) setSearchOpen(true)
      else searchInputRef.current?.focus()
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [searchOpen])

  // ── Inbox load ────────────────────────────────────────────────────────────
  const loadInbox = useCallback(() => {
    if (searchOpen) return
    setLoading(true)
    getArticles({
      page, page_size: PAGE_SIZE,
      source_id: sourceId,
      language: language || undefined,
      from_date: fromDate,
      to_date: toDate,
      is_read: unreadOnly ? false : undefined,
    })
      .then(r => { setArticles(r.items); setTotal(r.total) })
      .catch(() => undefined)
      .finally(() => setLoading(false))
  }, [searchOpen, page, sourceId, language, fromDate, toDate, unreadOnly])

  useEffect(() => { loadInbox() }, [loadInbox])

  // ── Search run ────────────────────────────────────────────────────────────
  useEffect(() => {
    if (!searchOpen) return
    const hasFilters = Boolean(srcParam || authorParam || fromParam || toParam ||
      unreadParam || starredParam || scrapedParam)
    if (!q && !hasFilters) { setResults([]); setSearched(false); return }
    setSearchLoading(true)
    setSearched(true)
    const filters: SearchFilters = {}
    if (srcParam)     filters.source_id   = Number(srcParam)
    if (authorParam)  filters.author      = authorParam
    if (fromParam)    filters.from_date   = fromParam
    if (toParam)      filters.to_date     = toParam
    if (unreadParam)  filters.is_unread   = true
    if (starredParam) filters.is_starred  = true
    if (scrapedParam) filters.has_scraped = true
    searchArticles(q, limit, filters)
      .then(setResults)
      .catch(() => setResults([]))
      .finally(() => setSearchLoading(false))
  }, [searchOpen, q, srcParam, authorParam, fromParam, toParam,
      unreadParam, starredParam, scrapedParam, limit])

  // ── Inbox param helpers ───────────────────────────────────────────────────
  const setInboxParam = (key: string, value: string | undefined) => {
    setSearchParams(prev => {
      const next = new URLSearchParams(prev)
      if (value) next.set(key, value); else next.delete(key)
      next.delete('page')
      return next
    })
  }

  const setPage = (p: number) => {
    setSearchParams(prev => {
      const next = new URLSearchParams(prev)
      if (p === 1) next.delete('page'); else next.set('page', String(p))
      return next
    })
  }

  // ── Search param helpers ──────────────────────────────────────────────────
  const buildSearchParams = (overrides: Record<string, string>) => {
    const base: Record<string, string> = {}
    if (inputValue.trim()) base.q       = inputValue.trim()
    if (srcParam)          base.src     = srcParam
    if (authorParam)       base.author  = authorParam
    if (fromParam)         base.sfrom   = fromParam
    if (toParam)           base.sto     = toParam
    if (unreadParam)       base.sunread = '1'
    if (starredParam)      base.starred = '1'
    if (scrapedParam)      base.scraped = '1'
    if (limit !== 50)      base.limit   = String(limit)
    // preserve inbox-specific params so they survive mode switches
    const inboxSrc  = searchParams.get('source')
    const inboxLang = searchParams.get('lang')
    if (inboxSrc)  base.source = inboxSrc
    if (inboxLang) base.lang   = inboxLang
    return { ...base, ...overrides }
  }

  const submitSearch = (e: React.FormEvent) => {
    e.preventDefault()
    setSearchParams(buildSearchParams({}))
  }

  const setSearchFilter = (key: string, value: string) => {
    const params = buildSearchParams({})
    if (value) params[key] = value; else delete params[key]
    setSearchParams(params)
  }

  const toggleSearchFlag = (key: string, current: boolean) =>
    setSearchFilter(key, current ? '' : '1')

  const clearSearchFilters = () => {
    const base: Record<string, string> = {}
    if (q) base.q = q
    const inboxSrc  = searchParams.get('source')
    const inboxLang = searchParams.get('lang')
    if (inboxSrc)  base.source = inboxSrc
    if (inboxLang) base.lang   = inboxLang
    setSearchParams(base)
  }

  const closeSearch = () => {
    setSearchOpen(false)
    setInputValue('')
    setResults([])
    setSearched(false)
    setSearchParams(prev => {
      const next = new URLSearchParams(prev)
      for (const k of ['q', 'src', 'author', 'sfrom', 'sto', 'sunread', 'starred', 'scraped', 'limit'])
        next.delete(k)
      return next
    })
  }

  // ── Article interactions ──────────────────────────────────────────────────
  const handleInboxClick = async (article: Article) => {
    if (!article.is_read && article.id != null) {
      const updated = await patchArticle(article.id, { is_read: true }).catch(() => null)
      if (updated) setArticles(prev => prev.map(a => a.id === updated.id ? updated : a))
    }
    navigate(`/articles/${article.id}`, { state: { from: location.pathname + location.search } })
  }

  const handleInboxStar = async (article: Article, starred: boolean) => {
    if (article.id == null) return
    const updated = await patchArticle(article.id, { is_starred: starred }).catch(() => null)
    if (updated) setArticles(prev => prev.map(a => a.id === updated.id ? updated : a))
  }

  const handleSearchClick = async (hit: ArticleSearchHit) => {
    if (!hit.is_read && hit.id != null)
      await patchArticle(hit.id, { is_read: true }).catch(() => null)
    navigate(`/articles/${hit.id}`, { state: { from: location.pathname + location.search } })
  }

  const handleSearchStar = async (hit: ArticleSearchHit, starred: boolean) => {
    if (hit.id == null) return
    const updated = await patchArticle(hit.id, { is_starred: starred }).catch(() => null)
    if (updated) setResults(prev => prev.map(r => r.id === updated.id ? { ...r, ...updated } : r))
  }

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  return (
    <div>
      {/* ── Top row: inbox filters (inbox mode only) + search toggle ──────── */}
      <div className={styles.topRow}>
        {!searchOpen && (
          <div className={styles.filters}>
            <select
              className={styles.select}
              value={sourceId ?? ''}
              onChange={e => setInboxParam('source', e.target.value || undefined)}
            >
              <option value="">All sources</option>
              {sources.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>

            <input
              className={styles.input}
              type="text"
              placeholder="Language (e.g. en)"
              value={language ?? ''}
              onChange={e => setInboxParam('lang', e.target.value || undefined)}
            />

            <input
              className={styles.input}
              type="date"
              title="From date"
              value={fromDate ?? ''}
              onChange={e => setInboxParam('from', e.target.value || undefined)}
            />

            <input
              className={styles.input}
              type="date"
              title="To date"
              value={toDate ?? ''}
              onChange={e => setInboxParam('to', e.target.value || undefined)}
            />

            <label className={styles.check}>
              <input
                type="checkbox"
                checked={unreadOnly}
                onChange={e =>
                  setSearchParams(prev => {
                    const next = new URLSearchParams(prev)
                    if (e.target.checked) next.set('unread', '1'); else next.delete('unread')
                    next.delete('page')
                    return next
                  })
                }
              />
              Unread only
            </label>
          </div>
        )}

        <button
          className={`${styles.searchToggle} ${searchOpen ? styles.searchToggleActive : ''}`}
          onClick={() => searchOpen ? closeSearch() : setSearchOpen(true)}
          title={searchOpen ? 'Close search' : 'Search articles (press /)'}
          aria-expanded={searchOpen}
        >
          {searchOpen ? '✕ Close search' : '🔍 Search'}
        </button>
      </div>

      {/* ── Search panel ─────────────────────────────────────────────────── */}
      {searchOpen && (
        <div className={styles.searchPanel}>
          <form className={styles.searchForm} onSubmit={submitSearch}>
            <input
              ref={searchInputRef}
              className={styles.searchInput}
              type="search"
              placeholder="Search articles… (press / to focus)"
              value={inputValue}
              onChange={e => setInputValue(e.target.value)}
            />
            <button
              className={styles.searchBtn}
              type="submit"
              disabled={!inputValue.trim() && activeFilterCount === 0}
            >
              Search
            </button>
          </form>

          <div className={styles.filterBar}>
            <div className={styles.filterFields}>
              <label className={styles.filterField}>
                <span className={styles.filterLabel}>Source</span>
                <select
                  className={styles.filterSelect}
                  value={srcParam}
                  onChange={e => setSearchFilter('src', e.target.value)}
                >
                  <option value="">All sources</option>
                  {sources.map(s => <option key={s.id} value={String(s.id)}>{s.name}</option>)}
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
                  onChange={e => setSearchFilter('author', e.target.value)}
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
                  onChange={e => setSearchFilter('sfrom', e.target.value)}
                />
              </label>

              <label className={styles.filterField}>
                <span className={styles.filterLabel}>To</span>
                <input
                  className={styles.filterInput}
                  type="date"
                  value={toParam}
                  onChange={e => setSearchFilter('sto', e.target.value)}
                />
              </label>
            </div>

            <div className={styles.filterDivider} />

            <div className={styles.filterChips}>
              <button
                type="button"
                className={`${styles.chip} ${unreadParam ? styles.chipActive : ''}`}
                onClick={() => toggleSearchFlag('sunread', unreadParam)}
              >
                Unread
              </button>
              <button
                type="button"
                className={`${styles.chip} ${starredParam ? styles.chipActive : ''}`}
                onClick={() => toggleSearchFlag('starred', starredParam)}
              >
                ★ Starred
              </button>
              <button
                type="button"
                className={`${styles.chip} ${scrapedParam ? styles.chipActive : ''}`}
                onClick={() => toggleSearchFlag('scraped', scrapedParam)}
              >
                ● Full text
              </button>

              <label className={styles.filterField}>
                <span className={styles.filterLabel}>Results</span>
                <select
                  className={styles.filterSelect}
                  value={String(limit)}
                  onChange={e => setSearchFilter('limit', e.target.value === '50' ? '' : e.target.value)}
                >
                  {LIMIT_OPTIONS.map(n => <option key={n} value={String(n)}>{n}</option>)}
                </select>
              </label>

              {activeFilterCount > 0 && (
                <button type="button" className={styles.clearBtn} onClick={clearSearchFilters}>
                  Clear ({activeFilterCount})
                </button>
              )}
            </div>
          </div>

          {searchLoading && <p className={styles.state}>Searching…</p>}
          {!searchLoading && searched && results.length === 0 && (
            <p className={styles.state}>No results{q ? ` for "${q}"` : ''}.</p>
          )}
          {!searchLoading && !searched && (
            <p className={styles.hint}>Type a query and press Search, or apply filters.</p>
          )}
          {!searchLoading && results.length > 0 && (
            <>
              <p className={styles.resultCount}>
                {results.length === limit
                  ? `First ${limit} results${q ? ` for "${q}"` : ''}`
                  : `${results.length} result${results.length !== 1 ? 's' : ''}${q ? ` for "${q}"` : ''}`}
                {activeFilterCount > 0 && (
                  <span className={styles.filterNote}>
                    {' '}· {activeFilterCount} filter{activeFilterCount !== 1 ? 's' : ''} active
                  </span>
                )}
              </p>
              <div className={styles.hitList}>
                {results.map(hit => (
                  <div
                    key={hit.id}
                    className={`${styles.hit} ${hit.is_read ? styles.hitRead : ''}`}
                    role="button"
                    tabIndex={0}
                    onClick={() => void handleSearchClick(hit)}
                    onKeyDown={e => e.key === 'Enter' && void handleSearchClick(hit)}
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
                          <span className={styles.hitScraped}
                            title={`Full article fetched ${formatDate(hit.scraped_at)}`}>
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
                      onClick={e => { e.stopPropagation(); void handleSearchStar(hit, !hit.is_starred) }}
                    >
                      {hit.is_starred ? '★' : '☆'}
                    </button>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      )}

      {/* ── Inbox article list ────────────────────────────────────────────── */}
      {!searchOpen && (
        loading ? (
          <p className={styles.empty}>Loading…</p>
        ) : articles.length === 0 ? (
          <p className={styles.empty}>No articles found.</p>
        ) : (
          <>
            <div className={styles.list}>
              {articles.map(a => (
                <ArticleRow
                  key={a.id}
                  article={a}
                  sourceName={a.source_name ?? undefined}
                  onClick={() => void handleInboxClick(a)}
                  onStar={starred => void handleInboxStar(a, starred)}
                />
              ))}
            </div>
            <div className={styles.pagination}>
              <button className={styles.pageBtn} disabled={page <= 1} onClick={() => setPage(page - 1)}>
                ← Prev
              </button>
              <span className={styles.pageInfo}>
                Page {page} of {totalPages} ({total} articles)
              </span>
              <button className={styles.pageBtn} disabled={page >= totalPages} onClick={() => setPage(page + 1)}>
                Next →
              </button>
            </div>
          </>
        )
      )}
    </div>
  )
}
