import { useEffect, useRef, useState } from 'react';
import * as pdfjsLib from 'pdfjs-dist';
import type { PDFDocumentProxy } from 'pdfjs-dist';
import { Spin, Empty, Typography } from 'antd';
import type { DocumentObject, BBox } from '../types';

pdfjsLib.GlobalWorkerOptions.workerSrc = new URL(
  'pdfjs-dist/build/pdf.worker.min.mjs',
  import.meta.url,
).toString();

const OVERLAY_COLORS: Record<string, string> = {
  text:    'transparent',
  table:   'rgba(249,115,22,0.28)',
  image:   'rgba(168,85,247,0.28)',
  summary: 'rgba(20,184,166,0.22)',
};
const BORDER_COLORS: Record<string, string> = {
  text:    '#3b82f6',
  table:   '#f97316',
  image:   '#a855f7',
  summary: '#14b8a6',
};

interface PageInfo {
  pageNum: number;
  origWidth: number;
  origHeight: number;
}

export interface SelectedRegion {
  bbox: BBox;        // PDF 좌표계 (origWidth/Height 포함)
  pageNum: number;
}

interface Props {
  docId: string;
  objects: DocumentObject[];
  selectedObjId?: string | null;
  onSelectObj?: (id: string) => void;
  selectMode?: boolean;
  onRegionSelect?: (region: SelectedRegion) => void;
}

// ── 단일 페이지 컴포넌트 ──────────────────────────────────────────────────────
function PdfPage({
  pdf, pageInfo, containerWidth,
  objects, selectedObjId, onSelectObj,
  selectMode, onRegionSelect,
}: {
  pdf: PDFDocumentProxy;
  pageInfo: PageInfo;
  containerWidth: number;
  objects: DocumentObject[];
  selectedObjId?: string | null;
  onSelectObj?: (id: string) => void;
  selectMode?: boolean;
  onRegionSelect?: (region: SelectedRegion) => void;
}) {
  const canvasRef  = useRef<HTMLCanvasElement>(null);
  const [scale, setScale] = useState(1);

  // 드래그 상태
  const dragStart  = useRef<{ x: number; y: number } | null>(null);
  const [dragRect, setDragRect] = useState<{ x: number; y: number; w: number; h: number } | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const page = await pdf.getPage(pageInfo.pageNum);
      const vp   = page.getViewport({ scale: 1 });
      const s    = containerWidth / vp.width;
      const svp  = page.getViewport({ scale: s });

      const canvas = canvasRef.current;
      if (!canvas || cancelled) return;
      canvas.width  = svp.width;
      canvas.height = svp.height;
      setScale(s);
      await page.render({ canvas, viewport: svp }).promise;
    })();
    return () => { cancelled = true; };
  }, [pdf, pageInfo.pageNum, containerWidth]);

  // ── 드래그 핸들러 ──────────────────────────────────────────────────────────
  const getPos = (e: React.MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    return { x: e.clientX - rect.left, y: e.clientY - rect.top };
  };

  const onMouseDown = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!selectMode) return;
    e.preventDefault();
    dragStart.current = getPos(e);
    setDragRect(null);
  };

  const onMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!selectMode || !dragStart.current) return;
    const cur = getPos(e);
    setDragRect({
      x: Math.min(dragStart.current.x, cur.x),
      y: Math.min(dragStart.current.y, cur.y),
      w: Math.abs(cur.x - dragStart.current.x),
      h: Math.abs(cur.y - dragStart.current.y),
    });
  };

  const onMouseUp = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!selectMode || !dragStart.current) return;
    const cur = getPos(e);
    const x0 = Math.min(dragStart.current.x, cur.x);
    const y0 = Math.min(dragStart.current.y, cur.y);
    const x1 = Math.max(dragStart.current.x, cur.x);
    const y1 = Math.max(dragStart.current.y, cur.y);
    dragStart.current = null;
    setDragRect(null);

    if (x1 - x0 < 5 || y1 - y0 < 5) return; // 너무 작은 선택 무시

    // CSS px → PDF 좌표 변환
    onRegionSelect?.({
      pageNum: pageInfo.pageNum,
      bbox: {
        x0: x0 / scale,
        y0: y0 / scale,
        x1: x1 / scale,
        y1: y1 / scale,
        page_width:  pageInfo.origWidth,
        page_height: pageInfo.origHeight,
      },
    });
  };

  const pageObjs = objects.filter((o) => o.bbox && o.page === pageInfo.pageNum);
  const canvasW  = pageInfo.origWidth * scale || '100%';

  return (
    <div style={{ marginBottom: 20 }}>
      {/* 페이지 구분 헤더 */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '5px 10px',
        marginBottom: 6,
        background: '#f5f5f5',
        borderRadius: 6,
        borderLeft: '3px solid #d9d9d9',
      }}>
        <span style={{ fontWeight: 700, fontSize: 11, color: '#595959', letterSpacing: '0.3px' }}>
          PAGE {pageInfo.pageNum}
        </span>
        <span style={{ fontSize: 10, color: '#bfbfbf' }}>
          of {pdf.numPages}
        </span>
      </div>

    <div
      style={{
        position: 'relative',
        width: canvasW,
        boxShadow: '0 2px 8px rgba(0,0,0,0.18)',
        background: '#fff',
        display: 'inline-block',
        cursor: selectMode ? 'crosshair' : 'default',
        userSelect: 'none',
      }}
      onMouseDown={onMouseDown}
      onMouseMove={onMouseMove}
      onMouseUp={onMouseUp}
      onMouseLeave={() => { dragStart.current = null; setDragRect(null); }}
    >
      <canvas ref={canvasRef} style={{ display: 'block' }} />

      {/* 기존 객체 오버레이 */}
      {pageObjs.map((obj) => {
        const b = obj.bbox!;
        return (
          <div
            key={obj.id}
            title={`[${obj.type}] ${obj.content.slice(0, 80)}`}
            onClick={(e) => { if (selectMode) return; e.stopPropagation(); onSelectObj?.(obj.id); }}
            style={{
              position: 'absolute',
              left:   b.x0 * scale,
              top:    b.y0 * scale,
              width:  (b.x1 - b.x0) * scale,
              height: (b.y1 - b.y0) * scale,
              backgroundColor: obj.id === selectedObjId
                ? (obj.type === 'text' ? 'rgba(59,130,246,0.30)' : OVERLAY_COLORS[obj.type].replace(/[\d.]+\)$/, '0.50)'))
                : OVERLAY_COLORS[obj.type],
              border: obj.id === selectedObjId
                ? `3px solid ${BORDER_COLORS[obj.type]}`
                : `1px solid ${BORDER_COLORS[obj.type]}`,
              outline: obj.id === selectedObjId ? `2px solid ${BORDER_COLORS[obj.type]}` : 'none',
              outlineOffset: '2px',
              boxSizing: 'border-box',
              cursor: selectMode ? 'crosshair' : 'pointer',
              zIndex: obj.id === selectedObjId ? 5 : 2,
              pointerEvents: selectMode ? 'none' : 'auto',
              transition: 'background-color 0.12s, border 0.12s',
            }}
          >
            {obj.type !== 'text' && (
              <span style={{
                position: 'absolute', top: 0, left: 0,
                fontSize: 9, fontWeight: 700, lineHeight: '14px',
                padding: '0 3px',
                background: BORDER_COLORS[obj.type],
                color: '#fff',
                borderBottomRightRadius: 3,
                pointerEvents: 'none',
                userSelect: 'none',
              }}>
                {obj.type.toUpperCase()}{obj.confirm_status === 'confirmed' ? ' ✓' : ''}
              </span>
            )}
          </div>
        );
      })}

      {/* 드래그 선택 사각형 */}
      {dragRect && (
        <div style={{
          position: 'absolute',
          left: dragRect.x, top: dragRect.y,
          width: dragRect.w, height: dragRect.h,
          border: '2px dashed #f59e0b',
          background: 'rgba(245,158,11,0.15)',
          boxSizing: 'border-box',
          zIndex: 10,
          pointerEvents: 'none',
        }} />
      )}
    </div>
    </div>
  );
}

