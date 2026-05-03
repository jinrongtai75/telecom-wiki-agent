import { useState, useCallback } from 'react';
import { Layout } from 'antd';
import Toolbar from './components/Toolbar';
import Viewer from './components/Viewer';
import type { DocumentObject } from './types';

const { Sider, Content } = Layout;

export default function App() {
  const [docId, setDocId] = useState<string | null>(null);
  const [format, setFormat] = useState<string>('');
  const [objects, setObjects] = useState<DocumentObject[]>([]);
  const [rawContent, setRawContent] = useState('');
  const [sourceName, setSourceName] = useState('');
  const [selectMode, setSelectMode] = useState(false);
  const [summarySelectMode, setSummarySelectMode] = useState(false);

  const handleDocLoaded = (id: string, objs: DocumentObject[], raw: string, fmt: string, name?: string) => {
    setDocId(id);
    setObjects(objs);
    setRawContent(raw);
    setFormat(fmt);
    if (name) setSourceName(name);
    setSelectMode(false);
    setSummarySelectMode(false);
  };

  const handleObjectsUpdated = useCallback((objs: DocumentObject[]) => setObjects(objs), []);

  const handleObjectUpdate = useCallback((id: string, updated: Partial<DocumentObject>) => {
    setObjects((prev) =>
      prev.map((o) => (o.id === id ? { ...o, ...updated } : o))
    );
  }, []);

  return (
    <Layout style={{ height: '100vh', background: '#0f0f17' }}>
      <Sider
        width={264}
        style={{
          background: '#161622',
          borderRight: '1px solid rgba(255,255,255,0.07)',
          overflowY: 'auto',
          overflowX: 'hidden',
        }}
      >
        {/* 브랜드 헤더 */}
        <div style={{
          padding: '14px 16px 12px',
          borderBottom: '1px solid rgba(255,255,255,0.07)',
          background: '#161622',
          display: 'flex',
          alignItems: 'center',
          gap: 10,
        }}>
          <div style={{
            width: 32, height: 32, borderRadius: 10, flexShrink: 0,
            background: 'linear-gradient(135deg, #E6007E, #9b0050)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <svg viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" width={16} height={16}>
              <path d="M1.5 8.5a13 13 0 0 1 21 0" />
              <path d="M5 12a10 10 0 0 1 14 0" />
              <path d="M8.5 15.5a6 6 0 0 1 7 0" />
              <circle cx="12" cy="19" r="1" fill="white" stroke="none" />
            </svg>
          </div>
          <div>
            <div style={{ fontSize: 12, fontWeight: 700, color: 'rgba(255,255,255,0.9)', letterSpacing: '-0.2px' }}>
              문서 전처리 도구
            </div>
            <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.35)', marginTop: 1 }}>RAG Pipeline Preprocessor</div>
          </div>
        </div>

        <Toolbar
          docId={docId}
          format={format}
          objects={objects}
          selectMode={selectMode}
          onSelectModeChange={setSelectMode}
          summarySelectMode={summarySelectMode}
          onSummarySelectModeChange={setSummarySelectMode}
          onDocLoaded={handleDocLoaded}
          onObjectsUpdated={handleObjectsUpdated}
          sourceName={sourceName}
        />
      </Sider>

      <Content style={{ height: '100vh', overflow: 'hidden', background: '#0f0f17' }}>
        <Viewer
          docId={docId}
          format={format}
          rawContent={rawContent}
          objects={objects}
          selectMode={selectMode}
          onSelectModeChange={setSelectMode}
          summarySelectMode={summarySelectMode}
          onSummarySelectModeChange={setSummarySelectMode}
          onObjectUpdate={handleObjectUpdate}
          onObjectsUpdated={handleObjectsUpdated}
        />
      </Content>
    </Layout>
  );
}
