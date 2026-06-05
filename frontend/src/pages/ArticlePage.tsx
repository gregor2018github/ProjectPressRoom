import { useEffect, useRef, useState } from 'react'
import { useParams, useNavigate, useLocation } from 'react-router-dom'
import { type Article, getArticle, patchArticle, formatDate } from '../api/client'
import styles from './ArticlePage.module.css'

export default function ArticlePage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const location = useLocation()
  const bodyRef = useRef<HTMLDivElement>(null)

  const [article, setArticle] = useState<Article | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)

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

  if (loading) return <p className={styles.state}>Loading…</p>
  if (error || !article) return <p className={styles.state}>Article not found.</p>

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
      </div>

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

      {article.summary && <p className={styles.summary}>{article.summary}</p>}

      {article.body_html ? (
        <div
          ref={bodyRef}
          className={styles.body}
          dangerouslySetInnerHTML={{ __html: article.body_html }}
        />
      ) : article.body_text ? (
        <div className={styles.body}>
          {article.body_text.split('\n').map((line, i) => (
            <p key={i}>{line}</p>
          ))}
        </div>
      ) : (
        <p className={styles.noBody}>No content available.</p>
      )}
    </div>
  )
}
