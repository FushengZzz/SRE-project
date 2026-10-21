import { Progress, Table, Tag, Tooltip, Typography } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import type { CandidateValidity, MemoryWithScore } from '../api/types';
import { VALIDITY_META } from '../constants';
import { formatTime } from '../utils';
import { useMemoryDrawer } from './MemoryDrawerContext';

interface Props {
  candidates: MemoryWithScore[];
  validity: CandidateValidity[];
}

export function CandidateTable({ candidates, validity }: Props) {
  const { openMemory } = useMemoryDrawer();
  const validityMap = new Map(validity.map((item) => [item.memory_id, item]));

  const columns: ColumnsType<MemoryWithScore> = [
    {
      title: '候选记忆',
      key: 'content',
      width: 380,
      render: (_, record) => (
        <div className="candidate-content">
          <Typography.Paragraph
            ellipsis={{ rows: 2, tooltip: record.memory.content }}
            className="candidate-content-text"
          >
            {record.memory.content}
          </Typography.Paragraph>
          <div className="muted">
            {record.memory.entity ?? '未抽取实体'}
            {record.memory.attribute ? ` · ${record.memory.attribute}` : ''}
            {record.memory.session_time ? ` · ${formatTime(record.memory.session_time)}` : ''}
          </div>
        </div>
      ),
    },
    {
      title: '相关度',
      dataIndex: 'score',
      key: 'score',
      width: 120,
      render: (score: number) => (
        <div className="score-cell">
          <Progress
            percent={Math.round(score * 100)}
            size="small"
            showInfo={false}
            strokeColor="#2563eb"
          />
          <span className="score-value">{score.toFixed(3)}</span>
        </div>
      ),
    },
    {
      title: '有效性',
      key: 'validity',
      width: 100,
      render: (_, record) => {
        const item = validityMap.get(record.memory.memory_id);
        if (!item) {
          return <span className="muted">—</span>;
        }
        const meta = VALIDITY_META[item.status];
        return (
          <Tooltip title={item.reason}>
            <Tag color={meta.color}>{meta.label}</Tag>
          </Tooltip>
        );
      },
    },
    {
      title: '判定理由',
      key: 'reason',
      width: 300,
      render: (_, record) => {
        const item = validityMap.get(record.memory.memory_id);
        if (!item) return <span className="muted">—</span>;
        return (
          <Typography.Paragraph
            ellipsis={{ rows: 2, tooltip: item.reason }}
            className="reason-text"
          >
            {item.reason}
          </Typography.Paragraph>
        );
      },
    },
    {
      title: '来源',
      key: 'source',
      width: 110,
      render: (_, record) => {
        const source = record.memory.sources[0];
        if (!source) return <span className="muted">—</span>;
        return (
          <Typography.Text code>
            {source.turn_id}
            {record.memory.sources.length > 1
              ? ` +${record.memory.sources.length - 1}`
              : ''}
          </Typography.Text>
        );
      },
    },
  ];

  return (
    <Table<MemoryWithScore>
      rowKey={(record) => record.memory.memory_id}
      columns={columns}
      dataSource={candidates}
      pagination={false}
      size="small"
      scroll={{ x: 980 }}
      onRow={(record) => ({
        onClick: () => openMemory(record.memory.memory_id),
        className: 'clickable-row candidate-row',
      })}
      rowClassName={(record) => {
        const item = validityMap.get(record.memory.memory_id);
        return item?.status === 'effective' ? 'candidate-effective-row' : '';
      }}
    />
  );
}
