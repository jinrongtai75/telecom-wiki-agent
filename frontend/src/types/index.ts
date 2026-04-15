export interface SourceInfo {
  doc_id: string
  filename: string
  page: number
  section: string
  score: number
  image_path?: string
  from_3gpp: boolean
}

export interface SearchResponse {
  answer: string
  sources: SourceInfo[]
  provider: string
  history_id: string
}

export interface HistoryItem {
  id: string
  question: string
  answer: string
  sources: SourceInfo[]
  provider: string
  created_at: string
}

export interface DocumentMeta {
  id: string
  original_name: string
  file_size: number
  chunk_count: number
  status: 'processing' | 'parsing' | 'indexed' | 'error'
  uploaded_at: string
  indexed_at?: string
  markdown_path?: string
}

export interface NoiseCandidateItem {
  text: string
  count: number
  chunk_ids: string[]
}

export interface AuthState {
  accessToken: string | null
  isAdmin: boolean
  apiToken: string | null
  provider: 'jihye' | 'gemini'
  jihyeToken: string | null
  geminiToken: string | null
}

export interface UserInfo {
  id: string
  username: string
  is_admin: boolean
  created_at: string
}

export interface ParsedChunkInfo {
  id: string
  doc_id: string
  type: 'text' | 'table' | 'image' | 'summary'
  content: string
  processed_content: string | null
  page: number
  section: string
  order: number
  is_heading: boolean
  heading_level: number
  image_b64: string | null
  image_path: string | null
  bbox_json: string | null
  status: 'pending' | 'confirmed' | 'discarded'
}
