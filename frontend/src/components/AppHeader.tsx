import { Tag } from 'antd';
import { NodeIndexOutlined } from '@ant-design/icons';
import type { Health } from '../api/types';

interface Props {
  health: Health | null;
}

export function AppHeader({ health }: Props) {
  const providerLabel =
    health?.llm_provider === 'mock'
      ? 'mock 演示模式'
      : health?.llm_model || health?.llm_provider || 'LLM';

  return (
    <header className="app-header">
      <div className="header-inner">
        <div className="brand">
          <div className="brand-mark" aria-hidden>
            <NodeIndexOutlined />
          </div>
          <div className="brand-copy">
            <div className="brand-title">智能体动态记忆管理</div>
            <div className="brand-sub">AGENT DYNAMIC MEMORY MANAGEMENT</div>
          </div>
        </div>

        <div className="header-right">
          {health ? (
            <Tag
              color={health.llm_provider === 'mock' ? 'gold' : 'green'}
              className="provider-tag"
            >
              LLM · {providerLabel}
            </Tag>
          ) : null}
        </div>
      </div>
    </header>
  );
}
