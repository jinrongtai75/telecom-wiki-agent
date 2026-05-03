import axios from 'axios';
import { message } from 'antd';
import type { DocumentObject, NoisePatterns } from '../types';

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';
const api = axios.create({ baseURL: BASE_URL });
// 에러 메시지 없이 조용히 실패하는 내부 요청용
const silentApi = axios.create({ baseURL: BASE_URL });

api.interceptors.response.use(
  (res) => res,
  async (err) => {
    // 404 문서/객체 없음 → 재업로드 안내 (서버 재시작 시 인메모리 상태 소실)
    if (err.response?.status === 404) {
      const detail = err.response?.data?.detail ?? '';
      const detailStr = typeof detail === 'string' ? detail : JSON.stringify(detail);
      if (detailStr.includes('문서') || detailStr.includes('객체') || detailStr.includes('Document') || detailStr.includes('Object')) {
        message.error('서버에서 문서를 찾을 수 없습니다. PDF를 다시 업로드해주세요.');
        return Promise.reject(err);
      }
    }
    let detail: string = err.message;
    if (err.response?.data instanceof Blob) {
      try {
        const text = await (err.response.data as Blob).text();
        const json = JSON.parse(text);
        detail = json.detail || json.error?.message || err.message;
      } catch { /* blob이 JSON이 아닌 경우 */ }
    } else if (err.response?.data?.detail) {
      detail = typeof err.response.data.detail === 'string'
        ? err.response.data.detail
        : JSON.stringify(err.response.data.detail);
    }
    message.error(detail);
    return Promise.reject(err);
  }
);

// ── Documents ────────────────────────────────────────────────────────────────
export const uploadDocument = async (file: File) => {
  const form = new FormData();
  form.append('file', file);
  const { data } = await api.post('/api/documents/upload', form);
  return data as { document_id: string; format: string; objects: DocumentObject[]; raw_content: string };
};


export const getNoiseCandidates = async (docId: string) => {
  const { data } = await silentApi.get(`/api/documents/${docId}/denoise/candidates`);
  return data as { candidates: { text: string; count: number; object_ids: string[] }[] };
};

export const denoise = async (docId: string, payload?: { delete_ids?: string[]; patterns?: NoisePatterns }) => {
  const { data } = await silentApi.post(`/api/documents/${docId}/denoise`, payload ?? null);
  return data as { objects: DocumentObject[] };
};

export const summarize = async (docId: string) => {
  const { data } = await api.post(`/api/documents/${docId}/summarize`);
  return data as { objects: DocumentObject[] };
};

export const summarizeSelection = async (docId: string, selectedIds: string[]) => {
  const { data } = await api.post(`/api/documents/${docId}/summarize-selection`, { selected_ids: selectedIds });
  return data as { objects: DocumentObject[] };
};

export const reorderObjects = async (docId: string, orderedIds: string[]) => {
  const { data } = await api.post(`/api/documents/${docId}/objects/reorder`, { ordered_ids: orderedIds });
  return data as { objects: DocumentObject[] };
};

export const addManualObject = async (
  docId: string,
  payload: { type: string; content: string; after_order?: number; bbox?: import('../types').BBox; page?: number }
) => {
  const { data } = await api.post(`/api/documents/${docId}/objects/manual`, payload);
  return data as { object: DocumentObject; objects: DocumentObject[] };
};

function parseContentDispositionFilename(cd: string): string | null {
  const rfc5987 = cd.match(/filename\*=UTF-8''([^;\s]+)/i)
  if (rfc5987) {
    try { return decodeURIComponent(rfc5987[1]) } catch { /* ignore */ }
  }
  const simple = cd.match(/filename="(.+?)"/)
  return simple ? simple[1] : null
}

