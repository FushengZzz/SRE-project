import type {
  AnswerStatus,
  RecordStatus,
  RelationType,
  ValidityStatus,
} from './api/types';

export interface PresetQuestion {
  label: string;
  question: string;
  asOf?: string;
  topK?: number;
}

export const RELATION_META: Record<
  RelationType,
  { label: string; color: string; hint: string }
> = {
  RETAIN: {
    label: '保留',
    color: 'green',
    hint: '比较范围内事实兼容，相关记忆继续保留',
  },
  UPDATE: {
    label: '更新',
    color: 'blue',
    hint: '同一过程的阶段推进，新阶段成为当前状态',
  },
  SUPERSEDE: {
    label: '替代',
    color: 'orange',
    hint: '新事实替代同一查询语义下的旧状态',
  },
  CONFLICT: {
    label: '冲突',
    color: 'red',
    hint: '同一时间条件下事实不兼容，暂无法消解',
  },
};

export const VALIDITY_META: Record<
  ValidityStatus,
  { label: string; color: string; className: string }
> = {
  effective: { label: '有效', color: 'green', className: 'validity-effective' },
  historical: { label: '历史', color: 'blue', className: 'validity-historical' },
  conflict: { label: '冲突', color: 'red', className: 'validity-conflict' },
  uncertain: { label: '不确定', color: 'gold', className: 'validity-uncertain' },
  irrelevant: { label: '无关', color: 'default', className: 'validity-irrelevant' },
};

export const ANSWER_META: Record<
  AnswerStatus,
  { label: string; color: string; className: string; description: string }
> = {
  answered: {
    label: '已生成答案',
    color: 'green',
    className: 'answer-answered',
    description: '基于当前有效记忆生成',
  },
  insufficient_evidence: {
    label: '证据不足',
    color: 'gold',
    className: 'answer-insufficient',
    description: '候选记忆不足以支持确定回答',
  },
  unresolved_conflict: {
    label: '存在未决冲突',
    color: 'red',
    className: 'answer-conflict',
    description: '冲突双方证据均保留，未强行给出结论',
  },
};

export const RECORD_STATUS_META: Record<RecordStatus, { label: string; color: string }> = {
  ready: { label: '就绪', color: 'green' },
  needs_review: { label: '待复核', color: 'gold' },
};

export const SPLIT_META: Record<string, { label: string; color: string }> = {
  dev: { label: '开发集', color: 'blue' },
  test: { label: '测试集', color: 'purple' },
  extra: { label: '扩展集', color: 'default' },
};

const CONVERSATION_PRESETS: Record<string, PresetQuestion[]> = {
  'conv-26': [
    {
      label: 'Caroline 的领养进度',
      question: "What is Caroline's adoption status?",
    },
    {
      label: '领养申请过程',
      question: 'What did Caroline do about adoption?',
    },
    {
      label: '职业变化 · 含替代',
      question: 'Caroline counseling mental health career adoption occupation',
      topK: 20,
    },
    {
      label: '历史视角 · 2023-08',
      question: "What is Caroline's adoption status?",
      asOf: '2023-08-01',
      topK: 10,
    },
  ],
  'conv-30': [
    {
      label: 'Gina 的工作变化（含替代）',
      question: 'Did Gina lose her job and open an online clothing store?',
      asOf: '2023-05-01',
      topK: 20,
    },
    {
      label: 'Gina 是否开了店',
      question: 'Did Gina open a store?',
    },
    {
      label: 'Gina 当前工作',
      question: "What is Gina's current job?",
    },
  ],
  'synthetic-conflict-01': [
    {
      label: '同一会话中的矛盾',
      question: 'Alex DoorDash job',
      topK: 10,
    },
  ],
};

const DEFAULT_PRESETS: PresetQuestion[] = [
  {
    label: '当前状态',
    question: 'What is the current status?',
  },
  {
    label: '发生了什么',
    question: 'What happened in this conversation?',
  },
];

export function getPresets(conversationId: string): PresetQuestion[] {
  return CONVERSATION_PRESETS[conversationId] ?? DEFAULT_PRESETS;
}
