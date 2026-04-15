import { useState, memo } from 'react';
import { Card, Tag, Badge, Switch, Typography, Space, Button, Popconfirm, Tooltip, Input, message } from 'antd';
import { DeleteOutlined, EditOutlined, CheckOutlined, CloseOutlined } from '@ant-design/icons';
import TableEditor from './TableEditor';
import ImageEditor from './ImageEditor';
import { setHeading, deleteObject, updateContent } from '../api/client';
import type { DocumentObject } from '../types';

interface Props {
  docId: string;
  obj: DocumentObject;
  onUpdate: (id: string, updated: Partial<DocumentObject>) => void;
  onDelete?: (objects: DocumentObject[]) => void;
}

const typeColor: Record<string, string> = {
  text: 'blue',
  table: 'orange',
  image: 'purple',
  summary: 'cyan',
};

export default memo(function ObjectBox({ docId, obj, onUpdate, onDelete }: Props) {
  const [collapsed, setCollapsed] = useState(true);
  const [editing, setEditing] = useState(false);
  const [editValue, setEditValue] = useState('');
  const [saving, setSaving] = useState(false);
  const update = (partial: Partial<DocumentObject>) => onUpdate(obj.id, partial);

  const handleDelete = async () => {
    const res = await deleteObject(docId, obj.id);
    onDelete?.(res.objects);
  };

  const handleHeadingToggle = async (checked: boolean) => {
    await setHeading(docId, obj.id, checked);
    onUpdate(obj.id, { is_heading: checked });
  };

  const startEdit = () => {
    setEditValue(obj.content);
    setEditing(true);
  };

  const cancelEdit = () => {
    setEditing(false);
  };

  const saveEdit = async () => {
    setSaving(true);
    try {
      await updateContent(docId, obj.id, { content: editValue });
      onUpdate(obj.id, { content: editValue });
      setEditing(false);
      message.success('저장되었습니다');
    } catch {
      // error handled by interceptor
    } finally {
      setSaving(false);
    }
  };

  const displayContent = obj.processed_content || obj.content;
  const preview = displayContent.length > 120 ? displayContent.slice(0, 120) + '…' : displayContent;

  if (obj.type === 'text' || obj.type === 'summary') {
    return (
      <div style={{ marginBottom: 8, padding: '4px 8px', borderLeft: `3px solid ${obj.is_heading ? '#1677ff' : '#d9d9d9'}` }}>
        <div style={{ display: 'flex', alignItems: 'center', marginBottom: 4, gap: 4 }}>
          <Space style={{ flex: 1, flexWrap: 'wrap' }}>
            <Tag color={typeColor[obj.type]}>{obj.type}</Tag>
            {obj.is_heading && <Tag color="blue">Heading</Tag>}
            {obj.confirm_status === 'confirmed' && <Tag color="green">Confirmed</Tag>}
            {obj.type === 'text' && (
              <Switch
                size="small"
                checked={obj.is_heading}
                onChange={handleHeadingToggle}
                checkedChildren="H"
                unCheckedChildren="T"
              />
            )}
          </Space>
          {!editing && (
            <Tooltip title="편집">
              <Button size="small" icon={<EditOutlined />} type="text" onClick={startEdit} />
            </Tooltip>
          )}
          <Popconfirm
            title="객체를 삭제할까요?"
            onConfirm={handleDelete}
            okText="삭제"
            cancelText="취소"
            okButtonProps={{ danger: true }}
          >
            <Tooltip title="삭제">
              <Button size="small" danger icon={<DeleteOutlined />} type="text" />
            </Tooltip>
          </Popconfirm>
        </div>

        {editing ? (
          <div>
            <Input.TextArea
              autoFocus
              rows={4}
              value={editValue}
              onChange={(e) => setEditValue(e.target.value)}
              style={{ fontSize: 13, marginBottom: 4 }}
            />
            <Space size={4}>
              <Button
                size="small"
                type="primary"
                icon={<CheckOutlined />}
                loading={saving}
                onClick={saveEdit}
              >
                저장
              </Button>
              <Button size="small" icon={<CloseOutlined />} onClick={cancelEdit}>
                취소
              </Button>
            </Space>
          </div>
        ) : (
          <Typography.Paragraph style={{ margin: 0, fontSize: 13, whiteSpace: 'pre-wrap' }}>
            {obj.is_heading ? <strong>{obj.content}</strong> : obj.content}
          </Typography.Paragraph>
        )}
      </div>
    );
  }

  return (
    <Badge.Ribbon
      text={obj.confirm_status === 'confirmed' ? '✓ Confirmed' : ''}
      color={obj.confirm_status === 'confirmed' ? 'green' : 'transparent'}
    >
      <Card
        size="small"
        style={{ marginBottom: 8, cursor: 'pointer' }}
        styles={{ body: { padding: '8px 12px' } }}
        onClick={() => setCollapsed((v) => !v)}
        title={
          <Space>
            <Tag color={typeColor[obj.type]}>{obj.type.toUpperCase()}</Tag>
            {obj.page && <Typography.Text type="secondary" style={{ fontSize: 11 }}>p.{obj.page}</Typography.Text>}
          </Space>
        }
        extra={
          <Popconfirm
            title={`${obj.type === 'image' ? '이미지' : '테이블'} 객체를 삭제할까요?`}
            onConfirm={(e) => { e?.stopPropagation(); handleDelete(); }}
            onCancel={(e) => e?.stopPropagation()}
            okText="삭제"
            cancelText="취소"
            okButtonProps={{ danger: true }}
          >
            <Button
              size="small"
              danger
              icon={<DeleteOutlined />}
              onClick={(e) => e.stopPropagation()}
            />
          </Popconfirm>
        }
      >
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
          {preview}
        </Typography.Text>

        {!collapsed && (
          <div style={{ marginTop: 12 }} onClick={(e) => e.stopPropagation()}>
            {obj.type === 'table' && (
              <TableEditor docId={docId} obj={obj} onUpdate={update} />
            )}
            {obj.type === 'image' && (
              <ImageEditor docId={docId} obj={obj} onUpdate={update} onDelete={onDelete} />
            )}
          </div>
        )}
      </Card>
    </Badge.Ribbon>
  );
});
