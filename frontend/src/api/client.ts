import type {
  ApiErrorBody,
  ConversationInfo,
  Health,
  MemoryEvidenceResponse,
  MemoryListParams,
  MemoryListResponse,
  QueryRequest,
  QueryResult,
} from './types';

const API_BASE = import.meta.env.VITE_API_BASE ?? '/api';

export class ApiError extends Error {
  readonly code: string;
  readonly status: number;
  readonly requestId: string | null;

  constructor(message: string, code: string, status: number, requestId: string | null) {
    super(message);
    this.name = 'ApiError';
    this.code = code;
    this.status = status;
    this.requestId = requestId;
  }
}

async function toApiError(response: Response): Promise<ApiError> {
  let body: ApiErrorBody | null = null;
  try {
    body = (await response.json()) as ApiErrorBody;
  } catch {
    // 非 JSON 错误体（例如代理层 502）保留状态码信息。
  }
  const payload = body?.error;
  return new ApiError(
    payload?.message ?? `请求失败（HTTP ${response.status}）`,
    payload?.code ?? 'http_error',
    response.status,
    payload?.request_id ?? response.headers.get('X-Request-ID'),
  );
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  if (init?.body && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }
  const response = await fetch(`${API_BASE}${path}`, { ...init, headers });
  if (!response.ok) {
    throw await toApiError(response);
  }
  return (await response.json()) as T;
}

function toQueryString(params: Record<string, string | number | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== '') {
      search.set(key, String(value));
    }
  }
  const qs = search.toString();
  return qs ? `?${qs}` : '';
}

export const api = {
  health(): Promise<Health> {
    return request<Health>('/health');
  },

  listConversations(): Promise<ConversationInfo[]> {
    return request<ConversationInfo[]>('/conversations');
  },

  listMemories(params: MemoryListParams): Promise<MemoryListResponse> {
    return request<MemoryListResponse>(
      `/memories${toQueryString({
        conversation_id: params.conversation_id,
        entity: params.entity,
        keyword: params.keyword,
        record_status: params.record_status,
        page: params.page,
        page_size: params.page_size,
      })}`,
    );
  },

  getMemoryEvidence(memoryId: string): Promise<MemoryEvidenceResponse> {
    return request<MemoryEvidenceResponse>(
      `/memories/${encodeURIComponent(memoryId)}/evidence`,
    );
  },

  query(payload: QueryRequest): Promise<QueryResult> {
    return request<QueryResult>('/query', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  async exportMemories(conversationId?: string): Promise<{ blob: Blob; filename: string }> {
    const response = await fetch(`${API_BASE}/export`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ conversation_id: conversationId ?? null }),
    });
    if (!response.ok) {
      throw await toApiError(response);
    }
    const disposition = response.headers.get('Content-Disposition') ?? '';
    const match = /filename="?([^";]+)"?/.exec(disposition);
    return {
      blob: await response.blob(),
      filename: match?.[1] ?? 'memories.json',
    };
  },
};