// ── 메인 컴포넌트 ─────────────────────────────────────────────────────────────
export default function PdfViewer({
  docId, objects, selectedObjId, onSelectObj,
  selectMode, onRegionSelect,
}: Props) {
  const wrapperRef = useRef<HTMLDivElement>(null);
  const [pdf, setPdf]             = useState<PDFDocumentProxy | null>(null);
  const [pages, setPages]         = useState<PageInfo[]>([]);
  const [containerWidth, setContainerWidth] = useState(0);
  const [loading, setLoading]     = useState(false);
  const [error, setError]         = useState('');

  useEffect(() => {
    const el = wrapperRef.current;
    if (!el) return;
    const ro = new ResizeObserver((entries) => {
      const w = entries[0].contentRect.width;
      if (w > 0) setContainerWidth(w);
    });
    ro.observe(el);
    if (el.clientWidth > 0) setContainerWidth(el.clientWidth);
    return () => ro.disconnect();
  }, []);

  useEffect(() => {
    if (!docId) return;
    let destroyed = false;
    setLoading(true); setError(''); setPdf(null); setPages([]);

    (async () => {
      try {
        const apiBase = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';
        const loaded = await pdfjsLib.getDocument({
          url: `${apiBase}/api/documents/${docId}/file`,
        }).promise;
        if (destroyed) { loaded.destroy(); return; }

        const infos: PageInfo[] = [];
        for (let i = 1; i <= loaded.numPages; i++) {
          const page = await loaded.getPage(i);
          const vp   = page.getViewport({ scale: 1 });
          infos.push({ pageNum: i, origWidth: vp.width, origHeight: vp.height });
        }
        setPdf(loaded);
        setPages(infos);
      } catch (e) {
        setError(String(e));
      } finally {
        setLoading(false);
      }
    })();
    return () => { destroyed = true; };
  }, [docId]);

  if (!docId)  return <Empty description="문서를 업로드해주세요" style={{ marginTop: 40 }} />;
  if (loading) return <Spin tip="PDF 불러오는 중..." style={{ display: 'block', marginTop: 40 }} />;
  if (error)   return <Typography.Text type="danger">PDF 렌더링 오류: {error}</Typography.Text>;

  return (
    <div ref={wrapperRef} style={{ width: '100%' }}>
      {pdf && containerWidth > 0 && pages.map((pi) => (
        <PdfPage
          key={pi.pageNum}
          pdf={pdf}
          pageInfo={pi}
          containerWidth={containerWidth}
          objects={objects}
          selectedObjId={selectedObjId}
          onSelectObj={onSelectObj}
          selectMode={selectMode}
          onRegionSelect={onRegionSelect}
        />
      ))}
    </div>
  );
}
