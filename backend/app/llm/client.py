# -*- coding: utf-8 -*-
"""LLM 客户端封装（OpenAI 兼容 API + 内置 mock provider）。

职责：
- provider=openai：任何 OpenAI 兼容服务（base_url / api_key / model 外置 .env，
  兼容 GLM / DeepSeek / Qwen / ollama）；有限超时 + 有限重试（NFR-03），
  超时与不可用分别映射为 timeout / model_unavailable（SRS 7.1）；
- provider=mock：确定性规则实现，无 API Key 亦可全链路演示（NFR-01），
  gold 标注不参与任何生成过程（SRS 3.1）。

接口约定：chat_json(kind, system, user, context)
- openai 端只使用 system / user 文本；
- mock 端依据 kind 与 context 结构化输入做规则计算，
  保证同一 pipeline 在两种 provider 下都可运行。
"""
from __future__ import annotations

import abc
import json
import re
from typing import Any, Literal

from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI

from ..config import Settings, get_settings
from ..errors import LLMTimeoutError, ModelUnavailableError

ChatKind = Literal["extract_memories", "judge_relations", "generate_answer"]


def extract_json_block(text: str) -> Any:
    """从模型输出中提取 JSON（容忍 ```json 代码块与前后杂文）。"""
    cleaned = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", cleaned, re.S)
    if fenced:
        cleaned = fenced.group(1).strip()
    # 去掉前后非 JSON 字符
    for opener, closer in (("[", "]"), ("{", "}")):
        start = cleaned.find(opener)
        end = cleaned.rfind(closer)
        if start != -1 and end > start:
            cleaned = cleaned[start : end + 1]
            break
    return json.loads(cleaned)


class LLMClient(abc.ABC):
    provider: str = "abstract"

    @abc.abstractmethod
    def chat_json(
        self,
        *,
        kind: ChatKind,
        system: str,
        user: str,
        context: dict[str, Any],
    ) -> Any:
        """调用模型并返回解析后的 JSON；失败抛 AppError 子类。"""


class OpenAICompatClient(LLMClient):
    """OpenAI 兼容客户端（有限超时 + 有限重试，NFR-03）。"""

    provider = "openai"

    def __init__(self, settings: Settings):
        if not settings.llm_api_key.get_secret_value():
            raise ModelUnavailableError(
                "LLM_PROVIDER=openai 但未配置 LLM_API_KEY，"
                "请在 backend/.env 中配置（NFR-01）或改用 LLM_PROVIDER=mock"
            )
        if not settings.llm_model:
            raise ModelUnavailableError("LLM_PROVIDER=openai 但未配置 LLM_MODEL")
        self.settings = settings
        self.model = settings.llm_model
        # 重试由本类控制（max_retries=0），避免 SDK 无声的内部重试
        self._client = OpenAI(
            base_url=settings.llm_base_url or None,
            api_key=settings.llm_api_key.get_secret_value(),
            timeout=settings.llm_timeout_seconds,
            max_retries=0,
        )

    def chat_json(self, *, kind: ChatKind, system: str, user: str, context: dict[str, Any]) -> Any:
        attempts = 1 + max(0, self.settings.llm_max_retries)
        last_error: Exception | None = None
        for attempt in range(attempts):
            try:
                resp = self._client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    temperature=0,  # NFR-04 可复现性
                )
                content = resp.choices[0].message.content or ""
                return extract_json_block(content)
            except APITimeoutError as e:
                raise LLMTimeoutError(
                    f"模型调用超时（{self.settings.llm_timeout_seconds:.0f}s，"
                    f"第 {attempt + 1} 次）") from e
            except APIConnectionError as e:
                # 连接失败可重试；最终失败映射为模型不可用
                last_error = e
                continue
            except APIStatusError as e:
                # 4xx/5xx：429 等瞬时可重试，其余视为不可用
                if e.status_code in (408, 409, 429) or e.status_code >= 500:
                    last_error = e
                    continue
                raise ModelUnavailableError(
                    f"模型服务返回错误：HTTP {e.status_code}") from e
            except (json.JSONDecodeError, ValueError) as e:
                # 输出不是合法 JSON → 重试一次
                last_error = e
                continue
        raise ModelUnavailableError(
            f"模型调用在 {attempts} 次尝试后仍失败：{last_error}")


