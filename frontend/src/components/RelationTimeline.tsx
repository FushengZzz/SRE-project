import { Button, Tag, Timeline, Typography } from 'antd';
import { ArrowDownOutlined, CheckCircleOutlined } from '@ant-design/icons';
import type { Memory, Relation } from '../api/types';
import { RELATION_META } from '../constants';
import { formatTime, shortMemoryId } from '../utils';
import { useMemoryDrawer } from './MemoryDrawerContext';

interface Props {
  relations: Relation[];
  memories: Map<string, Memory>;
}

export function RelationTimeline({ relations, memories }: Props) {
  const { openMemory } = useMemoryDrawer();

  if (relations.length === 0) {
    return (
      <div className="relation-empty">
        <CheckCircleOutlined className="relation-empty-icon" />
        <div>
          <div className="relation-empty-title">未发现更新、替代或冲突关系</div>
          <div className="muted">
            候选记忆在当前时间条件下兼容，系统按有效证据继续生成回答。
          </div>
        </div>
      </div>
    );
  }

  const items = relations.map((relation) => {
    const meta = RELATION_META[relation.type];
    const from = memories.get(relation.from_memory_id);
    const to = memories.get(relation.to_memory_id);
    const directional = relation.type === 'UPDATE' || relation.type === 'SUPERSEDE';
    const fromLabel = directional ? '旧状态' : '记忆 A';
    const toLabel = directional ? '新状态' : '记忆 B';

    return {
      color: meta.color,
      children: (
        <div className="relation-card">
          <div className="relation-head">
            <Tag color={meta.color} className="relation-type-tag">
              {meta.label} · {relation.type}
            </Tag>
            <span className="muted">{meta.hint}</span>
          </div>

          <div className="relation-nodes">
            <div className="relation-node">
              <span className="node-badge">{fromLabel}</span>
              <div className="node-body">
                <div className="node-content">
                  {from?.content ?? (
                    <span className="muted">记忆 {shortMemoryId(relation.from_memory_id)}</span>
                  )}
                </div>
                <div className="muted">
                  {from ? formatTime(from.session_time) : relation.from_memory_id}
                </div>
              </div>
            </div>
            <div className="relation-arrow">
              <ArrowDownOutlined />
            </div>
            <div className="relation-node">
              <span className="node-badge node-badge-new">{toLabel}</span>
              <div className="node-body">
                <div className="node-content">
                  {to?.content ?? (
                    <span className="muted">记忆 {shortMemoryId(relation.to_memory_id)}</span>
                  )}
                </div>
                <div className="muted">
                  {to ? formatTime(to.session_time) : relation.to_memory_id}
                </div>
              </div>
            </div>
          </div>

          <Typography.Paragraph
            className="relation-reason"
            ellipsis={{ rows: 3, expandable: true, symbol: '展开理由' }}
          >
            {relation.reason}
          </Typography.Paragraph>

          <div className="relation-evidence">
            <span className="muted">证据记忆</span>
            {relation.evidence_memory_ids.length ? (
              relation.evidence_memory_ids.map((id) => (
                <Button
                  key={id}
                  type="link"
                  size="small"
                  className="evidence-id"
                  onClick={() => openMemory(id)}
                >
                  {shortMemoryId(id)}
                </Button>
              ))
            ) : (
              <span className="muted">—</span>
            )}
          </div>
        </div>
      ),
    };
  });

  return <Timeline className="relation-timeline" items={items} />;
}
