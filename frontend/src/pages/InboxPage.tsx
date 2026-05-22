import { useEffect, useState, useCallback } from 'react'
import { useNavigate, useLocation, useSearchParams } from 'react-router-dom'
import {
  type Article,
  type Source,
  getArticles,
  getSources,
  patchArticle,
} from '../api/client'
import ArticleRow from '../components/ArticleRow'
import styles from './InboxPage.module.css'

const PAGE_SIZE = 25

export default function InboxPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const [searchParams, setSearchParams] = useSearchParams()

  const page = parseInt(searchParams.get('page') ?? '1', 10)
  const sourceId = searchParams.get('source') ? Number(searchParams.get('source')) : undefined
  const language = searchParams.get('lang') ?? undefined
  const fromDate = searchParams.get('from') ?? undefined
  const toDate = searchParams.get('to') ?? undefined
  const unreadOnly = searchParams.get('unread') === '1'

  const [articles, setArticles] = useState<Article[]>([])
  const [total, setTotal] = useState(0)
  const [sources, setSources] = useState<Source[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getSources()
      .then(setSources)
      .catch(() => undefined)
  }, [])

  const load = useCallback(() => {
    setLoading(true)
    getArticles({
      page,
      page_size: PAGE_SIZE,
      source_id: sourceId,
      language: language || undefined,
      from_date: fromDate,
      to_date: toDate,
      is_read: unreadOnly ? false : undefined,
    })
      .then(result => {
        setArticles(result.items)
        setTotal(result.total)
      })
      .catch(() => undefined)
      .finally(() => setLoading(false))
  }, [page, sourceId, language, fromDate, toDate, unreadOnly])

  useEffect(() => {
    load()
  }, [load])

  const setParam = (key: string, value: string | undefined) => {
    setSearchParams(prev => {
      const next = new URLSearchParams(prev)
      if (value) next.set(key, value)
      else next.delete(key)
      next.delete('page')
      return next
    })
  }

  const setPage = (p: number) => {
    setSearchParams(prev => {
      const next = new URLSearchParams(prev)
      if (p === 1) next.delete('page')
      else next.set('page', String(p))
      return next
    })
  }

  const handleClick = async (article: Article) => {
    if (!article.is_read && article.id != null) {
      const updated = await patchArticle(article.id, { is_read: true }).catch(() => null)
      if (updated) {
        setArticles(prev => prev.map(a => (a.id === updated.id ? updated : a)))
      }
    }
    navigate(`/articles/${article.id}`, {
      state: { from: location.pathname + location.search },
    })
  }

  const handleStar = async (article: Article, starred: boolean) => {
    if (article.id == null) return
    const updated = await patchArticle(article.id, { is_starred: starred }).catch(() => null)
    if (updated) {
      setArticles(prev => prev.map(a => (a.id === updated.id ? updated : a)))
    }
  }

  const sourceMap = Object.fromEntries(sources.map(s => [s.id, s.name]))
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  return (
    <div>
      <div className={styles.filters}>
        <select
          className={styles.select}
          value={sourceId ?? ''}
          onChange={e => setParam('source', e.target.value || undefined)}
        >
          <option value="">All sources</option>
          {sources.map(s => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </select>

        <input
          className={styles.input}
          type="text"
          placeholder="Language (e.g. en)"
          value={language ?? ''}
          onChange={e => setParam('lang', e.target.value || undefined)}
        />

        <input
          className={styles.input}
          type="date"
          title="From date"
          value={fromDate ?? ''}
          onChange={e => setParam('from', e.target.value || undefined)}
        />

        <input
          className={styles.input}
          type="date"
          title="To date"
          value={toDate ?? ''}
          onChange={e => setParam('to', e.target.value || undefined)}
        />

        <label className={styles.check}>
          <input
            type="checkbox"
            checked={unreadOnly}
            onChange={e =>
              setSearchParams(prev => {
                const next = new URLSearchParams(prev)
                if (e.target.checked) next.set('unread', '1')
                else next.delete('unread')
                next.delete('page')
                return next
              })
            }
          />
          Unread only
        </label>
      </div>

      {loading ? (
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
                sourceName={a.source_id != null ? sourceMap[a.source_id] : undefined}
                onClick={() => void handleClick(a)}
                onStar={starred => void handleStar(a, starred)}
              />
            ))}
          </div>

          <div className={styles.pagination}>
            <button
              className={styles.pageBtn}
              disabled={page <= 1}
              onClick={() => setPage(page - 1)}
            >
              ← Prev
            </button>
            <span className={styles.pageInfo}>
              Page {page} of {totalPages} ({total} articles)
            </span>
            <button
              className={styles.pageBtn}
              disabled={page >= totalPages}
              onClick={() => setPage(page + 1)}
            >
              Next →
            </button>
          </div>
        </>
      )}
    </div>
  )
}
