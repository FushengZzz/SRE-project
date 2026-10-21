import {
  Alert,
  App as AntdApp,
  AutoComplete,
  Button,
  Card,
  Empty,
  Input,
  Select,
  Space,
  Table,
  Tag,
  Typography,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import {
  ClearOutlined,
  ReloadOutlined,
  SearchOutlined,
} from '@ant-design/icons';
import { useEffect, useMemo, useState } from 'react';
import { api, ApiError } from '../api/client';
import type {
  ConversationInfo,
  Memory,
  MemoryListResponse,
  RecordStatus,
} from '../api/types';
import { RECORD_STATUS_META } from '../constants';
import { useDebouncedValue } from '../hooks';
import { formatTime } from '../utils';
import { useMemoryDrawer } from './MemoryDrawerContext';

interface Props {
  conversation: ConversationInfo;
}

export function MemoryBrowser({ conversation }: Props) {
  const { message } = AntdApp.useApp();
  const { openMemory } = useMemoryDrawer();
  const [keywordInput, setKeywordInput] = useState('');
  const keyword = useDebouncedValue(keywordInput.trim(), 350);
  const [entity, setEntity] = useState<string | undefined>();
  const [recordStatus, setRecordStatus] = useState<RecordStatus | undefined>();
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [data, setData] = useState<MemoryListResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [entityOptions, setEntityOptions] = useState<string[]>([]);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    setKeywordInput('');
    setEntity(undefined);
    setRecordStatus(undefined);
    setPage(1);
  }, [conversation.conversation_id]);

  useEffect(() => {
    let cancelled = false;
    api
      .listMemories({
        conversation_id: conversation.conversation_id,
        page: 1,
        page_size: 100,
      })
      .then((response) => {
        if (cancelled) return;
        const entities = Array.from(
          new Set(
            response.items
              .map((item) => item.entity)
              .filter((value): value is string => Boolean(value)),
          ),
        ).sort((a, b) => a.localeCompare(b));
        setEntityOptions(entities);
      })
      .catch(() => {
        // 实体候选只是输入辅助，失败时不影响主列表。
      });
    return () => {
      cancelled = true;
    };
  }, [conversation.conversation_id, reloadKey]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    api
      .listMemories({
        conversation_id: conversation.conversation_id,
        keyword: keyword || undefined,
        entity: entity || undefined,
        record_status: recordStatus,
        page,
        page_size: pageSize,
      })
      .then((response) => {
        if (!cancelled) setData(response);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setError(
          err instanceof ApiError
            ? `${err.message}（${err.code}）`
            : '加载记忆失败，请检查后端服务',
        );
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [
    conversation.conversation_id,
    keyword,
    entity,
    recordStatus,
    page,
    pageSize,
    reloadKey,
  ]);

  const columns = useMemo<ColumnsType<Memory>>(
    () => [
      {
        title: '记忆内容',
        dataIndex: 'content',
        key: 'content',
        width: 440,
        render: (content: string) => (
          <div className="memory-content-cell">
            <Typography.Paragraph
              ellipsis={{ rows: 2, tooltip: content }}
              className="memory-content-text"
            >
              {content}
            </Typography.Paragraph>
          </div>
        ),
      },
      {
        title: '实体',
        dataIndex: 'entity',
        key: 'entity',
        width: 110,
        render: (value: string | null) =>
          value ? <Tag bordered={false}>{value}</Tag> : <span className="muted">—</span>,
      },
      {
        title: '属性',
        dataIndex: 'attribute',
        key: 'attribute',
        width: 120,
        render: (value: string | null) =>
          value ? <code className="attr-code">{value}</code> : <span className="muted">—</span>,
      },
      {
        title: '会话时间',
        dataIndex: 'session_time',
        key: 'session_time',
        width: 150,
        render: (value: string | null) => (
          <span className="time-cell">{formatTime(value)}</span>
        ),
      },
      {
        title: '来源',
        dataIndex: 'sources',
        key: 'sources',
        width: 130,
        render: (sources: Memory['sources']) => {
          if (!sources.length) return <span className="muted">—</span>;
          const first = sources[0];
          return (
            <span className="source-cell">
              <Typography.Text code>{first.turn_id}</Typography.Text>
              {sources.length > 1 ? (
                <span className="muted"> +{sources.length - 1}</span>
              ) : null}
            </span>
          );
        },
      },
      {
        title: '状态',
        dataIndex: 'record_status',
        key: 'record_status',
        width: 90,
        render: (status: RecordStatus) => {
          const meta = RECORD_STATUS_META[status];
          return <Tag color={meta.color}>{meta.label}</Tag>;
        },
      },
    ],
    [],
  );

  const handleReset = () => {
    setKeywordInput('');
    setEntity(undefined);
    setRecordStatus(undefined);
    setPage(1);
  };

  const handleRefresh = () => {
    setReloadKey((key) => key + 1);
    message.success('已刷新记忆列表');
  };

  const hasFilters = Boolean(keyword || entity || recordStatus);

  return (
    <Card className="academic-card memory-card" bordered={false}>
      <div className="card-heading">
        <div>
          <div className="section-kicker">Memory Browser</div>
          <div className="card-title">结构化记忆</div>
          <div className="card-subtitle">
            浏览从原始对话抽取的 Memory，点击任意行查看结构化字段与来源证据。
          </div>
        </div>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={handleRefresh} loading={loading}>
            刷新
          </Button>
        </Space>
      </div>

      <div className="filter-bar">
        <Input
          allowClear
          prefix={<SearchOutlined />}
          placeholder="按关键词搜索记忆内容"
          value={keywordInput}
          onChange={(event) => {
            setKeywordInput(event.target.value);
            setPage(1);
          }}
          onPressEnter={() => setPage(1)}
          className="filter-keyword"
        />
        <AutoComplete
          allowClear
          options={entityOptions.map((value) => ({ value }))}
          value={entity}
          onChange={(value) => {
            setEntity(value || undefined);
            setPage(1);
          }}
          placeholder="按实体筛选（如 Caroline）"
          className="filter-entity"
          filterOption={(input, option) =>
            String(option?.value ?? '')
              .toLowerCase()
              .includes(input.toLowerCase())
          }
        />
        <Select
          allowClear
          value={recordStatus}
          onChange={(value) => {
            setRecordStatus(value);
            setPage(1);
          }}
          placeholder="记录状态"
          className="filter-status"
          options={[
            { value: 'ready', label: '就绪' },
            { value: 'needs_review', label: '待复核' },
          ]}
        />
        <Button
          icon={<ClearOutlined />}
          onClick={handleReset}
          disabled={!hasFilters}
        >
          重置
        </Button>
        <div className="filter-summary">
          共 <strong>{data?.total ?? 0}</strong> 条
          {hasFilters ? <span className="muted"> · 已筛选</span> : null}
        </div>
      </div>

      {error ? (
        <Alert
          type="error"
          showIcon
          message="记忆列表加载失败"
          description={error}
          action={
            <Button size="small" onClick={handleRefresh}>
              重试
            </Button>
          }
          className="inline-alert"
        />
      ) : null}

      <Table<Memory>
        rowKey="memory_id"
        columns={columns}
        dataSource={data?.items ?? []}
        loading={loading}
        size="middle"
        scroll={{ x: 1040 }}
        locale={{
          emptyText: (
            <Empty
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              description={
                hasFilters
                  ? '没有匹配的记忆，试试清空筛选'
                  : '该对话还没有构建记忆，请先在命令行运行 build_memories.py'
              }
            />
          ),
        }}
        onRow={(record) => ({
          onClick: () => openMemory(record.memory_id),
          className: 'clickable-row',
        })}
        pagination={{
          current: page,
          pageSize,
          total: data?.total ?? 0,
          showSizeChanger: true,
          pageSizeOptions: [10, 20, 50],
          showTotal: (total) => `共 ${total} 条`,
          onChange: (nextPage, nextPageSize) => {
            if (nextPageSize !== pageSize) {
              setPageSize(nextPageSize);
              setPage(1);
            } else {
              setPage(nextPage);
            }
          },
        }}
      />
    </Card>
  );
}
