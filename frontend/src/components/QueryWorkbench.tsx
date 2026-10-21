import {
  Alert,
  App as AntdApp,
  Button,
  Card,
  Collapse,
  DatePicker,
  Descriptions,
  Input,
  InputNumber,
  Skeleton,
  Space,
  Tag,
  Tooltip,
  Typography,
} from 'antd';
import {
  ArrowRightOutlined,
  BranchesOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  ExperimentOutlined,
  HistoryOutlined,
  SearchOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
import dayjs from 'dayjs';
import { useMemo, useState } from 'react';
import { api, ApiError } from '../api/client';
import type {
  ConversationInfo,
  QueryResult,
} from '../api/types';
import {
  ANSWER_META,
  getPresets,
  type PresetQuestion,
} from '../constants';
import { countByValidity, formatTime, shortMemoryId } from '../utils';
import { CandidateTable } from './CandidateTable';
import { useMemoryDrawer } from './MemoryDrawerContext';
import { RelationTimeline } from './RelationTimeline';

interface Props {
  conversation: ConversationInfo;
}

interface QueryError {
  message: string;
  code?: string;
  requestId?: string | null;
}

export function QueryWorkbench({ conversation }: Props) {
  const { message } = AntdApp.useApp();
  const [question, setQuestion] = useState('');
  const [asOf, setAsOf] = useState<string | null>(null);
  const [topK, setTopK] = useState(5);
  const [activePreset, setActivePreset] = useState<string | null>(null);
  const [result, setResult] = useState<QueryResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<QueryError | null>(null);

  const presets = getPresets(conversation.conversation_id);

  const applyPreset = (preset: PresetQuestion) => {
    setQuestion(preset.question);
    setAsOf(preset.asOf ?? null);
    setTopK(preset.topK ?? 5);
    setActivePreset(preset.label);
    setResult(null);
    setError(null);
  };

  const submit = async () => {
    const trimmed = question.trim();
    if (!trimmed) {
      message.warning('请先输入问题');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const response = await api.query({
        conversation_id: conversation.conversation_id,
        question: trimmed,
        as_of: asOf ?? undefined,
        top_k: topK,
      });
      setResult(response);
    } catch (err: unknown) {
      setResult(null);
      if (err instanceof ApiError) {
        setError({
          message: err.message,
          code: err.code,
          requestId: err.requestId,
        });
      } else {
        setError({ message: '请求失败，请确认后端服务已启动' });
      }
    } finally {
      setLoading(false);
    }
  };

  const memoryCount = conversation.memory_count;

  return (
    <div className="query-layout">
      <Card className="academic-card query-card" bordered={false}>
        <div className="card-heading">
          <div>
            <div className="section-kicker">Query & Resolution</div>
            <div className="card-title">问答与状态解析</div>
            <div className="card-subtitle">
              从完整记忆中检索候选，判定状态关系，解析当前有效证据后生成回答。
            </div>
          </div>
          <Tag className="conversation-pill" bordered={false}>
            {conversation.conversation_id} · {memoryCount} 条记忆
          </Tag>
        </div>

        {memoryCount === 0 ? (
          <Alert
            type="warning"
            showIcon
            className="inline-alert"
            message="该对话还没有构建记忆"
            description="请先在 backend 目录运行 build_memories.py，再回到这里提问。"
          />
        ) : null}

        <div className="preset-row">
          <span className="preset-label">
            <ThunderboltOutlined /> 示例问题
          </span>
          <Space size={8} wrap>
            {presets.map((preset) => (
              <Tooltip key={preset.label} title={preset.question}>
                <Button
                  size="small"
                  className={
                    activePreset === preset.label
                      ? 'preset-button preset-button-active'
                      : 'preset-button'
                  }
                  icon={
                    preset.asOf ? <HistoryOutlined /> : <SearchOutlined />
                  }
                  onClick={() => applyPreset(preset)}
                >
                  {preset.label}
                </Button>
              </Tooltip>
            ))}
          </Space>
        </div>

        <Input.TextArea
          value={question}
          onChange={(event) => {
            setQuestion(event.target.value);
            setActivePreset(null);
          }}
          onKeyDown={(event) => {
            if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
              event.preventDefault();
              void submit();
            }
          }}
          autoSize={{ minRows: 2, maxRows: 4 }}
          maxLength={500}
          placeholder={`输入一个关于这段对话的问题，例如：${
            presets[0]?.question ?? 'What happened in this conversation?'
          }`}
          className="question-input"
        />

        <div className="query-toolbar">
          <Collapse
            ghost
            className="advanced-collapse"
            items={[
              {
                key: 'advanced',
                label: (
                  <span className="advanced-label">
                    <ExperimentOutlined /> 高级选项
                    {asOf ? <Tag color="blue">截止 {asOf}</Tag> : null}
                    {topK !== 5 ? <Tag color="blue">Top-{topK}</Tag> : null}
                  </span>
                ),
                children: (
                  <div className="advanced-grid">
                    <div className="advanced-field">
                      <label htmlFor="as-of">时间截止 as_of</label>
                      <DatePicker
                        id="as-of"
                        value={asOf ? dayjs(asOf) : null}
                        onChange={(value) =>
                          setAsOf(value ? value.format('YYYY-MM-DD') : null)
                        }
                        allowClear
                        placeholder="留空 = 对话历史末端"
                        className="advanced-control"
                      />
                      <span className="muted">
                        早于该日期的会话才会进入检索与回答（BR-09）。
                      </span>
                    </div>
                    <div className="advanced-field">
                      <label htmlFor="top-k">召回数量 top_k</label>
                      <InputNumber
                        id="top-k"
                        min={1}
                        max={100}
                        value={topK}
                        onChange={(value) => setTopK(Number(value ?? 5))}
                        className="advanced-control"
                      />
                      <span className="muted">
                        返回相关度最高的 K 条候选记忆，默认 5。
                      </span>
                    </div>
                  </div>
                ),
              },
            ]}
          />

          <div className="submit-area">
            <span className="muted keyboard-hint">Ctrl / ⌘ + Enter 提交</span>
            <Button
              type="primary"
              size="large"
              icon={<ExperimentOutlined />}
              loading={loading}
              onClick={() => void submit()}
              disabled={!question.trim()}
            >
              解析并回答
            </Button>
          </div>
        </div>
      </Card>

      {loading ? (
        <Card className="academic-card result-skeleton-card" bordered={false}>
          <Skeleton active title paragraph={{ rows: 3 }} />
          <Skeleton active title={false} paragraph={{ rows: 8 }} />
        </Card>
      ) : error ? (
        <Alert
          type="error"
          showIcon
          className="query-error"
          message="查询失败"
          description={
            <div>
              <div>{error.message}</div>
              <div className="muted">
                {error.code ? `code: ${error.code}` : null}
                {error.requestId ? ` · request_id: ${error.requestId}` : null}
              </div>
            </div>
          }
          action={
            <Button size="small" onClick={() => void submit()}>
              重试
            </Button>
          }
        />
      ) : result ? (
        <QueryResultView result={result} />
      ) : (
        <EmptyPipeline />
      )}
    </div>
  );
}

