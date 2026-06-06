// Typed API client — one function per endpoint.

const BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? ''

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, init)
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json() as Promise<T>
}

const json = (body: unknown): RequestInit => ({
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
})

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface Source {
  id: number
  name: string
  feed_url: string
  feed_type: 'rss' | 'atom' | 'scraped'
  homepage_url: string | null
  category: string | null
  language: string | null
  is_active: boolean
  fetch_interval_minutes: number
  last_etag: string | null
  last_modified: string | null
  last_fetched_at: string | null
  last_status: 'ok' | 'error' | 'not_modified' | null
  last_error: string | null
  created_at: string | null
  updated_at: string | null
  // SourceResponse enrichment
  last_run_status: 'running' | 'ok' | 'error' | 'not_modified' | null
  last_run_articles_new: number | null
  last_run_finished_at: string | null
}

export interface Article {
  id: number | null
  source_id: number
  external_id: string
  url: string
  title: string
  summary: string | null
  body_html: string | null
  body_text: string | null
  body_html_raw: string | null
  author: string | null
  language: string | null
  published_at: string | null
  fetched_at: string | null
  content_hash: string
  is_read: boolean
  is_starred: boolean
  scraped_body_html: string | null
  scraped_body_text: string | null
  scraped_at: string | null
  source_name: string | null
}

export interface ArticleSearchHit extends Article {
  snippet: string
}

export interface ArticlePage {
  items: Article[]
  total: number
  page: number
  page_size: number
}

export interface FetchRun {
  id: number | null
  source_id: number
  triggered_by: 'scheduler' | 'manual' | 'cli'
  started_at: string | null
  finished_at: string | null
  status: 'running' | 'ok' | 'error' | 'not_modified'
  http_status: number | null
  articles_seen: number
  articles_new: number
  articles_duplicate: number
  error_message: string | null
}

export interface Health {
  status: string
  articles: number
}

// ---------------------------------------------------------------------------
// API functions
// ---------------------------------------------------------------------------

export interface DbStats {
  articles_total: number
  articles_unread: number
  articles_starred: number
  oldest_fetched_at: string | null
  newest_fetched_at: string | null
  sources_total: number
  sources_active: number
  fetch_runs_total: number
  db_size_bytes: number
}

export const getHealth = () => req<Health>('/api/health')
export const getStats = () => req<DbStats>('/api/stats')

export interface SyncResult {
  synced: number
  sources: Source[]
}

export const getSources = () => req<Source[]>('/api/sources')

export const syncSources = () =>
  req<SyncResult>('/api/sources/sync', { method: 'POST' })

export const patchSource = (id: number, body: { is_active?: boolean; fetch_interval_minutes?: number }) =>
  req<Source>(`/api/sources/${id}`, { method: 'PATCH', ...json(body) })

export const triggerFetch = (id: number) =>
  req<FetchRun>(`/api/sources/${id}/fetch`, { method: 'POST' })

export interface ArticleFilters {
  source_id?: number
  language?: string
  from_date?: string
  to_date?: string
  is_read?: boolean
  is_starred?: boolean
  page?: number
  page_size?: number
}

export const getArticles = (filters: ArticleFilters = {}) => {
  const p = new URLSearchParams()
  for (const [k, v] of Object.entries(filters)) {
    if (v !== undefined && v !== '') p.set(k, String(v))
  }
  return req<ArticlePage>(`/api/articles?${p}`)
}

export const getArticle = (id: number) => req<Article>(`/api/articles/${id}`)

export interface SearchFilters {
  source_id?: number
  author?: string
  from_date?: string
  to_date?: string
}

export const searchArticles = (q: string, limit = 50, filters: SearchFilters = {}) => {
  const p = new URLSearchParams({ q, limit: String(limit) })
  if (filters.source_id !== undefined) p.set('source_id', String(filters.source_id))
  if (filters.author) p.set('author', filters.author)
  if (filters.from_date) p.set('from_date', filters.from_date)
  if (filters.to_date) p.set('to_date', filters.to_date)
  return req<ArticleSearchHit[]>(`/api/articles/search?${p}`)
}

export const patchArticle = (id: number, body: { is_read?: boolean; is_starred?: boolean }) =>
  req<Article>(`/api/articles/${id}`, { method: 'PATCH', ...json(body) })

export const scrapeArticle = async (id: number): Promise<Article> => {
  const res = await fetch(`${BASE}/api/articles/${id}/scrape`, { method: 'POST' })
  if (!res.ok) {
    const body = await res.json().catch(() => null) as { detail?: string } | null
    throw new Error(body?.detail ?? `${res.status} ${res.statusText}`)
  }
  return res.json() as Promise<Article>
}

export const getRuns = (limit = 50) => req<FetchRun[]>(`/api/runs?limit=${limit}`)

export const shutdownApp = () =>
  req<{ status: string }>('/api/shutdown', { method: 'POST' })

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const dtFmt = new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' })
export const formatDate = (iso: string | null | undefined): string =>
  iso ? dtFmt.format(new Date(iso)) : ''
