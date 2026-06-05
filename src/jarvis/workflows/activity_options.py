"""Shared Temporal activity names, retries, and timeout presets."""

from __future__ import annotations

from datetime import timedelta

from temporalio.common import RetryPolicy

LIST_REGISTERED_AGENTS = "list_registered_agents"
GET_POLL_WATERMARK = "get_poll_watermark"
SET_POLL_WATERMARK = "set_poll_watermark"
RUN_SUB_AGENT = "run_sub_agent"
REPORT_SOURCE_FAILURES = "report_source_failures"
EXECUTE_PERMISSIONS = "execute_permissions"
RUN_MAIN_AGENT_SYNTHESIZE = "run_main_agent_synthesize"
PUBLISH_BRIEFING = "publish_briefing"
RUN_INTERACTIVE_CHAT = "run_interactive_chat"

DEFAULT_RETRY = RetryPolicy(maximum_attempts=3)
SUB_AGENT_RETRY = RetryPolicy(maximum_attempts=2)


def short_activity() -> dict:
    return {
        "start_to_close_timeout": timedelta(seconds=5),
        "retry_policy": DEFAULT_RETRY,
    }


def quick_activity(seconds: int = 10) -> dict:
    return {
        "start_to_close_timeout": timedelta(seconds=seconds),
        "retry_policy": DEFAULT_RETRY,
    }


def publish_activity() -> dict:
    return {
        "start_to_close_timeout": timedelta(seconds=30),
        "retry_policy": DEFAULT_RETRY,
    }


def sub_agent_activity() -> dict:
    return {
        "start_to_close_timeout": timedelta(minutes=5),
        "retry_policy": SUB_AGENT_RETRY,
    }


def agent_activity(minutes: int = 3) -> dict:
    return {
        "start_to_close_timeout": timedelta(minutes=minutes),
        "retry_policy": DEFAULT_RETRY,
    }
