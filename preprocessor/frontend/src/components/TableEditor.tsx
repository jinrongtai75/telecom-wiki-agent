import { useState } from 'react';
import { Button, Input, Space, Spin, Tag, Typography, Divider, message } from 'antd';
import { flattenTable, chatTable, confirmObject, updateContent } from '../api/client';
import type { DocumentObject } from '../types';

interface Props {
  docId: string;
  obj: DocumentObject;
  onUpdate: (updated: Partial<DocumentObject>) => void;
}

export default function TableEditor({ docId, obj, onUpdate }: Props) {
  const [content, setContent] = useState(obj.processed_content || obj.content);
  const [chatMsg, setChatMsg] = useState('');
  const [loading, setLoading] = useState(false);

  const run = async (fn: () => Promise<{ processed_content: string }>) => {
    setLoading(true);
    try {
      const res = await fn();
      setContent(res.processed_content);
      onUpdate({ processed_content: res.processed_content });
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    setLoading(true);
    try {
      await updateContent(docId, obj.id, { processed_content: content });
      onUpdate({ processed_content: content });
      message.success('저장되었습니다');
    } catch {
      // error handled by interceptor
    } finally {
      setLoading(false);
    }
  };

  const handleConfirm = async () => {
    setLoading(true);
    try {
      await confirmObject(docId, obj.id, { processed_content: content });
      onUpdate({ confirm_status: 'confirmed', processed_content: content });
    } finally {
      setLoading(false);
    }
  };

  return (
    <Spin spinning={loading}>
      <Space direction="vertical" style={{ width: '100%' }}>
        <Space wrap>
          <Button size="small" onClick={() => run(() => flattenTable(docId, obj.id))}>
            LLM text flattening
          </Button>
          {obj.confirm_status === 'confirmed' && <Tag color="green">Confirmed</Tag>}
        </Space>

        <Input.TextArea
          rows={6}
          value={content}
          onChange={(e) => setContent(e.target.value)}
        />

        <Space style={{ width: '100%' }}>
          <Button block onClick={handleSave} style={{ flex: 1 }}>
            저장
          </Button>
          <Button type="primary" block onClick={handleConfirm} disabled={obj.confirm_status === 'confirmed'} style={{ flex: 1 }}>
            Confirm
          </Button>
        </Space>

        <Divider style={{ margin: '8px 0' }} />
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>채팅으로 수정 요청</Typography.Text>
        <Space.Compact style={{ width: '100%' }}>
          <Input
            value={chatMsg}
            onChange={(e) => setChatMsg(e.target.value)}
            placeholder="수정 요청사항 입력..."
            onPressEnter={() => {
              if (chatMsg) run(() => chatTable(docId, obj.id, chatMsg)).then(() => setChatMsg(''));
            }}
          />
          <Button
            onClick={() => {
              if (chatMsg) run(() => chatTable(docId, obj.id, chatMsg)).then(() => setChatMsg(''));
            }}
          >
            전송
          </Button>
        </Space.Compact>
      </Space>
    </Spin>
  );
}
