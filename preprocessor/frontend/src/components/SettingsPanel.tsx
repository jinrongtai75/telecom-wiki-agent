import { useState, useEffect } from 'react';
import axios from 'axios';
import { Card, Form, Input, Button, Space, Tag, message, Divider } from 'antd';
import { listKeys, saveKey, validateKey, getWikiAgentConfig, setWikiAgentConfig } from '../api/client';

export default function SettingsPanel() {
  const [jihyeToken, setJihyeToken] = useState('');
  const [status, setStatus] = useState<Record<string, boolean>>({});

  // Wiki Agent 연동
  const [wikiUrl, setWikiUrl] = useState(import.meta.env.VITE_WIKI_AGENT_URL ?? 'http://localhost:8001');
  const [wikiToken, setWikiToken] = useState('');
  const [wikiSaved, setWikiSaved] = useState(false);

  useEffect(() => {
    listKeys().then(setStatus).catch(() => {});
    const cfg = getWikiAgentConfig();
    setWikiUrl(cfg.url);
    setWikiSaved(!!cfg.token);
    if (cfg.token) setWikiToken('••••••••');
  }, []);

  const handleSaveJihye = async () => {
    await saveKey('JIHYE', jihyeToken);

    // wiki agent에도 JIHYE 토큰 동기화 (연결된 경우)
    const cfg = getWikiAgentConfig();
    if (cfg.url && cfg.token && jihyeToken && !jihyeToken.startsWith('•')) {
      try {
        await axios.post(
          `${cfg.url}/api/settings/keys`,
          { service: 'JIHYE', api_key: jihyeToken },
          { headers: { Authorization: `Bearer ${cfg.token}` } },
        );
      } catch {
        // wiki agent 미연결 시 무시
      }
    }

    message.success('JIHYE 토큰이 저장되었습니다 (Wiki Agent 동기화 포함)');
    const updated = await listKeys();
    setStatus(updated);
    setJihyeToken('');
  };

  const handleValidate = async () => {
    try {
      await validateKey('JIHYE');
      message.success('JIHYE 토큰이 유효합니다');
    } catch {
      // 에러는 interceptor에서 처리
    }
  };

  const handleSaveWiki = () => {
    const cfg = getWikiAgentConfig();
    const token = wikiToken.startsWith('•') ? cfg.token : wikiToken;
    setWikiAgentConfig(wikiUrl || import.meta.env.VITE_WIKI_AGENT_URL || 'http://localhost:8001', token);
    setWikiSaved(!!token);
    message.success('Wiki Agent 설정이 저장되었습니다');
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {/* JIHYE 토큰 */}
      <Card title="LLM API 설정" size="small">
        <Form layout="vertical" size="small">
          <Form.Item
            label={
              <Space>
                JIHYE 게이트웨이 토큰
                {status.jihye ? <Tag color="green">등록됨</Tag> : <Tag color="red">미등록</Tag>}
              </Space>
            }
            extra="사내 Claude API 게이트웨이 JWT 토큰"
          >
            <Space.Compact style={{ width: '100%' }}>
              <Input.Password
                value={jihyeToken}
                onChange={(e) => setJihyeToken(e.target.value)}
                placeholder="eyJhbGci..."
              />
              <Button onClick={handleSaveJihye} disabled={!jihyeToken}>저장</Button>
              <Button onClick={handleValidate}>검증</Button>
            </Space.Compact>
          </Form.Item>
        </Form>
      </Card>

      <Divider style={{ margin: '4px 0' }} />

      {/* Wiki Agent 연동 */}
      <Card
        title={
          <Space>
            Wiki Agent 연동
            {wikiSaved ? <Tag color="green">연결됨</Tag> : <Tag color="orange">미설정</Tag>}
          </Space>
        }
        size="small"
      >
        <Form layout="vertical" size="small">
          <Form.Item label="Wiki Agent URL" style={{ marginBottom: 6 }}>
            <Input
              value={wikiUrl}
              onChange={(e) => setWikiUrl(e.target.value)}
              placeholder="http://localhost:8001"
            />
          </Form.Item>
          <Form.Item
            label="JWT 토큰"
            extra="Wiki Agent 로그인 후 발급된 JWT"
            style={{ marginBottom: 8 }}
          >
            <Input.Password
              value={wikiToken}
              onChange={(e) => setWikiToken(e.target.value)}
              placeholder="eyJhbGci..."
              onFocus={() => { if (wikiToken.startsWith('•')) setWikiToken(''); }}
            />
          </Form.Item>
          <Button block size="small" type="primary" onClick={handleSaveWiki}>
            저장
          </Button>
        </Form>
      </Card>
    </div>
  );
}
