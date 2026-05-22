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

export const getHealth = () => req<Health>('/api/health')

export const getSources = () => req<Source[]>('/api/sources')

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

export const searchArticles = (q: string, limit = 50) =>
  req<ArticleSearchHit[]>(`/api/articles/search?q=${encodeURIComponent(q)}&limit=${limit}`)

export const patchArticle = (id: number, body: { is_read?: boolean; is_starred?: boolean }) =>
  req<Article>(`/api/articles/${id}`, { method: 'PATCH', ...json(body) })

export const getRuns = (limit = 50) => req<FetchRun[]>(`/api/runs?limit=${limit}`)

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const dtFmt = new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' })
export const formatDate = (iso: string | null | undefined): string =>
  iso ? dtFmt.format(new Date(iso)) : ''
