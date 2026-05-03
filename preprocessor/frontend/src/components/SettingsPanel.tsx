import { useState, useEffect } from 'react';
import { Card, Form, Input, Button, Space, Tag, message } from 'antd';
import { listKeys, saveKey } from '../api/client';

export default function SettingsPanel() {
  const [wikiPass, setWikiPass] = useState('');
  const [status, setStatus] = useState<Record<string, boolean>>({});

  useEffect(() => {
    listKeys().then(setStatus).catch(() => {});
  }, []);

  const handleSaveWikiPass = async () => {
    await saveKey('WIKI_AGENT_PASSWORD', wikiPass);
    message.success('Wiki Agent 비밀번호가 저장되었습니다');
    const updated = await listKeys();
    setStatus(updated);
    setWikiPass('');
  };

  return (
    <Card title="연동 설정" size="small">
      <Form layout="vertical" size="small">
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