function EmptyPipeline() {
  const steps = [
    {
      icon: <SearchOutlined />,
      title: '检索候选',
      text: '从完整记忆集合召回 Top-K',
    },
    {
      icon: <BranchesOutlined />,
      title: '判定关系',
      text: 'RETAIN / UPDATE / SUPERSEDE / CONFLICT',
    },
    {
      icon: <CheckCircleOutlined />,
      title: '解析有效性',
      text: 'effective / historical / conflict / uncertain',
    },
    {
      icon: <ExperimentOutlined />,
      title: '生成回答',
      text: '只引用当前有效证据与来源',
    },
  ];

  return (
    <Card className="academic-card pipeline-card" bordered={false}>
      <div className="section-kicker">Pipeline</div>
      <div className="card-title">从问题到有效记忆</div>
      <div className="card-subtitle">
        系统不会把 gold 答案或证据作为输入；回答只基于原始对话抽取的 Memory。
      </div>
      <div className="pipeline-steps">
        {steps.map((step, index) => (
          <div className="pipeline-step-wrap" key={step.title}>
            <div className="pipeline-step">
              <div className="pipeline-step-icon">{step.icon}</div>
              <div className="pipeline-step-index">0{index + 1}</div>
              <div className="pipeline-step-title">{step.title}</div>
              <div className="pipeline-step-text">{step.text}</div>
            </div>
            {index < steps.length - 1 ? (
              <ArrowRightOutlined className="pipeline-arrow" />
            ) : null}
          </div>
        ))}
      </div>
    </Card>
  );
}

