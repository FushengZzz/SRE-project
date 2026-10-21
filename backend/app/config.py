# -*- coding: utf-8 -*-
"""应用配置：全部可外部化到 .env（NFR-08 框架与模型可配置）。

约定：
- 相对路径（database_path / export_dir）均相对 backend/ 目录解析；
- LLM 采用 OpenAI 兼容 API，base_url / api_key / model 全部外置，
  兼容 GLM / DeepSeek / Qwen / ollama 等服务（SRS 2.2 外部依赖）；
- llm_provider=mock 时不依赖任何外部服务，可全链路演示与测试（NFR-01）。
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal, Optional

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/ 目录（config.py 位于 backend/app/ 下）
BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """全局配置，从 backend/.env 与环境变量读取。"""

    app_name: str = "Agent Dynamic Memory Management"
    app_host: str = "127.0.0.1"
    app_port: int = 8000

    # 存储（物理存储方式不受 SRS 3.2 限制，M4 采用 SQLite + JSON 导出）
    database_path: str = "data/app.db"
    export_dir: str = "exports"

    # ---- LLM 配置 ----
    llm_provider: Literal["mock", "openai"] = "mock"
    llm_base_url: Optional[str] = None      # 例如 https://api.openai.com/v1
    llm_api_key: SecretStr = SecretStr("")
    llm_model: Optional[str] = None         # 例如 gpt-4o-mini / glm-4-flash
    llm_timeout_seconds: float = 60.0        # NFR-03 有限超时
    llm_max_retries: int = 2                # NFR-03 有限重试

    # 提示词版本（导出与查询结果中记录，NFR-04 可复现性）
    extract_prompt_version: str = "extract-v0.1"
    relation_prompt_version: str = "relation-v0.1"
    answer_prompt_version: str = "answer-v0.1"

    # ---- 检索 / 解析配置 ----
    retrieval_default_top_k: int = 5
    relation_mode: Literal["rules", "llm"] = "rules"
    irrelevant_score_threshold: float = 0.05

    # ---- 数据划分 ----
    dataset_version: str = "locomo10-raw"
    # 课程尚未确认 6 段对话名单（SRS 3.1），此处仅为可配置占位
    dev_conversations: str = ""             # 逗号分隔 conversation_id
    test_conversations: str = ""            # 逗号分隔 conversation_id

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def db_file(self) -> Path:
        p = Path(self.database_path)
        if not p.is_absolute():
            p = BASE_DIR / p
        return p

    @property
    def export_path(self) -> Path:
        p = Path(self.export_dir)
        if not p.is_absolute():
            p = BASE_DIR / p
        return p

    def split_of(self, conversation_id: str) -> str:
        """按配置返回对话划分；未配置的对话标记为 extra（扩展评测）。"""
        dev = {x.strip() for x in self.dev_conversations.split(",") if x.strip()}
        test = {x.strip() for x in self.test_conversations.split(",") if x.strip()}
        if conversation_id in dev:
            return "dev"
        if conversation_id in test:
            return "test"
        return "extra"


_settings: Optional[Settings] = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reset_settings() -> None:
    """测试辅助：强制下次重新读取配置。"""
    global _settings
    _settings = None
