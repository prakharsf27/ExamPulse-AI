from __future__ import annotations

import hashlib
import logging
import math
import re
from typing import List, Optional, Tuple
from uuid import uuid4

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PayloadSchemaType,
    VectorParams,
)

from app.config import settings

logger = logging.getLogger(__name__)


class LocalHashEmbeddings(Embeddings):
    """Zero-dependency deterministic embeddings for offline/no-key local execution."""

    def __init__(self, dimension: int = 384) -> None:
        self.dimension = dimension

    def _embed(self, text: str) -> List[float]:
        vec = [0.0] * self.dimension
        normalized = text.lower()
        tokens = re.findall(r"[a-z0-9_]+", normalized)
        features: List[Tuple[str, float]] = []

        for tok in tokens:
            features.append((f"w:{tok}", 1.5))
            if len(tok) >= 4:
                for i in range(len(tok) - 2):
                    features.append((f"g:{tok[i:i+3]}", 0.45))

        for i in range(len(tokens) - 1):
            features.append((f"b:{tokens[i]}_{tokens[i+1]}", 1.2))

        for feat, weight in features:
            digest = hashlib.blake2b(feat.encode("utf-8"), digest_size=8).digest()
            idx = int.from_bytes(digest[:4], "little") % self.dimension
            sign = 1.0 if (digest[4] & 1) == 0 else -1.0
            vec[idx] += sign * weight

        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0:
            vec = [v / norm for v in vec]
        return vec

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [self._embed(t) for t in texts]

    def embed_query(self, text: str) -> List[float]:
        return self._embed(text)


class QdrantRAGStore:
    """Manages Qdrant Cloud or in-memory :memory: vector operations with metadata filtering."""

    def __init__(self) -> None:
        self._client: Optional[QdrantClient] = None
        self._mode = "memory"
        self._embeddings: Optional[Embeddings] = None
        self._embedding_mode = "local"
        self._vector_size = 384
        self._collection_name = settings.qdrant_collection
        self._initialized_collections: set[str] = set()
        self._init_backend()

    def _init_backend(self) -> None:
        # 1. Initialize Embeddings (Gemini primary, local deterministic fallback)
        if settings.has_gemini:
            try:
                from langchain_google_genai import GoogleGenerativeAIEmbeddings

                gemini_emb = GoogleGenerativeAIEmbeddings(
                    model=settings.gemini_embedding_model,
                    google_api_key=settings.gemini_api_key,
                )
                probe = gemini_emb.embed_query("ExamPulse initialization probe")
                self._embeddings = gemini_emb
                self._embedding_mode = "gemini"
                self._vector_size = len(probe)
                self._collection_name = f"{settings.qdrant_collection}_gemini_{self._vector_size}"
            except Exception as exc:
                logger.warning("Gemini embeddings unavailable (%s); falling back to local embeddings.", exc)

        if self._embeddings is None:
            self._embeddings = LocalHashEmbeddings(dimension=384)
            self._embedding_mode = "local"
            self._vector_size = 384
            self._collection_name = f"{settings.qdrant_collection}_local_384"

        # 2. Initialize Qdrant Client (Cloud if env vars set, else :memory:)
        if settings.has_qdrant_cloud:
            try:
                self._client = QdrantClient(
                    url=settings.qdrant_url,
                    api_key=settings.qdrant_api_key or None,
                    timeout=15.0,
                )
                self._client.get_collections()
                self._mode = "cloud"
            except Exception as exc:
                logger.warning("Qdrant Cloud unavailable (%s); falling back to :memory:.", exc)
                self._client = QdrantClient(":memory:")
                self._mode = "memory"
        else:
            self._client = QdrantClient(":memory:")
            self._mode = "memory"

        self._ensure_collection()

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def embedding_mode(self) -> str:
        return self._embedding_mode

    def _ensure_collection(self) -> None:
        assert self._client is not None
        if self._collection_name in self._initialized_collections:
            return

        existing = [c.name for c in self._client.get_collections().collections]
        if self._collection_name not in existing:
            self._client.create_collection(
                collection_name=self._collection_name,
                vectors_config=VectorParams(size=self._vector_size, distance=Distance.COSINE),
            )

        if self._mode == "cloud":
            for field in ("metadata.session_id", "metadata.source"):
                try:
                    self._client.create_payload_index(
                        collection_name=self._collection_name,
                        field_name=field,
                        field_schema=PayloadSchemaType.KEYWORD,
                    )
                except Exception:
                    pass

        self._initialized_collections.add(self._collection_name)

    def _vector_store(self) -> QdrantVectorStore:
        assert self._client is not None and self._embeddings is not None
        self._ensure_collection()
        return QdrantVectorStore(
            client=self._client,
            collection_name=self._collection_name,
            embedding=self._embeddings,
        )

    def _build_filter(self, session_id: str, source: Optional[str] = None) -> Filter:
        conditions = [
            FieldCondition(key="metadata.session_id", match=MatchValue(value=session_id))
        ]
        if source:
            conditions.append(
                FieldCondition(key="metadata.source", match=MatchValue(value=source))
            )
        return Filter(must=conditions)

    def upsert_documents(self, session_id: str, docs: List[Document]) -> int:
        if not docs:
            return 0
        for doc in docs:
            doc.metadata["session_id"] = session_id

        vs = self._vector_store()
        ids = [str(uuid4()) for _ in docs]
        vs.add_documents(documents=docs, ids=ids)
        return len(docs)

    def search(
        self,
        session_id: str,
        query: str,
        source: Optional[str] = None,
        k: int = 6,
    ) -> List[Tuple[Document, float]]:
        vs = self._vector_store()
        q_filter = self._build_filter(session_id=session_id, source=source)
        return vs.similarity_search_with_score(query=query, k=k, filter=q_filter)

    def get_session_documents(
        self,
        session_id: str,
        source: Optional[str] = None,
        limit: int = 200,
    ) -> List[Document]:
        assert self._client is not None
        self._ensure_collection()
        q_filter = self._build_filter(session_id=session_id, source=source)
        points, _ = self._client.scroll(
            collection_name=self._collection_name,
            scroll_filter=q_filter,
            limit=limit,
            with_payload=True,
            with_vectors=False,
        )
        docs: List[Document] = []
        for pt in points:
            payload = pt.payload or {}
            content = payload.get("page_content", "")
            meta = payload.get("metadata", {})
            if content:
                docs.append(Document(page_content=content, metadata=meta))
        return docs


qdrant_store = QdrantRAGStore()
