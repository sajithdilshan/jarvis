"""Embedder interface + in-process local implementation.

Kept behind a Protocol so the embedding model is swappable (local <-> Bedrock/OpenAI)
without touching MemoryService.
"""

from __future__ import annotations

import threading
from typing import Protocol


class Embedder(Protocol):
    dim: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class LocalEmbedder:
    """In-process sentence-transformers embedder.

    The model (~270MB) is loaded lazily on first ``embed`` call so that merely
    constructing the DI container / importing this module is cheap.
    """

    def __init__(self, model_name: str = "BAAI/bge-base-en-v1.5", dim: int = 768):
        self._model_name = model_name
        self.dim = dim
        self._model = None
        # embed() runs in worker threads (asyncio.to_thread); without this lock two
        # concurrent first-calls trigger parallel HF downloads into the same cache and
        # corrupt it (duplicated/half-written blobs). Load the model exactly once.
        self._lock = threading.Lock()

    def _ensure_model(self):
        if self._model is None:
            with self._lock:
                if self._model is None:  # double-checked: another thread may have loaded it
                    from sentence_transformers import SentenceTransformer

                    # BGE is a standard BERT — no trust_remote_code / custom modeling code.
                    model = SentenceTransformer(self._model_name)
                    get_dim = getattr(
                        model,
                        "get_embedding_dimension",
                        model.get_sentence_embedding_dimension,
                    )
                    self.dim = get_dim()
                    self._model = model  # publish only after fully initialized
        return self._model

    def embed(self, texts: list[str]) -> list[list[float]]:
        model = self._ensure_model()
        # Caller is responsible for any task prefix (BGE prefixes queries only) —
        # MemoryService adds it.
        return model.encode(texts, normalize_embeddings=True).tolist()
