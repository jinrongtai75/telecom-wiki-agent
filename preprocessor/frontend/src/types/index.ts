export interface BBox {
  x0: number;
  y0: number;
  x1: number;
  y1: number;
  page_width: number;
  page_height: number;
}

export type ObjectType = 'text' | 'table' | 'image' | 'summary';
export type ConfirmStatus = 'pending' | 'confirmed';
export type DocumentFormat = 'pdf' | 'docx' | 'web';

export interface DocumentObject {
  id: string;
  type: ObjectType;
  content: string;
  order: number;
  page?: number;
  bbox?: BBox;
  metadata: Record<string, unknown>;
  is_heading: boolean;
  confirm_status: ConfirmStatus;
  image_path?: string;
  processed_content?: string;
}

export interface ParseResult {
  document_id: string;
  format: DocumentFormat;
  objects: DocumentObject[];
  raw_content?: string;
}

export interface NoisePatterns {
  header_patterns: string[];
  footer_patterns: string[];
  page_number_patterns: string[];
}

export interface ProcessedDocument {
  document_id: string;
  source_filename: string;
  format: DocumentFormat;
  objects: DocumentObject[];
  noise_patterns_applied?: NoisePatterns;
  created_at: string;
  updated_at: string;
}
