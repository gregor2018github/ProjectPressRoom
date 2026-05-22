import { type Article, formatDate } from '../api/client'
import styles from './ArticleRow.module.css'

interface Props {
  article: Article
  sourceName?: string
  onClick: () => void
  onStar: (starred: boolean) => void
}

export default function ArticleRow({ article, sourceName, onClick, onStar }: Props) {
  return (
    <div
      className={`${styles.row} ${article.is_read ? styles.read : ''}`}
      onClick={onClick}
      role="button"
      tabIndex={0}
      onKeyDown={e => e.key === 'Enter' && onClick()}
    >
      <div className={styles.body}>
        <div className={styles.meta}>
          {sourceName && <span className={styles.source}>{sourceName}</span>}
          {article.author && <span className={styles.author}>{article.author}</span>}
          {article.published_at && (
            <span className={styles.date}>{formatDate(article.published_at)}</span>
          )}
        </div>
        <h3 className={styles.title}>{article.title}</h3>
        {article.summary && <p className={styles.summary}>{article.summary}</p>}
      </div>
      <button
        className={`${styles.star} ${article.is_starred ? styles.starred : ''}`}
        title={article.is_starred ? 'Unstar' : 'Star'}
        onClick={e => {
          e.stopPropagation()
          onStar(!article.is_starred)
        }}
      >
        {article.is_starred ? '★' : '☆'}
      </button>
    </div>
  )
}
