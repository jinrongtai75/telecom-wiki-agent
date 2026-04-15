import axios from 'axios'
import type { DocumentMeta, HistoryItem, NoiseCandidateItem, ParsedChunkInfo, SearchResponse, SourceInfo, UserInfo } from '../types'

const API_BASE = import.meta.env.VITE_API_URL ?? ''

const client = axios.create({ baseURL: `${API_BASE}/api`, timeout: 120_000 })  // 2분 기본 타임아웃

// JWT 토큰 자동 첨부
client.interceptors.request.use((config) => {
  const token = sessionStorage.getItem('access_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

export type StreamEvent =
  | { type: 'sources'; data: SourceInfo[] }
  | { type: 'token'; data: string }
  | { type: 'done'; data: { history_id: string } }
  | { type: 'error'; data: string }

export function searchStream(
  question: string,
  provider: string,
  apiToken: string,
  onEvent: (event: StreamEvent) => void,
): () => void {
  const token = sessionStorage.getItem('access_token') ?? ''
  let aborted = false
  const controller = new AbortController()

  fetch(`${API_BASE}/api/search/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ question, provider, api_token: apiToken }),
    signal: controller.signal,
  })
    .then(async (res) => {
      if (!res.ok || !res.body) {
        onEvent({ type: 'error', data: `HTTP ${res.status}` })
        return
      }
      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buf = ''

      while (!aborted) {
        const { done, value } = await reader.read()
        if (done) break
        buf += decoder.decode(value, { stream: true })
        const lines = buf.split('\n')
        buf = lines.pop() ?? ''
        for (const line of lines) {
          if (!line.startsWith('data:')) continue
          const raw = line.slice(5).trim()
          if (!raw || raw === '[DONE]') continue
          try {
            onEvent(JSON.parse(raw) as StreamEvent)
          } catch {
            // ignore malformed
          }
        }
      }
    })
    .catch((err) => {
      if (!aborted) onEvent({ type: 'error', data: String(err) })
    })

  return () => {
    aborted = true
    controller.abort()
  }
}

export const api = {
  // Auth
  login: (username: string, password: string) =>
    client.post<{ access_token: string; is_admin: boolean }>('/auth/login', { username, password }),

  // Users (admin)
  getUsers: () =>
    client.get<UserInfo[]>('/admin/users'),

  createUser: (username: string, password: string, is_admin = false) =>
    client.post<UserInfo>('/admin/users', { username, password, is_admin }),

  deleteUser: (id: string) =>
    client.delete(`/admin/users/${id}`),

  // Search
  search: (question: string, provider: string, apiToken: string) =>
    client.post<SearchResponse>('/search', { question, provider, api_token: apiToken }),

  // History
  getHistory: (limit = 50) =>
    client.get<HistoryItem[]>(`/history?limit=${limit}`),

  deleteHistory: (id: string) =>
    client.delete(`/history/${id}`),

  deleteAllHistory: () =>
    client.delete('/history'),

  submitFeedback: (historyId: string, rating: 1 | -1) =>
    client.post('/history/feedback', { history_id: historyId, rating }),

  // Documents (admin)
  getDocuments: () =>
    client.get<DocumentMeta[]>('/documents'),

  uploadDocument: (file: File, _provider?: string, _apiToken?: string) => {
    const form = new FormData()
    form.append('file', file)
    return client.post<DocumentMeta>('/documents', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },

  deleteDocument: (id: string) =>
    client.delete(`/documents/${id}`),

  indexDocument: (docId: string, provider: string, apiToken: string) =>
    client.post<DocumentMeta>(`/documents/${docId}/index`, { provider, api_token: apiToken }, { timeout: 600_000 }),  // 10분 (임베딩 모델 로딩 포함)

  reparseDocument: (docId: string) =>
    client.post<DocumentMeta>(`/documents/${docId}/reparse`),

  summarizeDocument: (docId: string, provider: string, apiToken: string) =>
    client.post<{ inserted: number }>(`/documents/${docId}/summarize`, { provider, api_token: apiToken }, { timeout: 300_000 }),  // 5분 (LLM 호출 多)

  getNoiseCandidates: (docId: string, customPatterns?: string[]) =>
    client.post<{ candidates: NoiseCandidateItem[] }>(`/documents/${docId}/noise/candidates`, customPatterns ?? []),

  getMarkdown: (docId: string) =>
    client.get<string>(`/documents/${docId}/markdown`),

  // Chunks (admin)
  getChunks: (docId: string) =>
    client.get<ParsedChunkInfo[]>(`/chunks/${docId}`),

  updateChunk: (docId: string, chunkId: string, body: { content?: string; processed_content?: string; is_heading?: boolean }) =>
    client.put<ParsedChunkInfo>(`/chunks/${docId}/${chunkId}`, body),

  deleteChunk: (docId: string, chunkId: string) =>
    client.delete(`/chunks/${docId}/${chunkId}`),

  confirmChunk: (docId: string, chunkId: string) =>
    client.post<ParsedChunkInfo>(`/chunks/${docId}/${chunkId}/confirm`),

  reorderChunks: (docId: string, orderedIds: string[]) =>
    client.post(`/chunks/${docId}/reorder`, { ordered_ids: orderedIds }),

  tableReview: (docId: string, chunkId: string, provider: string, apiToken: string) =>
    client.post<ParsedChunkInfo>(`/chunks/${docId}/${chunkId}/table/review`, { provider, api_token: apiToken }),

  tableFlatten: (docId: string, chunkId: string, provider: string, apiToken: string) =>
    client.post<ParsedChunkInfo>(`/chunks/${docId}/${chunkId}/table/flatten`, { provider, api_token: apiToken }),

  tableChat: (docId: string, chunkId: string, message: string, provider: string, apiToken: string) =>
    client.post<ParsedChunkInfo>(`/chunks/${docId}/${chunkId}/table/chat`, { message, provider, api_token: apiToken }),

  imageReview: (docId: string, chunkId: string, provider: string, apiToken: string) =>
    client.post<ParsedChunkInfo>(`/chunks/${docId}/${chunkId}/image/review`, { provider, api_token: apiToken }),

  imageChat: (docId: string, chunkId: string, message: string, provider: string, apiToken: string) =>
    client.post<ParsedChunkInfo>(`/chunks/${docId}/${chunkId}/image/chat`, { message, provider, api_token: apiToken }),
}
