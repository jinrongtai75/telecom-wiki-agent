import axios from 'axios';
import { message } from 'antd';
import type { DocumentObject, NoisePatterns } from '../types';

const api = axios.create({ baseURL: import.meta.env.VITE_API_URL ?? 'http://localhost:8000' });

api.interceptors.response.use(
  (res) => res,
  (err) => {
    const detail = err.response?.data?.detail || err.message;
    message.error(typeof detail === 'string' ? detail : JSON.stringify(detail));
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
  const { data } = await api.get(`/api/documents/${docId}/denoise/candidates`);
  return data as { candidates: { text: string; count: number; object_ids: string[] }[] };
};

export const denoise = async (docId: string, payload?: { delete_ids?: string[]; patterns?: NoisePatterns }) => {
  const { data } = await api.post(`/api/documents/${docId}/denoise`, payload ?? null);
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
  const cd = res.headers['content-disposition'] || '';
  const match = cd.match(/filename="(.+?)"/);
  a.download = match ? match[1] : 'document.md';
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
  const match = cd.match(/filename="(.+?)"/);
  return { content: res.data as string, filename: match ? match[1] : 'document.md' };
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
    const pdfRes = await api.get(`/api/documents/${docId}/file`, { responseType: 'arraybuffer' });
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
  const { data } = await api.post(`/api/objects/${docId}/${objId}/table/review`);
  return data as { action: 'keep' | 'flatten'; processed_content: string };
};

export const reviewImage = async (docId: string, objId: string) => {
  const { data } = await api.post(`/api/objects/${docId}/${objId}/image/review`);
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
  const { data } = await api.delete(`/api/objects/${docId}/${objId}`);
  return data as { objects: DocumentObject[] };
};

export const deleteObjects = async (docId: string, ids: string[]) => {
  const { data } = await api.post(`/api/documents/${docId}/denoise`, { delete_ids: ids });
  return data as { objects: DocumentObject[] };
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
