import { useState, useEffect } from 'react';
import { Card, Form, Input, Button, Space, Tag, message, Segmented } from 'antd';
import { listKeys, saveKey, getLlmMode, setLlmMode } from '../api/client';

export default function SettingsPanel() {
  const [wikiPass, setWikiPass] = useState('');
  const [status, setStatus] = useState<Record<string, boolean>>({});
  const [llmMode, setLlmModeState] = useState<'fast' | 'thinking'>('fast');
  const [llmSaving, setLlmSaving] = useState(false);

  useEffect(() => {
    listKeys().then(setStatus).catch(() => {});
    getLlmMode().then((r) => setLlmModeState(r.mode)).catch(() => {});
  }, []);

  const handleSaveWikiPass = async () => {
    await saveKey('WIKI_AGENT_PASSWORD', wikiPass);
    message.success('Wiki Agent 비밀번호가 저장되었습니다');
    const updated = await listKeys();
    setStatus(updated);
    setWikiPass('');
  };

  const handleLlmModeChange = async (val: string) => {
    const mode = val as 'fast' | 'thinking';
    setLlmSaving(true);
    try {
      await setLlmMode(mode);
      setLlmModeState(mode);
      message.success(mode === 'fast' ? '빠른 모드로 변경되었습니다' : '사고 모드로 변경되었습니다');
    } catch {
      message.error('LLM 모드 변경 실패');
    } finally {
      setLlmSaving(false);
    }
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

        <Form.Item
          label="LLM 모드"
          extra={llmMode === 'fast' ? '⚡ thinking 비활성화 — 빠른 응답' : '🧠 extended thinking 활성화 — 복잡한 분석에 적합'}
        >
          <Segmented
            block
            disabled={llmSaving}
            value={llmMode}
            onChange={handleLlmModeChange}
            options={[
              { label: '⚡ 빠른 모드', value: 'fast' },
              { label: '🧠 사고 모드', value: 'thinking' },
            ]}
          />
        </Form.Item>
      </Form>
    </Card>
  );
}