function QueryResultView({ result }: { result: QueryResult }) {
  const { openMemory } = useMemoryDrawer();
  const memoryMap = useMemo(
    () =>
      new Map(
        result.candidates.map((candidate) => [
          candidate.memory.memory_id,
          candidate.memory,
        ]),
      ),
    [result.candidates],
  );
  const answerMeta = ANSWER_META[result.answer.status];
  const counts = countByValidity(result.validity);
  const historicalCount = counts.historical ?? 0;
  const uncertainCount = counts.uncertain ?? 0;

  return (
    <div className="result-stack">
      <Card
        className={`academic-card answer-card ${answerMeta.className}`}
        bordered={false}
      >
        <div className="answer-top">
          <div>
            <div className="section-kicker">Answer</div>
            <div className="card-title">最终回答</div>
          </div>
          <Tooltip title={answerMeta.description}>
            <Tag color={answerMeta.color} className="answer-status-tag">
              {answerMeta.label}
            </Tag>
          </Tooltip>
        </div>

        <div className="answer-question">{result.question}</div>

        {result.answer.text ? (
          <div className="answer-text">{result.answer.text}</div>
        ) : (
          <Alert
            type={
              result.answer.status === 'unresolved_conflict' ? 'error' : 'warning'
            }
            showIcon
            message={answerMeta.description}
            description="系统没有生成确定答案，避免把证据不足或未决冲突表述为事实。"
            className="inline-alert"
          />
        )}

        {result.answer.conflict_explanation ? (
          <Alert
            type="warning"
            showIcon
            message="冲突说明"
            description={result.answer.conflict_explanation}
            className="inline-alert"
          />
        ) : null}

        {result.run_config.llm_provider === 'mock' ? (
          <div className="mock-note">
            当前为 mock 演示模式：回答由规则从有效记忆中摘录，未调用外部 LLM。
          </div>
        ) : null}

        <div className="citation-row">
          <span className="muted">引用证据</span>
          {result.answer.cited_memory_ids.length ? (
            result.answer.cited_memory_ids.map((id) => {
              const memory = memoryMap.get(id);
              return (
                <Button
                  key={id}
                  type="link"
                  size="small"
                  className="citation-link"
                  onClick={() => openMemory(id)}
                >
                  {memory ? truncate(memory.content, 38) : shortMemoryId(id)}
                </Button>
              );
            })
          ) : (
            <span className="muted">—</span>
          )}
        </div>

        <div className="answer-meta">
          <span>
            <ClockCircleOutlined /> 实际截止 {formatTime(result.effective_cutoff)}
          </span>
          <span>as_of {result.as_of ?? '默认（历史末端）'}</span>
          <span>top_k {result.top_k}</span>
          <span>query {result.query_id}</span>
        </div>
      </Card>

      <div className="stat-grid">
        <StatCard label="候选记忆" value={result.candidates.length} tone="blue" />
        <StatCard
          label="有效记忆"
          value={result.effective_memory_ids.length}
          tone="green"
        />
        <StatCard label="历史记忆" value={historicalCount} tone="slate" />
        <StatCard
          label="冲突 / 不确定"
          value={`${result.conflict_memory_ids.length} / ${uncertainCount}`}
          tone="red"
        />
      </div>

      {result.conflict_memory_ids.length ? (
        <Alert
          type="warning"
          showIcon
          className="inline-alert conflict-alert"
          message="存在未决冲突"
          description={
            <div>
              冲突记忆：
              {result.conflict_memory_ids.map((id) => (
                <Button
                  key={id}
                  type="link"
                  size="small"
                  onClick={() => openMemory(id)}
                >
                  {shortMemoryId(id)}
                </Button>
              ))}
              <div className="muted">
                系统保留双方证据，不会强行选择一方作为确定结论。
              </div>
            </div>
          }
        />
      ) : null}

      <Card className="academic-card" bordered={false}>
        <div className="card-heading compact">
          <div>
            <div className="section-kicker">Relations</div>
            <div className="card-title">关系判定与解析</div>
            <div className="card-subtitle">
              方向统一为旧 → 新；冲突关系对称展示，理由与证据一并保留。
            </div>
          </div>
          <Tag>{result.relations.length} 条关系</Tag>
        </div>
        <RelationTimeline relations={result.relations} memories={memoryMap} />
      </Card>

      <Card className="academic-card" bordered={false}>
        <div className="card-heading compact">
          <div>
            <div className="section-kicker">Candidates</div>
            <div className="card-title">候选记忆与逐条有效性</div>
            <div className="card-subtitle">
              点击任意一行查看完整字段与来源证据；绿色行为当前有效证据。
            </div>
          </div>
          <Tag>{result.candidates.length} 条候选</Tag>
        </div>
        <CandidateTable
          candidates={result.candidates}
          validity={result.validity}
        />
      </Card>

      <Collapse
        ghost
        className="technical-collapse"
        items={[
          {
            key: 'technical',
            label: (
              <span className="advanced-label">
                <ExperimentOutlined /> 技术细节 · 运行配置与原始 JSON
              </span>
            ),
            children: (
              <div>
                <Descriptions
                  size="small"
                  column={1}
                  bordered
                  items={Object.entries(result.run_config).map(([key, value]) => ({
                    key,
                    label: key,
                    children: (
                      <Typography.Text code>
                        {typeof value === 'string'
                          ? value
                          : JSON.stringify(value)}
                      </Typography.Text>
                    ),
                  }))}
                />
                <pre className="json-block">
                  {JSON.stringify(result, null, 2)}
                </pre>
              </div>
            ),
          },
        ]}
      />
    </div>
  );
}

function StatCard({
  label,
  value,
  tone,
}: {
  label: string;
  value: number | string;
  tone: 'blue' | 'green' | 'slate' | 'red';
}) {
  return (
    <div className={`stat-card stat-${tone}`}>
      <div className="stat-value">{value}</div>
      <div className="stat-label">{label}</div>
    </div>
  );
}

function truncate(text: string, maxLength: number): string {
  return text.length > maxLength ? `${text.slice(0, maxLength)}…` : text;
}
