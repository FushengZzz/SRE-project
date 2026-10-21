import {
  Alert,
  Descriptions,
  Divider,
  Drawer,
  Skeleton,
  Tag,
  Typography,
} from 'antd';
import { useEffect, useState } from 'react';
import { api, ApiError } from '../api/client';
import type { MemoryEvidenceResponse } from '../api/types';
import { RECORD_STATUS_META } from '../constants';
import { formatTime } from '../utils';

interface Props {
  memoryId: string | null;
  open: boolean;
  onClose: () => void;
}

export function MemoryDrawer({ memoryId, open, onClose }: Props) {
  const [data, setData] = useState<MemoryEvidenceResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open || !memoryId) {
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    setData(null);
    api
      .getMemoryEvidence(memoryId)
      .then((response) => {
        if (!cancelled) setData(response);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setError(
          err instanceof ApiError
            ? `${err.message}（${err.code}）`
            : '加载记忆详情失败，请检查后端服务',
        );
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [open, memoryId]);

  const memory = data?.memory;
  const recordMeta = memory ? RECORD_STATUS_META[memory.record_status] : null;

  return (
    <Drawer
      open={open}
      onClose={onClose}
      width={760}
      destroyOnClose
      className="memory-drawer"
      title={
        <div className="drawer-title">
          <span>记忆详情</span>
          <span className="drawer-subtitle">Memory detail</span>
        </div>
      }
    >
      {loading ? (
        <Skeleton active paragraph={{ rows: 10 }} />
      ) : error ? (
        <Alert type="error" showIcon message="无法加载记忆" description={error} />
      ) : memory && data ? (
        <>
          <div className="drawer-status-row">
            {recordMeta ? (
              <Tag color={recordMeta.color}>{recordMeta.label}</Tag>
            ) : null}
            <span className="muted">来源 {data.sources.length} 条轮次</span>
            <span className="muted">会话时间 {formatTime(memory.session_time)}</span>
          </div>

          <div className="memory-quote">{memory.content}</div>

          <Divider orientation="left" className="section-divider">
            结构化字段
          </Divider>
          <Descriptions
            bordered
            size="small"
            column={1}
            labelStyle={{ width: 150 }}
            contentStyle={{ background: '#fff' }}
            items={[
              {
                key: 'memory_id',
                label: 'Memory ID',
                children: (
                  <Typography.Text code copyable={{ text: memory.memory_id }}>
                    {memory.memory_id}
                  </Typography.Text>
                ),
              },
              {
                key: 'conversation_id',
                label: '对话 ID',
                children: memory.conversation_id,
              },
              {
                key: 'entity',
                label: '实体 Entity',
                children: memory.entity ?? <span className="muted">未抽取</span>,
              },
              {
                key: 'attribute',
                label: '属性 Attribute',
                children: memory.attribute ?? <span className="muted">未抽取</span>,
              },
              {
                key: 'value',
                label: '值 Value',
                children: memory.value ?? <span className="muted">未抽取</span>,
              },
              {
                key: 'session_time',
                label: '会话时间',
                children: formatTime(memory.session_time),
              },
              {
                key: 'time_expression',
                label: '时间表达',
                children:
                  memory.time_expression ?? <span className="muted">原文未标注</span>,
              },
              {
                key: 'event_time',
                label: '事件时间',
                children:
                  memory.event_time ?? (
                    <span className="muted">无法解析（不以记录时间补齐）</span>
                  ),
              },
              {
                key: 'sources',
                label: '来源定位',
                children: memory.sources
                  .map((source) => `会话 ${source.session_id} / ${source.turn_id}`)
                  .join('；'),
              },
            ]}
          />

          <Divider orientation="left" className="section-divider">
            来源证据 · {data.sources.length}
          </Divider>
          {data.sources.length === 0 ? (
            <Alert
              type="warning"
              showIcon
              message="该记忆没有可定位的来源轮次"
              description="后端会报告错误，不会展示其他轮次替代。"
            />
          ) : (
            <div className="evidence-list">
              {data.sources.map((source, index) => (
                <div
                  className="evidence-item"
                  key={`${source.session_id}-${source.turn_id}-${index}`}
                >
                  <div className="evidence-head">
                    <Tag color="blue" bordered={false}>
                      {source.speaker}
                    </Tag>
                    <Typography.Text code>{source.turn_id}</Typography.Text>
                    <span
                      className="muted"
                      title={source.session_raw_time ?? undefined}
                    >
                      会话 {source.session_id} · {formatTime(source.session_parsed_time)}
                    </span>
                  </div>
                  <Typography.Paragraph className="evidence-text">
                    {source.text}
                  </Typography.Paragraph>
                </div>
              ))}
            </div>
          )}
        </>
      ) : null}
    </Drawer>
  );
}
