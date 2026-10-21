# -*- coding: utf-8 -*-
"""统一错误类型（SRS 7.1：code / message / request_id，区分校验、
数据不存在、模型不可用与超时）。"""
from __future__ import annotations


class AppError(Exception):
    """业务错误基类，携带稳定错误码与 HTTP 状态。"""

    code: str = "internal_error"
    http_status: int = 500

    def __init__(self, message: str, *, code: str | None = None, http_status: int | None = None):
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        if http_status is not None:
            self.http_status = http_status


class InvalidParamError(AppError):
    """参数校验失败（FR-07：无效参数返回可理解的错误）。"""

    code = "validation_error"
    http_status = 400


class NotFoundError(AppError):
    """数据不存在（对话 / 记忆 / 任务 / 轮次）。"""

    code = "not_found"
    http_status = 404


class AlreadyExistsError(AppError):
    """重复资源（FR-01：重复导入不得静默重复记录）。"""

    code = "already_exists"
    http_status = 409


class ModelUnavailableError(AppError):
    """外部模型服务不可用（UC-03 分支：返回失败阶段，不显示伪造答案）。"""

    code = "model_unavailable"
    http_status = 503


class LLMTimeoutError(AppError):
    """外部模型调用超时（NFR-03 有限超时）。"""

    code = "timeout"
    http_status = 504


class NotCapableError(AppError):
    """能力占位（FR-13 批量评测端点 Phase 2 提供）。"""

    code = "not_implemented"
    http_status = 501