class MockLLMClient(LLMClient):
    """确定性 mock：规则实现三类调用，服务冒烟测试与无 Key 演示。

    不读取 gold（qa.answer / evidence / observation / event_summary）。
    """

    provider = "mock"

    def __init__(self, settings: Settings):
        self.settings = settings

    # -- 延迟导入以避免循环依赖（rules 为纯规则模块） --
    def chat_json(self, *, kind: ChatKind, system: str, user: str, context: dict[str, Any]) -> Any:
        if kind == "extract_memories":
            return self._extract_memories(context)
        if kind == "judge_relations":
            from ..reasoning import rules

            return rules.judge_relations_rules(
                question=context["question"],
                candidates=context["candidates"],
            )
        if kind == "generate_answer":
            return self._generate_answer(context)
        raise ModelUnavailableError(f"mock 不支持的能力：{kind}")

    # ------------------------------------------------------------------
    # 记忆抽取（启发式）：第一人称陈述句 → 带来源记忆，
    # 并按关键词给出轻度结构化属性（occupation / progress），
    # 使关系判定在 mock 模式下也可演示 UPDATE / SUPERSEDE / CONFLICT。
    # ------------------------------------------------------------------
    _FIRST_PERSON = re.compile(
        r"(?:^|[\"'(\s])(I|I'm|I am|I've|I have|I'll|I will|I would|I plan"
        r"|I want|I got|I was|I worked|I started|I passed|I applied)\b",
        re.IGNORECASE,
    )
    # 职业状态 → attribute=occupation（SUPERSEDE 演示：失业 → 开网店）
    _OCCUPATION = [
        (re.compile(r"I (?:lost (?:my|the) job|got laid off|was laid off|got fired)", re.I),
         "unemployed"),
        (re.compile(r"I(?:'m| am) (?:currently )?unemployed", re.I), "unemployed"),
        (re.compile(r"I (?:work|worked) (?:at|for) (?P<v>.{3,60}?)(?:[.,!;]|$)", re.I), None),
        (re.compile(r"I (?:started|opened|launched|set up) (?:a |an |my |my own )?(?P<v>.{3,60}?)(?:[.,!;]|$)", re.I), None),
    ]
    # 过程推进 → attribute=progress（UPDATE 演示：researching → applied → passed）
    _PROGRESS = [
        (re.compile(r"I(?:'m| am) (?:still )?(?:researching|looking into) (?P<v>.{3,60}?)(?:[.,!;]|$)", re.I), "researching"),
        (re.compile(r"I (?:applied to|applied for) (?P<v>.{3,60}?)(?:[.,!;]|$)", re.I), "applied"),
        (re.compile(r"I passed (?P<v>.{3,60}?)(?:[.,!;]|$)", re.I), "passed"),
    ]

    def _extract_memories(self, context: dict[str, Any]) -> list[dict[str, Any]]:
        session = context["session"]
        out: list[dict[str, Any]] = []
        for turn in session["turns"]:
            text = (turn.get("text") or "").strip()
            if not text or len(text) < 5:
                continue
            if not self._FIRST_PERSON.search(text):
                continue
            speaker = turn["speaker"]
            attribute, value = self._structure(text)
            out.append(
                {
                    "content": f"{speaker} said: {text}",
                    "entity": speaker,
                    "attribute": attribute,
                    "value": value,
                    "time_expression": None,
                    "event_time": None,
                    "source_turn_ids": [turn["turn_id"]],
                    "record_status": "ready",
                }
            )
        return out

    def _structure(self, text: str) -> tuple[str | None, str | None]:
        """关键词级结构化：返回 (attribute, value)。"""
        for pat, fixed in self._OCCUPATION:
            m = pat.search(text)
            if m:
                v = fixed if fixed else m.group("v").strip()
                return "occupation", v
        for pat, fixed in self._PROGRESS:
            m = pat.search(text)
            if m:
                # 阶段 + 对象（如 "passed the adoption agency interviews"）
                v = f"{fixed} {m.group('v').strip()}".strip()
                return "progress", v
        return "statement", text

    # ------------------------------------------------------------------
    # 回答生成（抽取式）：直接以有效记忆内容拼装，杜绝外部知识（BR-12）
    # ------------------------------------------------------------------
    def _generate_answer(self, context: dict[str, Any]) -> dict[str, Any]:
        memories = context.get("memories") or []
        if not memories:
            return {"answer": "", "cited_memory_ids": []}
        # 按候选排序（调用方保证顺序即相关性排序），取前两条拼装
        top = memories[:2]
        parts = [m["content"] for m in top]
        return {
            "answer": " ".join(parts),
            "cited_memory_ids": [m["memory_id"] for m in top],
        }


def get_llm_client(settings: Settings | None = None) -> LLMClient:
    """按配置返回 LLM 客户端。"""
    s = settings or get_settings()
    if s.llm_provider == "mock":
        return MockLLMClient(s)
    return OpenAICompatClient(s)
