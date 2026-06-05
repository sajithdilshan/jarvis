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


@lru_cache(maxsize=None)
def build_model(spec: str):
    """Resolve a model spec string into something ``Agent(model=...)`` accepts."""
    if spec.startswith("bedrock:"):
        from pydantic_ai.models.bedrock import BedrockConverseModel
        from pydantic_ai.providers.bedrock import BedrockProvider

        model_id = spec.removeprefix("bedrock:")
        region = os.environ.get("AWS_REGION", _DEFAULT_BEDROCK_REGION)
        logger.info("Building Bedrock model model_id=%s region=%s", model_id, region)
        provider = BedrockProvider(region_name=region)
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
