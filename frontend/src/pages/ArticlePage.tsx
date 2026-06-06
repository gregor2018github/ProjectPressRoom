import { useEffect, useRef, useState } from 'react'
import { useParams, useNavigate, useLocation } from 'react-router-dom'
import { type Article, getArticle, patchArticle, scrapeArticle, formatDate } from '../api/client'
import styles from './ArticlePage.module.css'

export default function ArticlePage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const location = useLocation()
  const bodyRef = useRef<HTMLDivElement>(null)

  const [article, setArticle] = useState<Article | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  const [scraping, setScraping] = useState(false)
  const [scrapeError, setScrapeError] = useState<string | null>(null)

  const backPath: string =
    (location.state as { from?: string } | null)?.from ?? '/'

  useEffect(() => {
    if (!id) return
    getArticle(Number(id))
      .then(setArticle)
      .catch(() => setError(true))
      .finally(() => setLoading(false))
  }, [id])

  useEffect(() => {
    if (!bodyRef.current) return
    bodyRef.current.querySelectorAll<HTMLAnchorElement>('a[href]').forEach(a => {
      a.target = '_blank'
      a.rel = 'noreferrer'
    })
  }, [article])

  const toggleStar = async () => {
    if (!article?.id) return
    const updated = await patchArticle(article.id, { is_starred: !article.is_starred }).catch(
      () => null,
    )
    if (updated) setArticle(updated)
  }

  const fetchFullArticle = async () => {
    if (!article?.id) return
    setScraping(true)
    setScrapeError(null)
    try {
      const updated = await scrapeArticle(article.id)
      setArticle(updated)
    } catch (err) {
      setScrapeError(err instanceof Error ? err.message : 'Could not fetch article')
    } finally {
      setScraping(false)
    }
  }

  if (loading) return <p className={styles.state}>Loading…</p>
  if (error || !article) return <p className={styles.state}>Article not found.</p>

  const hasScraped = !!(article.scraped_body_html || article.scraped_body_text)
  const displayHtml = hasScraped ? article.scraped_body_html : article.body_html
  const displayText = hasScraped ? article.scraped_body_text : article.body_text

  return (
    <div className={styles.page}>
      <div className={styles.toolbar}>
        <button className={styles.back} onClick={() => navigate(backPath)}>
          ← Back
        </button>
        <button
          className={`${styles.star} ${article.is_starred ? styles.starred : ''}`}
          title={article.is_starred ? 'Unstar' : 'Star'}
          onClick={() => void toggleStar()}
        >
          {article.is_starred ? '★' : '☆'}
        </button>
        <button
          className={`${styles.scrapeBtn} ${scraping ? styles.scrapeBtnBusy : ''}`}
          onClick={() => void fetchFullArticle()}
          disabled={scraping}
          title={hasScraped ? 'Re-fetch full article text' : 'Download full article text'}
        >
          {scraping ? 'Downloading…' : hasScraped ? '↻ Re-fetch article' : '⬇ Fetch full article'}
        </button>
      </div>

      {scrapeError && (
        <p className={styles.scrapeError}>{scrapeError}</p>
      )}

      <h1 className={styles.title}>{article.title}</h1>

      <div className={styles.meta}>
        {article.source_name && <span className={styles.source}>{article.source_name}</span>}
        {article.author && <span>{article.author}</span>}
        {article.published_at && <span>{formatDate(article.published_at)}</span>}
        {article.url && (
          <a href={article.url} target="_blank" rel="noreferrer" className={styles.externalLink}>
            Original ↗
          </a>
        )}
      </div>

      {article.summary && article.summary.trim() !== (article.body_text ?? '').trim() && (
        <p className={styles.summary}>{article.summary}</p>
      )}

      {hasScraped && (
        <div className={styles.scrapedBadge}>
          Full article fetched {article.scraped_at ? formatDate(article.scraped_at) : ''}
        </div>
      )}

      {displayHtml ? (
        <div
          ref={bodyRef}
          className={styles.body}
          dangerouslySetInnerHTML={{ __html: displayHtml }}
        />
      ) : displayText ? (
        <div className={styles.body}>
          {displayText.split('\n').map((line, i) => (
            <p key={i}>{line}</p>
          ))}
        </div>
      ) : (
        <p className={styles.noBody}>No content available. Use "Fetch full article" to download the text.</p>
      )}
    </div>
  )
}
