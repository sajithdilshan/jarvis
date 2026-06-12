"""Provider-agnostic model resolution.

A model spec is a string:
  - "openai:gpt-5.5" / "anthropic:..."  -> passed through to PydanticAI's native resolver
  - "bedrock:<arn-or-model-id>"          -> BedrockConverseModel (boto3 standard auth)
  - "ollama:<model-name>"               -> OpenAI-compatible via Ollama (local)
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache

logger = logging.getLogger(__name__)

_DEFAULT_BEDROCK_REGION = "eu-central-1"
_DEFAULT_OLLAMA_BASE_URL = "http://host.docker.internal:11434/v1"


@lru_cache(maxsize=1)
def _bedrock_client():
    """One shared bedrock-runtime client for all models.

    Each BedrockProvider would otherwise build its own boto3 Session, hence its own
    botocore SSO token provider. Under concurrent sub-agents that all refresh at once,
    AWS SSO's rotating (single-use) refresh token means the first refresh invalidates the
    rest -> "Invalid refresh token provided". A single shared client = one token provider,
    whose refresh is lock-guarded, so only one refresh happens and the others reuse it.
    """
    import boto3

    region = os.environ.get("AWS_REGION", _DEFAULT_BEDROCK_REGION)
    logger.info("Building shared Bedrock client region=%s", region)
    return boto3.Session().client("bedrock-runtime", region_name=region)


@lru_cache(maxsize=None)
def build_model(spec: str):
    """Resolve a model spec string into something ``Agent(model=...)`` accepts."""
    if spec.startswith("bedrock:"):
        from pydantic_ai.models.bedrock import BedrockConverseModel
        from pydantic_ai.providers.bedrock import BedrockProvider

        model_id = spec.removeprefix("bedrock:")
        logger.info("Building Bedrock model model_id=%s", model_id)
        provider = BedrockProvider(bedrock_client=_bedrock_client())
        return BedrockConverseModel(model_id, provider=provider)

    if spec.startswith("ollama:"):
        from pydantic_ai.models.openai import OpenAIModel
        from pydantic_ai.providers.openai import OpenAIProvider

        model_name = spec.removeprefix("ollama:")
        base_url = os.environ.get("OLLAMA_BASE_URL", _DEFAULT_OLLAMA_BASE_URL)
        logger.info("Building Ollama model model=%s base_url=%s", model_name, base_url)
        provider = OpenAIProvider(base_url=base_url, api_key="ollama")
        return OpenAIModel(model_name, provider=provider)

    logger.info("Using native model spec=%s", spec)
    return spec  # PydanticAI resolves "openai:..."/"anthropic:..." natively
