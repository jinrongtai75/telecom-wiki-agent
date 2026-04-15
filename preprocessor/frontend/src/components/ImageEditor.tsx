import { useState } from 'react';
import { Button, Input, Space, Spin, Tag, Radio, Typography, Divider, Tooltip } from 'antd';
import { SaveOutlined } from '@ant-design/icons';
import { linkImage, interpretImage, chatImage, confirmObject } from '../api/client';
import type { DocumentObject } from '../types';

interface Props {
  docId: string;
  obj: DocumentObject;
  onUpdate: (updated: Partial<DocumentObject>) => void;
  onDelete?: (objects: DocumentObject[]) => void;
}

export default function ImageEditor({ docId, obj, onUpdate, onDelete }: Props) {
  const [mode, setMode] = useState<'link' | 'vlm'>('link');
  const [linkText, setLinkText] = useState('');
  const [content, setContent] = useState(obj.processed_content || '');
  const [chatMsg, setChatMsg] = useState('');
  const [loading, setLoading] = useState(false);

  const handleLink = async () => {
    setLoading(true);
    try {
      const res = await linkImage(docId, obj.id, linkText);
      setContent(res.processed_content);
      onUpdate({ image_path: res.image_path, processed_content: res.processed_content });
    } finally {
      setLoading(false);
    }
  };

  const handleInterpret = async () => {
    setLoading(true);
    try {
      const res = await interpretImage(docId, obj.id);
      setContent(res.processed_content);
      onUpdate({ processed_content: res.processed_content, image_path: res.image_path });
    } finally {
      setLoading(false);
    }
  };

  const handleChat = async () => {
    if (!chatMsg) return;
    setLoading(true);
    try {
      const res = await chatImage(docId, obj.id, chatMsg);
      setContent(res.processed_content);
      onUpdate({ processed_content: res.processed_content });
      setChatMsg('');
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
        <Radio.Group value={mode} onChange={(e) => setMode(e.target.value)} size="small">
          <Radio.Button value="link">지정 텍스트에 링크로 연결</Radio.Button>
          <Radio.Button value="vlm">VLM으로 이미지 해석</Radio.Button>
        </Radio.Group>

        {mode === 'link' ? (
          <Space.Compact style={{ width: '100%' }}>
            <Input
              value={linkText}
              onChange={(e) => setLinkText(e.target.value)}
              placeholder="연결할 텍스트 입력..."
            />
            <Button onClick={handleLink}>연결</Button>
          </Space.Compact>
        ) : (
          <>
            <Button onClick={handleInterpret} block>VLM 해석 실행</Button>
            {obj.image_path && (
              <Tooltip title={obj.image_path}>
                <Typography.Text type="secondary" style={{ fontSize: 11 }}>
                  <SaveOutlined style={{ marginRight: 4 }} />
                  이미지 저장됨: {obj.image_path}
                </Typography.Text>
              </Tooltip>
            )}
          </>
        )}

        {content && (
          <>
            <Input.TextArea
              rows={5}
              value={content}
              onChange={(e) => setContent(e.target.value)}
            />
            <Divider style={{ margin: '8px 0' }} />
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>채팅으로 수정 요청</Typography.Text>
            <Space.Compact style={{ width: '100%' }}>
              <Input
                value={chatMsg}
                onChange={(e) => setChatMsg(e.target.value)}
                placeholder="수정 요청사항 입력..."
                onPressEnter={handleChat}
              />
              <Button onClick={handleChat}>전송</Button>
            </Space.Compact>
          </>
        )}

        <Space>
          {obj.confirm_status === 'confirmed' && <Tag color="green">Confirmed</Tag>}
          <Button
            type="primary"
            onClick={handleConfirm}
            disabled={obj.confirm_status === 'confirmed' || !content}
          >
            Confirm
          </Button>
        </Space>
      </Space>
    </Spin>
  );
}
