import { useState, useRef, useEffect, memo, useCallback } from 'react';
import { Splitter, Typography, Empty, Modal, Button, Checkbox, Spin } from 'antd';
import {
  DndContext, closestCenter, PointerSensor, useSensor, useSensors,
} from '@dnd-kit/core';
import type { DragEndEvent } from '@dnd-kit/core';
import {
  SortableContext, verticalListSortingStrategy,
  useSortable, arrayMove,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { HolderOutlined } from '@ant-design/icons';
import ObjectBox from './ObjectBox';
import PdfViewer from './PdfViewer';
import type { SelectedRegion } from './PdfViewer';
import type { DocumentObject } from '../types';
import { addManualObject, reorderObjects, summarizeSelection, deleteObjects } from '../api/client';
import { message } from 'antd';

interface Props {
  docId: string | null;
  format: string;
  rawContent: string;
  objects: DocumentObject[];
  selectMode: boolean;
  onSelectModeChange: (v: boolean) => void;
  summarySelectMode: boolean;
  onSummarySelectModeChange: (v: boolean) => void;
  onObjectUpdate: (id: string, updated: Partial<DocumentObject>) => void;
  onObjectsUpdated?: (objects: DocumentObject[]) => void;
}

// ── HTML 원본 문서 렌더링 (rawContent 변경 시에만 리렌더) ─────────────────────
const HtmlContent = memo(({ html, contentRef, onClick }: {
  html: string;
  contentRef: React.RefObject<HTMLDivElement | null>;
  onClick: (e: React.MouseEvent<HTMLDivElement>) => void;
}) => (
  <div
    ref={contentRef}
    style={{ fontSize: 13, lineHeight: 1.6 }}
    dangerouslySetInnerHTML={{ __html: html }}
    onClick={onClick}
  />
));

// ── 드래그 가능한 객체 행 ────────────────────────────────────────────────────
const SortableItem = memo(function SortableItem({
  obj, docId, isSelected, onObjectUpdate, onObjectsUpdated, onClick, objRefsMap,
}: {
  obj: DocumentObject;
  docId: string;
  isSelected: boolean;
  onObjectUpdate: (id: string, updated: Partial<DocumentObject>) => void;
  onObjectsUpdated?: (objects: DocumentObject[]) => void;
  onClick: (id: string) => void;
  objRefsMap: React.MutableRefObject<Record<string, HTMLDivElement | null>>;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: obj.id });

  return (
    <div
      ref={(el) => { setNodeRef(el); objRefsMap.current[obj.id] = el; }}
      style={{
        transform: CSS.Transform.toString(transform),
        transition,
        opacity: isDragging ? 0.5 : 1,
        outline: isSelected ? '2px solid #E6007E' : 'none',
        borderRadius: 4,
        display: 'flex',
        alignItems: 'flex-start',
        gap: 4,
      }}
      onClick={() => onClick(obj.id)}
    >
      {/* 드래그 핸들 */}
      <div
        {...attributes}
        {...listeners}
        style={{
          paddingTop: 8,
          cursor: 'grab',
          color: 'rgba(255,255,255,0.2)',
          flexShrink: 0,
          touchAction: 'none',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <HolderOutlined />
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <ObjectBox
          docId={docId}
          obj={obj}
          onUpdate={onObjectUpdate}
          onDelete={onObjectsUpdated}
        />
      </div>
    </div>
  );
});

// ── 메인 컴포넌트 ────────────────────────────────────────────────────────────
export default function Viewer({ docId, format, rawContent, objects, selectMode, onSelectModeChange, summarySelectMode, onSummarySelectModeChange, onObjectUpdate, onObjectsUpdated }: Props) {
  const [selectedObjId, setSelectedObjId] = useState<string | null>(null);
  const [pendingRegion, setPendingRegion] = useState<SelectedRegion | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [adding, setAdding] = useState(false);
  const [summaryCheckedIds, setSummaryCheckedIds] = useState<Set<string>>(new Set());
  const [summarizing, setSummarizing] = useState(false);
  const [deleteSelectMode, setDeleteSelectMode] = useState(false);
  const [deleteCheckedIds, setDeleteCheckedIds] = useState<Set<string>>(new Set());
  const [deleting, setDeleting] = useState(false);
  const objRefs = useRef<Record<string, HTMLDivElement | null>>({});
  const leftScrollRef = useRef<HTMLDivElement | null>(null);
  const rightScrollRef = useRef<HTMLDivElement | null>(null);
  const htmlContentRef = useRef<HTMLDivElement | null>(null);

  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 3 } }));

  const sorted = [...objects].sort((a, b) => a.order - b.order);

  const handleSelectObj = useCallback((id: string) => {
    setSelectedObjId(id);
    // 우측: 선택 객체가 스크롤 컨테이너의 상단 1/4 지점에 오도록 스크롤
    const el = objRefs.current[id];
    const container = rightScrollRef.current;
    if (el && container) {
      const elTop = el.offsetTop;
      const targetScrollTop = elTop - container.clientHeight * 0.25;
      container.scrollTo({ top: Math.max(0, targetScrollTop), behavior: 'smooth' });
    }
    // 좌측: bbox y0 위치로 스크롤 (PDF)
    const obj = objects.find((o) => o.id === id);
    if (obj?.bbox && leftScrollRef.current) {
      const container = leftScrollRef.current;
      const scale = container.clientWidth / obj.bbox.page_width;
      // 페이지 헤더(26px) + 페이지 간격(20px) 보정
      const pageOffset = obj.page ? (obj.bbox.page_height * scale + 46) * (obj.page - 1) : 0;
      const objTop = pageOffset + obj.bbox.y0 * scale;
      // 객체가 컨테이너 상단 1/4 지점에 오도록 스크롤
      const targetY = objTop - container.clientHeight * 0.25;
      container.scrollTo({ top: Math.max(0, targetY), behavior: 'smooth' });
    }
  }, [objects]);

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    if (!over || active.id === over.id || !docId) return;

    const oldIndex = sorted.findIndex((o) => o.id === active.id);
    const newIndex = sorted.findIndex((o) => o.id === over.id);
    const reordered = arrayMove(sorted, oldIndex, newIndex);
    // 즉시 UI 반영 (낙관적 업데이트) — 백엔드 응답 대기 없음
    onObjectsUpdated?.(reordered.map((o, i) => ({ ...o, order: i })));
    // 백엔드 동기화는 fire-and-forget
    reorderObjects(docId, reordered.map((o) => o.id)).catch(() => {});
  };

  const prevHighlightRef = useRef<HTMLElement | null>(null);

  // HTML 원본 문서 영역에서 data-obj-id 요소 하이라이트
  useEffect(() => {
    const container = htmlContentRef.current;
    if (!container) return;
    // 이전 하이라이트만 제거
    if (prevHighlightRef.current) {
      prevHighlightRef.current.style.outline = '';
      prevHighlightRef.current.style.background = '';
      prevHighlightRef.current = null;
    }
    if (!selectedObjId) return;
    const el = container.querySelector(`[data-obj-id="${selectedObjId}"]`) as HTMLElement | null;
    if (el) {
      el.style.outline = '2px solid #E6007E';
      el.style.background = 'rgba(230,0,126,0.08)';
      el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      prevHighlightRef.current = el;
    }
  }, [selectedObjId]);

  const handleHtmlClick = (e: React.MouseEvent<HTMLDivElement>) => {
    const target = (e.target as HTMLElement).closest('[data-obj-id]') as HTMLElement | null;
    if (!target) return;
    const id = target.dataset.objId;
    if (id) handleSelectObj(id);
  };

  const handleSummaryConfirm = async () => {
    if (!docId) return;
    if (summaryCheckedIds.size === 0) return message.warning('요약할 객체를 선택해주세요');
    setSummarizing(true);
    try {
      const res = await summarizeSelection(docId, [...summaryCheckedIds]);
      onObjectsUpdated?.(res.objects);
      onSummarySelectModeChange(false);
      setSummaryCheckedIds(new Set());
      message.success('요약 생성 완료');
    } finally {
      setSummarizing(false);
    }
  };

  const handleSummaryCancel = () => {
    onSummarySelectModeChange(false);
    setSummaryCheckedIds(new Set());
  };

  const handleDeleteSelectToggle = () => {
    if (!docId) return;
    if (deleteSelectMode) {
      // "선택 완료" 클릭 → 삭제 실행
      if (deleteCheckedIds.size === 0) {
        setDeleteSelectMode(false);
        return;
      }
      setDeleting(true);
      deleteObjects(docId, [...deleteCheckedIds])
        .then((res) => {
          onObjectsUpdated?.(res.objects);
          message.success(`${deleteCheckedIds.size}개 객체 삭제 완료`);
        })
        .catch(() => {})
        .finally(() => {
          setDeleting(false);
          setDeleteSelectMode(false);
          setDeleteCheckedIds(new Set());
        });
    } else {
      setDeleteSelectMode(true);
      setDeleteCheckedIds(new Set());
    }
  };

  const handleDeleteCancel = () => {
    setDeleteSelectMode(false);
    setDeleteCheckedIds(new Set());
  };

  const handleRegionSelect = (region: SelectedRegion) => {
    setPendingRegion(region);
    setModalOpen(true);
  };

  const handleAddManual = async (type: 'table' | 'image') => {
    if (!docId || !pendingRegion) return;
    setAdding(true);
    try {
      // 새 객체가 삽입될 위치를 bbox 기준으로 계산
      // 같은 페이지에서 y0가 새 객체보다 작은(위에 있는) 객체 중 가장 마지막 객체의 order를 after_order로 사용
      const { pageNum, bbox: newBbox } = pendingRegion;
      const newCenterY = (newBbox.y0 + newBbox.y1) / 2;

      const sorted_objs = [...objects].sort((a, b) => a.order - b.order);

      // 새 객체의 중심 y보다 위에 있는 객체들 중 가장 마지막 order
      let afterOrder: number | undefined = undefined;
      for (const obj of sorted_objs) {
        if (obj.page === undefined || obj.bbox === undefined) continue;
        if (obj.page < pageNum) {
          afterOrder = obj.order;
        } else if (obj.page === pageNum) {
          const objCenterY = (obj.bbox.y0 + obj.bbox.y1) / 2;
          if (objCenterY < newCenterY) {
            afterOrder = obj.order;
          }
        }
      }

      const res = await addManualObject(docId, {
        type,
        content: '',
        bbox: pendingRegion.bbox,
        page: pendingRegion.pageNum,
        after_order: afterOrder,
      });
      onObjectsUpdated?.(res.objects);
      message.success(`${type === 'table' ? '표' : '이미지'} 객체 추가 완료`);
    } catch {
      // error already shown by axios interceptor
    } finally {
      setAdding(false);
      setModalOpen(false);
      setPendingRegion(null);
      onSelectModeChange(false);
    }
  };

  const handleModalCancel = () => {
    setModalOpen(false);
    setPendingRegion(null);
  };

  return (
    <>
      <Splitter style={{ height: '100%' }}>
        {/* 좌측: 원본 문서 */}
        <Splitter.Panel defaultSize="50%" min="25%">
          <div style={{ height: '100%', background: '#0f0f17', display: 'flex', flexDirection: 'column' }}>
            <div style={{ padding: '8px 8px 6px', borderBottom: '1px solid rgba(255,255,255,0.07)', flexShrink: 0 }}>
              <Typography.Title level={5} style={{ margin: 0 }}>원본 문서</Typography.Title>
            </div>
            <div ref={leftScrollRef} style={{ flex: 1, overflowY: 'auto', padding: 8 }}>
              {docId && format === 'pdf' ? (
                <PdfViewer
                  docId={docId}
                  objects={objects}
                  selectedObjId={selectedObjId}
                  onSelectObj={handleSelectObj}
                  selectMode={selectMode}
                  onRegionSelect={handleRegionSelect}
                />
              ) : rawContent ? (
                rawContent.trimStart().startsWith('<') ? (
                  <HtmlContent
                    html={rawContent}
                    contentRef={htmlContentRef}
                    onClick={handleHtmlClick}
                  />
                ) : (
                  <div style={{ fontSize: 13, lineHeight: 1.6, whiteSpace: 'pre-wrap' }}>
                    {rawContent}
                  </div>
                )
              ) : (
                <Empty description="문서를 업로드해주세요" />
              )}
            </div>
          </div>
        </Splitter.Panel>

        {/* 우측: 전처리 결과 */}
        <Splitter.Panel>
          <div style={{ height: '100%', display: 'flex', flexDirection: 'column', background: '#0f0f17' }}>
            <div style={{ padding: '8px 8px 6px', borderBottom: '1px solid rgba(255,255,255,0.07)', flexShrink: 0 }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <Typography.Title level={5} style={{ margin: 0 }}>
                  전처리 결과
                  {objects.length > 0 && (
                    <Typography.Text type="secondary" style={{ fontSize: 12, fontWeight: 400, marginLeft: 8 }}>
                      ({objects.length}개 객체)
                    </Typography.Text>
                  )}
                </Typography.Title>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  {summarySelectMode && (
                    <>
                      <Button size="small" type="primary" loading={summarizing} onClick={handleSummaryConfirm}>
                        요약 생성 ({summaryCheckedIds.size})
                      </Button>
                      <Button size="small" onClick={handleSummaryCancel}>취소</Button>
                    </>
                  )}
                  {!summarySelectMode && docId && (
                    <>
                      <Button
                        size="small"
                        danger={deleteSelectMode}
                        type={deleteSelectMode ? 'primary' : 'default'}
                        loading={deleting}
                        onClick={handleDeleteSelectToggle}
                      >
                        {deleteSelectMode ? `선택 완료 (${deleteCheckedIds.size})` : '선택 삭제'}
                      </Button>
                      {deleteSelectMode && (
                        <Button size="small" onClick={handleDeleteCancel}>취소</Button>
                      )}
                    </>
                  )}
                </div>
              </div>
              {summarySelectMode && (
                <Typography.Text type="secondary" style={{ fontSize: 11, marginTop: 4, display: 'block' }}>
                  요약할 객체를 선택하세요
                </Typography.Text>
              )}
              {deleteSelectMode && (
                <Typography.Text type="secondary" style={{ fontSize: 11, marginTop: 4, display: 'block' }}>
                  삭제할 객체를 선택하세요
                </Typography.Text>
              )}
            </div>
            <div ref={rightScrollRef} style={{ flex: 1, overflowY: 'auto', padding: 8 }}>
              {objects.length === 0 ? (
                <Empty description="파싱 결과가 없습니다" />
              ) : docId ? (
                <Spin spinning={summarizing}>
                  <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
                    <SortableContext items={sorted.map((o) => o.id)} strategy={verticalListSortingStrategy}>
                      {(() => {
                        // PDF인 경우 페이지별 그룹핑, DOCX(page 없음)는 단일 그룹
                        const hasPaging = sorted.some((o) => o.page != null);
                        const totalPages = hasPaging ? Math.max(...sorted.map((o) => o.page ?? 0)) : 0;
                        const result: React.ReactNode[] = [];
                        let lastPage: number | null = null;

                        sorted.forEach((obj) => {
                          const pageNum = obj.page ?? null;
                          if (hasPaging && pageNum !== lastPage) {
                            lastPage = pageNum;
                            result.push(
                              <div key={`page-sep-${pageNum}`} style={{
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'space-between',
                                padding: '5px 10px',
                                margin: '10px 0 6px',
                                background: 'rgba(255,255,255,0.04)',
                                borderRadius: 6,
                                borderLeft: '3px solid rgba(230,0,126,0.5)',
                              }}>
                                <span style={{ fontWeight: 700, fontSize: 11, color: 'rgba(255,255,255,0.6)', letterSpacing: '0.3px' }}>
                                  PAGE {pageNum}
                                </span>
                                <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.25)' }}>
                                  of {totalPages}
                                </span>
                              </div>
                            );
                          }

                          result.push(
                            <div key={obj.id} style={{ display: 'flex', alignItems: 'flex-start', gap: 4 }}>
                              {summarySelectMode && (
                                <Checkbox
                                  style={{ paddingTop: 10, flexShrink: 0 }}
                                  checked={summaryCheckedIds.has(obj.id)}
                                  onChange={(e) => {
                                    setSummaryCheckedIds((prev) => {
                                      const next = new Set(prev);
                                      e.target.checked ? next.add(obj.id) : next.delete(obj.id);
                                      return next;
                                    });
                                  }}
                                />
                              )}
                              {deleteSelectMode && (
                                <Checkbox
                                  style={{ paddingTop: 10, flexShrink: 0 }}
                                  checked={deleteCheckedIds.has(obj.id)}
                                  onChange={(e) => {
                                    setDeleteCheckedIds((prev) => {
                                      const next = new Set(prev);
                                      e.target.checked ? next.add(obj.id) : next.delete(obj.id);
                                      return next;
                                    });
                                  }}
                                />
                              )}
                              <div style={{ flex: 1, minWidth: 0 }}>
                                <SortableItem
                                  obj={obj}
                                  docId={docId}
                                  isSelected={selectedObjId === obj.id}
                                  onObjectUpdate={onObjectUpdate}
                                  onObjectsUpdated={onObjectsUpdated}
                                  onClick={handleSelectObj}
                                  objRefsMap={objRefs}
                                />
                              </div>
                            </div>
                          );
                        });
                        return result;
                      })()}
                    </SortableContext>
                  </DndContext>
                </Spin>
              ) : null}
            </div>
          </div>
        </Splitter.Panel>
      </Splitter>

      <Modal
        title="객체 유형 선택"
        open={modalOpen}
        onCancel={handleModalCancel}
        footer={null}
        width={320}
      >
        <Typography.Text type="secondary" style={{ display: 'block', marginBottom: 16 }}>
          선택한 영역을 어떤 객체로 등록할까요?
        </Typography.Text>
        <div style={{ display: 'flex', gap: 8 }}>
          <Button block type="primary" loading={adding} onClick={() => handleAddManual('table')}>
            표 (Table)
          </Button>
          <Button block loading={adding} onClick={() => handleAddManual('image')}>
            이미지 (Image)
          </Button>
        </div>
      </Modal>
    </>
  );
}
