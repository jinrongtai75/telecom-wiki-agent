import { useState, useEffect } from 'react';
import { Card, Form, Input, Button, Space, Tag, message } from 'antd';
import { listKeys, saveKey, validateKey } from '../api/client';

export default function SettingsPanel() {
  const [jihyeToken, setJihyeToken] = useState('');
  const [wikiPass, setWikiPass] = useState('');
  const [status, setStatus] = useState<Record<string, boolean>>({});

  useEffect(() => {
    listKeys().then(setStatus).catch(() => {});
  }, []);

  const handleSaveJihye = async () => {
    await saveKey('JIHYE', jihyeToken);
    message.success('JIHYE 토큰이 저장되었습니다');
    const updated = await listKeys();
    setStatus(updated);
    setJihyeToken('');
  };

  const handleSaveWikiPass = async () => {
    await saveKey('WIKI_AGENT_PASSWORD', wikiPass);
    message.success('Wiki Agent 비밀번호가 저장되었습니다');
    const updated = await listKeys();
    setStatus(updated);
    setWikiPass('');
  };

  const handleValidate = async () => {
    try {
      await validateKey('JIHYE');
      message.success('JIHYE 토큰이 유효합니다');
    } catch {
      // 에러는 interceptor에서 처리
    }
  };

  return (
    <Card title="API 설정" size="small">
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

        <Form.Item
          label={
            <Space>
              Wiki Agent 비밀번호
              {status.wiki_agent ? <Tag color="green">등록됨</Tag> : <Tag color="red">미등록</Tag>}
            </Space>
          }
          extra="위키에이전트 관리자 비밀번호 (적재 시 자동 로그인)"
        >
          <Space.Compact style={{ width: '100%' }}>
            <Input.Password
              value={wikiPass}
              onChange={(e) => setWikiPass(e.target.value)}
              placeholder="비밀번호 입력"
            />
            <Button onClick={handleSaveWikiPass} disabled={!wikiPass}>저장</Button>
          </Space.Compact>
        </Form.Item>
      </Form>
    </Card>
  );
}
