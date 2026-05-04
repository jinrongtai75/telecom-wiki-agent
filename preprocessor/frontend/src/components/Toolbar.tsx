import { useState, useRef } from 'react';
import axios from 'axios';
import {
  Button, Upload, Input, Space, message, Spin, Checkbox, Typography, Modal, Form, Tag,
} from 'antd';
import {
  UploadOutlined, ClearOutlined, FileTextOutlined,
  DownloadOutlined, SettingOutlined, SelectOutlined, CloudUploadOutlined,
} from '@ant-design/icons';
import {
  uploadDocument, denoise, getNoiseCandidates,
  exportDocument, exportDocumentContent, ingestToWikiAgent,
  reviewTable, reviewImage, listKeys, listRagDocuments,
} from '../api/client';
import type { RagDocument } from '../api/client';
import type { DocumentObject } from '../types';
import SettingsPanel from './SettingsPanel';

interface Props {
  docId: string | null;
  format: string;
  objects: DocumentObject[];
  selectMode: boolean;
  onSelectModeChange: (v: boolean) => void;
  summarySelectMode: boolean;
  onSummarySelectModeChange: (v: boolean) => void;
  onDocLoaded: (docId: string, objects: DocumentObject[], rawContent: string, format: string, name?: string) => void;
  onObjectsUpdated: (objects: DocumentObject[]) => void;
  sourceName?: string;  // 업로드된 원본 파일명
}

