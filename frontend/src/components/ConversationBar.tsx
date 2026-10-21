import { App as AntdApp, Button, Select, Tag, Tooltip } from 'antd';
import {
  DownloadOutlined,
  ReloadOutlined,
  SwapOutlined,
} from '@ant-design/icons';
import { useState } from 'react';
import { api, ApiError } from '../api/client';
import type { ConversationInfo } from '../api/types';
import { SPLIT_META } from '../constants';
import { downloadBlob } from '../utils';

interface Props {
  conversations: ConversationInfo[];
  selectedId: string;
  onSelect: (id: string) => void;
  onRefresh: () => void;
  refreshing: boolean;
}

export function ConversationBar({
  conversations,
  selectedId,
  onSelect,
  onRefresh,
  refreshing,
}: Props) {
  const { message } = AntdApp.useApp();
  const [exporting, setExporting] = useState(false);
  const selected = conversations.find((item) => item.conversation_id === selectedId);
  const isSynthetic = selected?.conversation_id.startsWith('synthetic-') ?? false;
  const split = isSynthetic
    ? { label: '合成用例', color: 'gold' }
    : SPLIT_META[selected?.split ?? ''] ?? {
        label: selected?.split ?? '未知',
        color: 'default',
      };

  const handleExport = async () => {
    if (!selected) return;
    setExporting(true);
    try {
      const { blob, filename } = await api.exportMemories(selected.conversation_id);
      downloadBlob(blob, filename);
      message.success(`已导出 ${encodedCount(selected.memory_count)} 条记忆 JSON`);
    } catch (error) {
      const text =
        error instanceof ApiError
          ? `${error.message}（${error.code}）`
          : '导出失败，请检查后端服务';
      message.error(text);
    } finally {
      setExporting(false);
    }
  };

  return (
    <section className="context-bar academic-card">
      <div className="context-primary">
        <div className="context-label">
          <SwapOutlined />
          <span>当前对话</span>
        </div>
        <Select
          value={selectedId || undefined}
          onChange={onSelect}
          className="conversation-select"
          popupMatchSelectWidth={380}
          placeholder="选择一段对话"
          options={conversations.map((item) => ({
            value: item.conversation_id,
            label: (
              <span className="conversation-option">
                <strong>{item.conversation_id}</strong>
                {item.conversation_id.startsWith('synthetic-') ? (
                  <Tag color="gold" bordered={false}>
                    合成
                  </Tag>
                ) : null}
                <span className="muted">
                  {item.memory_count} 条记忆 · {item.session_count} 个会话
                </span>
              </span>
            ),
          }))}
        />
        {selected ? (
          <Tag color={split.color} className="split-tag">
            {split.label}
          </Tag>
        ) : null}
      </div>

      {selected ? (
        <div className="context-stats">
          <div className="context-stat">
            <span className="context-stat-value">{selected.session_count}</span>
            <span className="context-stat-label">会话</span>
          </div>
          <div className="context-stat">
            <span className="context-stat-value">{selected.turn_count}</span>
            <span className="context-stat-label">轮次</span>
          </div>
          <div className="context-stat">
            <span className="context-stat-value">{selected.memory_count}</span>
            <span className="context-stat-label">结构化记忆</span>
          </div>
        </div>
      ) : null}

      <div className="context-actions">
        <Tooltip title="重新读取对话与记忆统计">
          <Button
            icon={<ReloadOutlined />}
            loading={refreshing}
            onClick={onRefresh}
          >
            刷新
          </Button>
        </Tooltip>
        <Tooltip title="导出该对话的结构化记忆 JSON">
          <Button
            icon={<DownloadOutlined />}
            loading={exporting}
            disabled={!selected || selected.memory_count === 0}
            onClick={handleExport}
          >
            导出 JSON
          </Button>
        </Tooltip>
      </div>
    </section>
  );
}

function encodedCount(count: number): string {
  return new Intl.NumberFormat('zh-CN').format(count);
}
