import { Alert, Button, Card, Empty, Spin, Tabs, Typography } from 'antd';
import {
  DatabaseOutlined,
  MessageOutlined,
  ReloadOutlined,
} from '@ant-design/icons';
import { useCallback, useEffect, useState } from 'react';
import { api, ApiError } from './api/client';
import type { ConversationInfo, Health } from './api/types';
import { AppHeader } from './components/AppHeader';
import { ConversationBar } from './components/ConversationBar';
import { MemoryBrowser } from './components/MemoryBrowser';
import { MemoryDrawerProvider } from './components/MemoryDrawerContext';
import { QueryWorkbench } from './components/QueryWorkbench';

const SELECTED_CONVERSATION_KEY = 'dm.selectedConversation';

export default function App() {
  const [conversations, setConversations] = useState<ConversationInfo[]>([]);
  const [health, setHealth] = useState<Health | null>(null);
  const [selectedId, setSelectedId] = useState<string>(
    () => window.localStorage.getItem(SELECTED_CONVERSATION_KEY) ?? '',
  );
  const [activeTab, setActiveTab] = useState('memories');
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (mode: 'initial' | 'refresh' = 'refresh') => {
    if (mode === 'initial') setLoading(true);
    else setRefreshing(true);
    setError(null);
    try {
      const conversationList = await api.listConversations();
      setConversations(conversationList);
      try {
        setHealth(await api.health());
      } catch {
        setHealth(null);
      }
    } catch (err: unknown) {
      setError(
        err instanceof ApiError
          ? `${err.message}（${err.code}）`
          : '无法连接后端服务，请确认 uvicorn 已在 127.0.0.1:8000 启动',
      );
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    void load('initial');
  }, [load]);

  useEffect(() => {
    if (!conversations.length) return;
    const exists = conversations.some(
      (conversation) => conversation.conversation_id === selectedId,
    );
    if (!selectedId || !exists) {
      const preferred =
        conversations.find(
          (conversation) => conversation.conversation_id === 'conv-26',
        ) ?? conversations[0];
      setSelectedId(preferred.conversation_id);
    }
  }, [conversations, selectedId]);

  useEffect(() => {
    if (selectedId) {
      window.localStorage.setItem(SELECTED_CONVERSATION_KEY, selectedId);
    }
  }, [selectedId]);

  const selected =
    conversations.find(
      (conversation) => conversation.conversation_id === selectedId,
    ) ?? null;

  return (
    <MemoryDrawerProvider>
      <div className="app-shell">
        <AppHeader health={health} />
        <main className="page">
          {loading ? (
            <div className="page-loading">
              <Spin size="large" />
              <div className="muted">正在读取对话与记忆数据…</div>
            </div>
          ) : (
            <>
              {error ? (
                <Alert
                  type="error"
                  showIcon
                  className="inline-alert"
                  message="后端连接失败"
                  description={error}
                  action={
                    <Button size="small" onClick={() => void load('refresh')}>
                      重试
                    </Button>
                  }
                />
              ) : null}

              {conversations.length === 0 ? (
                <SetupEmpty
                  error={error}
                  onRefresh={() => void load('refresh')}
                  refreshing={refreshing}
                />
              ) : (
                <>
                  <ConversationBar
                    conversations={conversations}
                    selectedId={selectedId}
                    onSelect={setSelectedId}
                    onRefresh={() => void load('refresh')}
                    refreshing={refreshing}
                  />

                  {selected ? (
                    <Tabs
                      activeKey={activeTab}
                      onChange={setActiveTab}
                      className="main-tabs"
                      items={[
                        {
                          key: 'memories',
                          label: (
                            <span>
                              <DatabaseOutlined /> 记忆浏览
                            </span>
                          ),
                          children: (
                            <MemoryBrowser
                              key={selected.conversation_id}
                              conversation={selected}
                            />
                          ),
                        },
                        {
                          key: 'query',
                          label: (
                            <span>
                              <MessageOutlined /> 问答与解析
                            </span>
                          ),
                          children: (
                            <QueryWorkbench
                              key={selected.conversation_id}
                              conversation={selected}
                            />
                          ),
                        },
                      ]}
                    />
                  ) : null}
                </>
              )}
            </>
          )}

        </main>
      </div>
    </MemoryDrawerProvider>
  );
}

function SetupEmpty({
  error,
  onRefresh,
  refreshing,
}: {
  error: string | null;
  onRefresh: () => void;
  refreshing: boolean;
}) {
  return (
    <Card className="academic-card setup-card" bordered={false}>
      <Empty
        image={Empty.PRESENTED_IMAGE_SIMPLE}
        description={
          error ? '后端已连接，但还没有可用数据' : '后端还没有可用的对话数据'
        }
      />
      <Typography.Paragraph className="setup-text">
        在 <Typography.Text code>backend/</Typography.Text> 目录完成一次导入与构建：
      </Typography.Paragraph>
      <pre className="json-block setup-code">{`python scripts/import_data.py --file data/demo_locomo.json --dev conv-26,conv-30
python scripts/build_memories.py --conversation conv-26
python scripts/build_memories.py --conversation conv-30`}</pre>
      <div className="setup-actions">
        <Button
          type="primary"
          icon={<ReloadOutlined />}
          loading={refreshing}
          onClick={onRefresh}
        >
          重新检查
        </Button>
        <span className="muted">
          构建完成后刷新即可看到结构化记忆与问答结果。
        </span>
      </div>
    </Card>
  );
}
