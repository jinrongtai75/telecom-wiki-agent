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
    <Layout style={{ height: '100vh' }}>
      <Sider
        width={260}
        theme="light"
        style={{ borderRight: '1px solid #e8e8e8', overflowY: 'auto', background: '#fafafa' }}
      >
        <div style={{
          padding: '14px 16px 12px',
          borderBottom: '1px solid #e8e8e8',
          background: '#fafafa',
        }}>
          <div style={{ fontSize: 13, fontWeight: 700, color: '#1a1a1a', letterSpacing: '-0.2px' }}>
            문서 전처리 도구
          </div>
          <div style={{ fontSize: 11, color: '#8c8c8c', marginTop: 2 }}>RAG Pipeline Preprocessor</div>
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

      <Content style={{ height: '100vh', overflow: 'hidden' }}>
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