export const exportDocument = async (
  docId: string,
  force = false,
  savePath?: string,
  filename?: string,
) => {
  const res = await api.get(`/api/documents/${docId}/export`, {
    params: { force, save_path: savePath || undefined, filename: filename || undefined },
    responseType: 'blob',
  });
  const blob = new Blob([res.data], { type: 'text/markdown' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  // 전달된 filename 우선 사용, 없으면 헤더 파싱 (RFC 5987 + simple 형식 모두 지원)
  let downloadName = filename ? (filename.endsWith('.md') ? filename : `${filename}.md`) : ''
  if (!downloadName) {
    downloadName = parseContentDispositionFilename(res.headers['content-disposition'] || '') ?? 'document.md'
  }
  a.download = downloadName;
  a.click();
  URL.revokeObjectURL(url);
};

/** MD 내용을 텍스트로 가져옴 (RAG 적재용) */
export const exportDocumentContent = async (docId: string, force = false): Promise<{ content: string; filename: string }> => {
  const res = await api.get(`/api/documents/${docId}/export`, {
    params: { force },
    responseType: 'text',
  });
  const cd = res.headers['content-disposition'] || '';
  return { content: res.data as string, filename: parseContentDispositionFilename(cd) ?? 'document.md' };
};

// ── Wiki Agent RAG 적재 (전처리 백엔드 프록시 경유) ──────────────────────────
export const ingestToWikiAgent = async (
  docId: string,
  content: string,
  filename: string,
  sourceName?: string,
): Promise<{ doc_id: string; chunk_count: number; has_pdf: boolean }> => {
  const form = new FormData();
  form.append('filename', filename);
  form.append('content', content);
  form.append('source_name', sourceName || filename);

  try {
    const pdfRes = await silentApi.get(`/api/documents/${docId}/file`, { responseType: 'arraybuffer' });
    const pdfName = sourceName || filename;
    const pdfBlob = new Blob([pdfRes.data], { type: 'application/pdf' });
    form.append('pdf_file', pdfBlob, pdfName.endsWith('.pdf') ? pdfName : pdfName.replace(/\.[^.]+$/, '.pdf'));
  } catch {
    // PDF 없이 계속 진행
  }

  const { data } = await api.post('/api/ingest/to-wiki', form);
  return data as { doc_id: string; chunk_count: number; has_pdf: boolean };
};


// ── Objects ───────────────────────────────────────────────────────────────────
export const processTable = async (docId: string, objId: string) => {
  const { data } = await api.post(`/api/objects/${docId}/${objId}/table/process`);
  return data as { processed_content: string };
};

export const flattenTable = async (docId: string, objId: string) => {
  const { data } = await api.post(`/api/objects/${docId}/${objId}/table/flatten`);
  return data as { processed_content: string };
};

export const reviewTable = async (docId: string, objId: string) => {
  const { data } = await silentApi.post(`/api/objects/${docId}/${objId}/table/review`);
  return data as { action: 'keep' | 'flatten'; processed_content: string };
};

export const reviewImage = async (docId: string, objId: string) => {
  const { data } = await silentApi.post(`/api/objects/${docId}/${objId}/image/review`);
  return data as
    | { action: 'discard'; objects: import('../types').DocumentObject[] }
    | { action: 'save'; processed_content: string; image_path: string }
    | { action: 'describe'; processed_content: string };
};

export const chatTable = async (docId: string, objId: string, msg: string) => {
  const { data } = await api.post(`/api/objects/${docId}/${objId}/table/chat`, { message: msg });
  return data as { processed_content: string };
};

export const linkImage = async (docId: string, objId: string, target_text: string) => {
  const { data } = await api.post(`/api/objects/${docId}/${objId}/image/link`, { target_text });
  return data as { image_path: string; processed_content: string };
};

export const interpretImage = async (docId: string, objId: string) => {
  const { data } = await api.post(`/api/objects/${docId}/${objId}/image/interpret`);
  return data as { processed_content: string; image_path: string | null };
};

export const chatImage = async (docId: string, objId: string, msg: string) => {
  const { data } = await api.post(`/api/objects/${docId}/${objId}/image/chat`, { message: msg });
  return data as { processed_content: string };
};

export const confirmObject = async (
  docId: string,
  objId: string,
  payload?: { processed_content?: string; is_heading?: boolean }
) => {
  const { data } = await api.post(`/api/objects/${docId}/${objId}/confirm`, payload ?? {});
  return data as { id: string; confirm_status: string; processed_content: string };
};

export const updateContent = async (
  docId: string,
  objId: string,
  payload: { content?: string; processed_content?: string }
) => {
  const { data } = await api.patch(`/api/objects/${docId}/${objId}/content`, payload);
  return data as { id: string; content: string; processed_content: string };
};

export const setHeading = async (docId: string, objId: string, is_heading: boolean) => {
  const { data } = await api.post(`/api/objects/${docId}/${objId}/heading`, { is_heading });
  return data as { id: string; is_heading: boolean };
};

export const deleteObject = async (docId: string, objId: string) => {
  const { data } = await silentApi.delete(`/api/objects/${docId}/${objId}`);
  return data as { objects: DocumentObject[] };
};

export const deleteObjects = async (docId: string, ids: string[]) => {
  const { data } = await silentApi.post(`/api/documents/${docId}/denoise`, { delete_ids: ids });
  return data as { objects: DocumentObject[] };
};

// ── RAG 적재 현황 ─────────────────────────────────────────────────────────────
export interface RagDocument {
  id: string;
  original_name: string;
  filename: string;
  status: string;
  chunk_count: number | null;
  indexed_at: string | null;
}

export const listRagDocuments = async () => {
  const { data } = await api.get('/api/ingest/rag-documents');
  return data as RagDocument[];
};

// ── Settings ──────────────────────────────────────────────────────────────────
export const listKeys = async () => {
  const { data } = await api.get('/api/settings/keys');
  return data as Record<string, boolean>;
};

export const saveKey = async (service: string, api_key: string) => {
  const { data } = await api.post('/api/settings/keys', { service, api_key });
  return data;
};

export const validateKey = async (service: string) => {
  const { data } = await api.post('/api/settings/keys/validate', { service });
  return data as { valid: boolean };
};