export default function Toolbar({ docId, format, objects, selectMode, onSelectModeChange, summarySelectMode, onSummarySelectModeChange, onDocLoaded, onObjectsUpdated, sourceName }: Props) {
  const [loading, setLoading] = useState(false);
  const [reviewingTable, setReviewingTable] = useState(false);
  const [reviewingImage, setReviewingImage] = useState(false);
  const [tableProgress, setTableProgress] = useState<{ current: number; total: number } | null>(null);
  const [imageProgress, setImageProgress] = useState<{ current: number; total: number } | null>(null);
  const tableAbortRef = useRef<AbortController | null>(null);
  const imageAbortRef = useRef<AbortController | null>(null);
  const [ingesting, setIngesting] = useState(false);
  const [ingestResult, setIngestResult] = useState<{ chunkCount: number } | null>(null);
  const [ragDocs, setRagDocs] = useState<RagDocument[] | null>(null);
  const [ragLoading, setRagLoading] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [noiseCandidates, setNoiseCandidates] = useState<{ text: string; count: number; object_ids: string[] }[]>([]);
  const [checkedIds, setCheckedIds] = useState<Set<string>>(new Set());
  const [noiseOpen, setNoiseOpen] = useState(false);
  const [containsInput, setContainsInput] = useState('');
  const [exportModalOpen, setExportModalOpen] = useState(false);
  const [exportSavePath, setExportSavePath] = useState('');
  const [exportFilename, setExportFilename] = useState('');

  const wrap = async (fn: () => Promise<void>) => {
    setLoading(true);
    try { await fn(); } finally { setLoading(false); }
  };

  const handleFileUpload = async (file: File) => {
    await wrap(async () => {
      const res = await uploadDocument(file);
      onDocLoaded(res.document_id, res.objects, res.raw_content || '', res.format, file.name);
      message.success('문서 파싱 완료');
    });
    return false;
  };

  const handleFindCandidates = async () => {
    if (!docId) return message.warning('문서를 먼저 업로드해주세요');
    await wrap(async () => {
      try {
        const res = await getNoiseCandidates(docId);
        setNoiseCandidates(res.candidates);
        if (res.candidates.length === 0) {
          message.info('노이즈 후보가 없습니다');
        } else {
          const allIds = res.candidates.flatMap((c) => c.object_ids);
          setCheckedIds(new Set(allIds));
        }
        setNoiseOpen(true);
      } catch (err: any) {
        if (err?.response?.status === 404) {
          message.error('서버에서 문서를 찾을 수 없습니다. PDF를 다시 업로드해주세요.');
        } else {
          message.error(err?.response?.data?.detail || err?.message || '노이즈 후보 조회 실패');
        }
      }
    });
  };

  const handleDenoise = async () => {
    if (!docId) return message.warning('문서를 먼저 업로드해주세요');
    if (checkedIds.size === 0) return message.warning('제거할 항목을 선택해주세요');
    await wrap(async () => {
      try {
        const res = await denoise(docId, { delete_ids: [...checkedIds] });
        onObjectsUpdated(res.objects);
        setNoiseCandidates([]);
        setCheckedIds(new Set());
        setContainsInput('');
        setNoiseOpen(false);
        message.success('노이즈 제거 완료');
      } catch (err: any) {
        if (err?.response?.status === 404) {
          message.error('서버에서 문서를 찾을 수 없습니다. PDF를 다시 업로드해주세요.');
        } else {
          message.error(err?.response?.data?.detail || err?.message || '노이즈 제거 실패');
        }
      }
    });
  };

  const toggleCandidate = (object_ids: string[], checked: boolean) => {
    setCheckedIds((prev) => {
      const next = new Set(prev);
      object_ids.forEach((id) => checked ? next.add(id) : next.delete(id));
      return next;
    });
  };

  const handleSummarySelectMode = () => {
    if (!docId) return message.warning('문서를 먼저 업로드해주세요');
    onSummarySelectModeChange(!summarySelectMode);
  };

  const handleExport = () => {
    if (!docId) return message.warning('문서를 먼저 업로드해주세요');
    setExportFilename(sourceName ? sourceName.replace(/\.[^.]+$/, '') : '');
    const unconfirmed = objects.filter(
      (o) => (o.type === 'table' || o.type === 'image') && o.confirm_status === 'pending'
    );
    if (unconfirmed.length > 0) {
      Modal.confirm({
        title: '미확인 객체가 있습니다',
        content: `이미지 또는 테이블 중 아직 확인(Confirm)되지 않은 항목이 ${unconfirmed.length}개 있습니다. 그대로 내보내시겠습니까?`,
        okText: '그대로 내보내기',
        cancelText: '취소',
        onOk: () => setExportModalOpen(true),
      });
    } else {
      setExportModalOpen(true);
    }
  };

  const handleExportConfirm = async () => {
    if (!docId) return;
    await wrap(async () => {
      await exportDocument(docId, true, exportSavePath || undefined, exportFilename || undefined);
      setExportModalOpen(false);
      message.success('내보내기 완료');
    });
  };

  /** MD를 Wiki Agent RAG DB에 적재 */
  const handleIngestToWiki = async () => {
    if (!docId) return message.warning('문서를 먼저 업로드해주세요');
    setIngesting(true);
    setIngestResult(null);
    try {
      const { content, filename } = await exportDocumentContent(docId, true);
      const res = await ingestToWikiAgent(docId, content, filename, sourceName);
      setIngestResult({ chunkCount: res.chunk_count });
      message.success(`Wiki Agent RAG 적재 완료 — ${res.chunk_count}개 청크`);
    } catch {
      // 에러 메시지는 axios 인터셉터에서 이미 표시
    } finally {
      setIngesting(false);
    }
  };

  const handleReviewAllTables = async () => {
    if (!docId) return message.warning('문서를 먼저 업로드해주세요');
    const targets = objects.filter((o) => o.type === 'table');
    if (targets.length === 0) return message.info('표 객체가 없습니다');
    const keys = await listKeys().catch(() => ({} as Record<string, boolean>));
    if (!keys.gemini) return message.error('Gemini API 키가 설정되지 않았습니다. 설정 패널에서 먼저 저장해주세요.');
    const controller = new AbortController();
    tableAbortRef.current = controller;
    setReviewingTable(true);
    setTableProgress({ current: 0, total: targets.length });
    let kept = 0, flattened = 0, failed = 0, cancelled = false;
    const updatedObjects = [...objects];
    try {
      for (let i = 0; i < targets.length; i++) {
        const obj = targets[i];
        setTableProgress({ current: i + 1, total: targets.length });
        try {
          const res = await reviewTable(docId, obj.id, controller.signal);
          const idx = updatedObjects.findIndex((o) => o.id === obj.id);
          if (idx !== -1 && res.action === 'flatten') {
            updatedObjects[idx] = { ...updatedObjects[idx], processed_content: res.processed_content ?? undefined };
            flattened++;
          } else {
            kept++;
          }
        } catch (err: any) {
          if (axios.isCancel(err)) { cancelled = true; break; }
          if (err?.response?.status === 404) {
            message.error('서버에서 문서를 찾을 수 없습니다. PDF를 다시 업로드해주세요.');
            break;
          }
          failed++;
        }
      }
      onObjectsUpdated(updatedObjects);
      if (cancelled) {
        message.info(`Table 검수 취소됨 — 유지: ${kept}, Flatten: ${flattened}${failed > 0 ? `, 실패: ${failed}` : ''}`);
      } else {
        message.success(`Table 검수 완료 — 유지: ${kept}, Flatten: ${flattened}${failed > 0 ? `, 실패: ${failed}` : ''}`);
      }
    } finally {
      setReviewingTable(false);
      setTableProgress(null);
      tableAbortRef.current = null;
    }
  };

  const handleReviewAllImages = async () => {
    if (!docId) return message.warning('문서를 먼저 업로드해주세요');
    const targets = objects.filter((o) => o.type === 'image');
    if (targets.length === 0) return message.info('이미지 객체가 없습니다');
    const keys = await listKeys().catch(() => ({} as Record<string, boolean>));
    if (!keys.gemini) return message.error('Gemini API 키가 설정되지 않았습니다. 설정 패널에서 먼저 저장해주세요.');
    const controller = new AbortController();
    imageAbortRef.current = controller;
    setReviewingImage(true);
    setImageProgress({ current: 0, total: targets.length });
    let saved = 0, described = 0, discarded = 0, failed = 0, cancelled = false;
    let currentObjects = [...objects];
    try {
      for (let i = 0; i < targets.length; i++) {
        const obj = targets[i];
        if (!currentObjects.find((o) => o.id === obj.id)) continue;
        setImageProgress({ current: i + 1, total: targets.length });
        try {
          const res = await reviewImage(docId, obj.id, controller.signal);
          if (res.action === 'discard') {
            currentObjects = res.objects;
            discarded++;
          } else if (res.action === 'save') {
            const idx = currentObjects.findIndex((o) => o.id === obj.id);
            if (idx !== -1) currentObjects[idx] = { ...currentObjects[idx], processed_content: res.processed_content, image_path: res.image_path };
            saved++;
          } else {
            const idx = currentObjects.findIndex((o) => o.id === obj.id);
            if (idx !== -1) currentObjects[idx] = { ...currentObjects[idx], processed_content: res.processed_content };
            described++;
          }
        } catch (err: any) {
          if (axios.isCancel(err)) { cancelled = true; break; }
          if (err?.response?.status === 404) {
            message.error('서버에서 문서를 찾을 수 없습니다. PDF를 다시 업로드해주세요.');
            break;
          }
          failed++;
        }
      }
      onObjectsUpdated(currentObjects);
      if (cancelled) {
        message.info(`Image 검수 취소됨 — 저장: ${saved}, 텍스트변환: ${described}, 삭제: ${discarded}${failed > 0 ? `, 실패: ${failed}` : ''}`);
      } else {
        message.success(`Image 검수 완료 — 저장: ${saved}, 텍스트변환: ${described}, 삭제: ${discarded}${failed > 0 ? `, 실패: ${failed}` : ''}`);
      }
    } finally {
      setReviewingImage(false);
      setImageProgress(null);
      imageAbortRef.current = null;
    }
  };

  const sectionLabel = (text: string) => (
    <div style={{
      fontSize: 10,
      fontWeight: 600,
      color: 'rgba(255,255,255,0.3)',
      letterSpacing: '0.6px',
      textTransform: 'uppercase',
      padding: '10px 12px 4px',
    }}>
      {text}
    </div>
  );

  const divider = <div style={{ height: 1, background: 'rgba(255,255,255,0.07)', margin: '6px 0' }} />;

  return (
    <Spin spinning={loading}>
      <div style={{ padding: '8px 0' }}>

        {/* ── 문서 ── */}
        {sectionLabel('문서')}
        <div style={{ padding: '0 10px', display: 'flex', flexDirection: 'column', gap: 4 }}>
          <Upload beforeUpload={handleFileUpload} showUploadList={false} accept=".pdf,.docx" style={{ display: 'block' }}>
            <Button icon={<UploadOutlined />} block size="small" type="primary" style={{ width: '100%' }}>
              PDF / Word 업로드
            </Button>
          </Upload>
          <Button icon={<DownloadOutlined />} block size="small" onClick={handleExport}>
            MD 내보내기
          </Button>
        </div>

        {divider}

        {/* ── 전처리 ── */}
        {sectionLabel('전처리')}
        <div style={{ padding: '0 10px', display: 'flex', flexDirection: 'column', gap: 4 }}>

          <Button icon={<ClearOutlined />} block size="small" onClick={handleFindCandidates}>
            노이즈 제거
          </Button>
          {noiseOpen && (
            <div style={{
              border: '1px solid rgba(255,255,255,0.1)',
              borderRadius: 8,
              background: '#1e1e35',
              boxShadow: '0 4px 20px rgba(0,0,0,0.4)',
              overflow: 'hidden',
            }}>
              <div style={{ maxHeight: 200, overflowY: 'auto', padding: '4px 8px' }}>
                {noiseCandidates.map((c) => {
                  const allChecked = c.object_ids.every((id) => checkedIds.has(id));
                  return (
                    <div key={c.text} style={{ padding: '4px 0', borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                      <Checkbox
                        checked={allChecked}
                        onChange={(e) => toggleCandidate(c.object_ids, e.target.checked)}
                      >
                        <Typography.Text style={{ fontSize: 11 }}>
                          {c.text.length > 26 ? c.text.slice(0, 26) + '…' : c.text}
                        </Typography.Text>
                        <Typography.Text type="secondary" style={{ fontSize: 10, marginLeft: 3 }}>
                          ({c.count})
                        </Typography.Text>
                      </Checkbox>
                    </div>
                  );
                })}
              </div>
              <div style={{ padding: '6px 8px', borderTop: '1px solid rgba(255,255,255,0.07)', background: '#161622' }}>
                <Input
                  size="small"
                  placeholder="포함 텍스트로 삭제 (예: Proprietary)"
                  value={containsInput}
                  onChange={(e) => setContainsInput(e.target.value)}
                  style={{ marginBottom: 5 }}
                />
                <div style={{ display: 'flex', gap: 5 }}>
                  <Button size="small" danger block onClick={handleDenoise}>제거</Button>
                  <Button size="small" block onClick={() => setNoiseOpen(false)}>닫기</Button>
                </div>
              </div>
            </div>
          )}

          <Button
            icon={<FileTextOutlined />}
            block
            size="small"
            type={summarySelectMode ? 'primary' : 'default'}
            onClick={handleSummarySelectMode}
          >
            {summarySelectMode ? '선택 중... (취소)' : '소제목 요약 생성'}
          </Button>

          {docId && format === 'pdf' && (
            <Button
              icon={<SelectOutlined />}
              block
              size="small"
              type={selectMode ? 'primary' : 'default'}
              onClick={() => onSelectModeChange(!selectMode)}
            >
              {selectMode ? '영역 지정 중... (취소)' : '이미지·표 영역 지정'}
            </Button>
          )}
        </div>

        {divider}

        {/* ── LLM 검수 ── */}
        {sectionLabel('LLM 검수')}
        <div style={{ padding: '0 10px', display: 'flex', flexDirection: 'column', gap: 4 }}>
          <Button
            block
            size="small"
            danger={reviewingTable}
            onClick={reviewingTable ? () => tableAbortRef.current?.abort() : handleReviewAllTables}
          >
            {reviewingTable
              ? `검수 중 (${tableProgress?.current}/${tableProgress?.total}) 취소`
              : 'Table 검수'}
          </Button>
          <Button
            block
            size="small"
            danger={reviewingImage}
            onClick={reviewingImage ? () => imageAbortRef.current?.abort() : handleReviewAllImages}
          >
            {reviewingImage
              ? `검수 중 (${imageProgress?.current}/${imageProgress?.total}) 취소`
              : 'Image 검수'}
          </Button>
        </div>

        {divider}

        {/* ── RAG 적재 ── */}
        {sectionLabel('RAG 적재')}
        <div style={{ padding: '0 10px', display: 'flex', flexDirection: 'column', gap: 4 }}>
          <Button
            icon={<CloudUploadOutlined />}
            block
            size="small"
            type="primary"
            style={{ background: '#7c3aed' }}
            loading={ingesting}
            onClick={handleIngestToWiki}
          >
            Wiki Agent에 적재
          </Button>
          {ingestResult && (
            <Space style={{ fontSize: 11, justifyContent: 'center' }}>
              <Tag color="purple">{ingestResult.chunkCount}개 청크 적재 완료</Tag>
            </Space>
          )}
          <div style={{ fontSize: 10, color: '#8c8c8c', textAlign: 'center', lineHeight: 1.4 }}>
            전처리 완료 후 MD를<br />Wiki Agent DB에 인덱싱
          </div>
        </div>

        {divider}

        {/* ── RAG 현황 ── */}
        {sectionLabel('RAG 현황')}
        <div style={{ padding: '0 10px', display: 'flex', flexDirection: 'column', gap: 4 }}>
          <Button
            block
            size="small"
            loading={ragLoading}
            onClick={async () => {
              setRagLoading(true);
              try {
                const docs = await listRagDocuments();
                setRagDocs(docs.filter(d => d.status !== 'indexing' || (d.chunk_count ?? 0) > 0));
              } catch {
                // 에러는 인터셉터에서 처리
              } finally {
                setRagLoading(false);
              }
            }}
          >
            적재 현황 조회
          </Button>
          {ragDocs !== null && (
            <div style={{ border: '1px solid rgba(255,255,255,0.1)', borderRadius: 6, overflow: 'hidden', fontSize: 10 }}>
              <div style={{ display: 'grid', gridTemplateColumns: '16px 1fr 56px 34px', gap: 0, background: 'rgba(255,255,255,0.04)', borderBottom: '1px solid rgba(255,255,255,0.07)' }}>
                {['', '문서명', '날짜', '청크'].map((h, i) => (
                  <div key={i} style={{ padding: '3px 4px', fontWeight: 600, color: 'rgba(255,255,255,0.4)' }}>{h}</div>
                ))}
              </div>
              <div style={{ maxHeight: 220, overflowY: 'auto' }}>
                {ragDocs.length === 0 ? (
                  <div style={{ padding: '8px', color: 'rgba(255,255,255,0.25)', textAlign: 'center' }}>적재된 문서 없음</div>
                ) : ragDocs.map((doc) => {
                  const statusIcon = doc.status === 'indexed' ? '✅' : doc.status === 'error' ? '❌' : '⏳';
                  const date = doc.indexed_at ? doc.indexed_at.slice(0, 10) : '-';
                  const name = doc.original_name || doc.filename;
                  const shortName = name.length > 22 ? name.slice(0, 22) + '…' : name;
                  return (
                    <div key={doc.id} style={{ display: 'grid', gridTemplateColumns: '16px 1fr 56px 34px', borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                      <div style={{ padding: '3px 4px' }}>{statusIcon}</div>
                      <div style={{ padding: '3px 4px', overflow: 'hidden', color: 'rgba(255,255,255,0.75)' }} title={name}>{shortName}</div>
                      <div style={{ padding: '3px 4px', color: 'rgba(255,255,255,0.35)' }}>{date}</div>
                      <div style={{ padding: '3px 4px', color: 'rgba(255,255,255,0.5)', textAlign: 'right' }}>{doc.chunk_count ?? 0}</div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>

        {divider}

        {/* ── 설정 ── */}
        {sectionLabel('설정')}
        <div style={{ padding: '0 10px', display: 'flex', flexDirection: 'column', gap: 4 }}>
          <Button
            icon={<SettingOutlined />}
            block
            size="small"
            type={showSettings ? 'primary' : 'default'}
            onClick={() => setShowSettings((v) => !v)}
          >
            API 키 / 연동 설정
          </Button>
          {showSettings && <SettingsPanel />}
        </div>

      </div>

      <Modal
        title="MD 내보내기"
        open={exportModalOpen}
        onCancel={() => setExportModalOpen(false)}
        onOk={handleExportConfirm}
        okText="내보내기"
        cancelText="취소"
      >
        <Form layout="vertical" size="small" style={{ marginTop: 8 }}>
          <Form.Item
            label="저장 경로"
            extra="비워두면 브라우저 다운로드로 저장됩니다"
          >
            <Input
              value={exportSavePath}
              onChange={(e) => setExportSavePath(e.target.value)}
              placeholder="예: /Users/user/Downloads"
            />
          </Form.Item>
          <Form.Item
            label="파일명"
            extra="비워두면 원본 파일명으로 저장됩니다"
          >
            <Input
              value={exportFilename}
              onChange={(e) => setExportFilename(e.target.value)}
              placeholder="예: result"
              addonAfter=".md"
            />
          </Form.Item>
        </Form>
      </Modal>
    </Spin>
  );
}
