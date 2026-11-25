from __future__ import annotations

import hashlib
import logging
import math
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

import fitz  # PyMuPDF
from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_qdrant import QdrantVectorStore
from langchain_text_splitters import RecursiveCharacterTextSplitter
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PayloadSchemaType,
    VectorParams,
)

ROOT_ENV = Path(__file__).resolve().parents[1] / ".env"
LOCAL_ENV = Path(__file__).resolve().parent / ".env"
load_dotenv(ROOT_ENV, override=False)
load_dotenv(LOCAL_ENV, override=False)

logger = logging.getLogger(__name__)


class LocalHashEmbeddings(Embeddings):
    """Lightweight deterministic embeddings used when cloud or transformer embeddings are unavailable."""

    def __init__(self, dimension: int = 384) -> None:
        self.dimension = dimension

    def _embed(self, text: str) -> List[float]:
        vec = [0.0] * self.dimension
        tokens = re.findall(r"[a-z0-9_]+", text.lower())
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


class BGEEmbeddingsWrapper(Embeddings):
    """Wrapper around BAAI/bge-small-en-v1.5 via sentence-transformers when USE_LOCAL_EMBEDDINGS=true."""

    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5") -> None:
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(model_name)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return self.model.encode(texts, normalize_embeddings=True).tolist()

    def embed_query(self, text: str) -> List[float]:
        return self.model.encode(text, normalize_embeddings=True).tolist()


class QdrantIngestionEngine:
    """Handles dual-PDF extraction, chunking, metadata tagging, and Qdrant vector upsert/search."""

    def __init__(self) -> None:
        self._client: Optional[QdrantClient] = None
        self._embeddings: Optional[Embeddings] = None
        self._qdrant_mode = "memory"
        self._embedding_mode = "local-hash"
        self._vector_size = 384
        self._collection_base = os.getenv("QDRANT_COLLECTION", "exampulse_rag")
        self._collection_name = f"{self._collection_base}_local_384"
        self._initialized_collections: set[str] = set()
        self._init_clients()

    def _init_clients(self) -> None:
        use_local_bge = os.getenv("USE_LOCAL_EMBEDDINGS", "false").lower() == "true"
        gemini_key = os.getenv("GEMINI_API_KEY", "").strip()

        if use_local_bge:
            try:
                bge = BGEEmbeddingsWrapper("BAAI/bge-small-en-v1.5")
                probe = bge.embed_query("ExamPulse probe")
                self._embeddings = bge
                self._embedding_mode = "bge-small-en-v1.5"
                self._vector_size = len(probe)
                self._collection_name = f"{self._collection_base}_bge_{self._vector_size}"
            except Exception as exc:
                logger.warning("Local BGE embeddings unavailable (%s); using deterministic hash embeddings.", exc)

        if self._embeddings is None and gemini_key:
            from langchain_google_genai import GoogleGenerativeAIEmbeddings

            candidate_models = [
                os.getenv("GEMINI_EMBEDDING_MODEL", "").strip(),
                "models/gemini-embedding-001",
                "models/gemini-embedding-001",
            ]
            for emb_model in [m for m in candidate_models if m]:
                try:
                    gemini_emb = GoogleGenerativeAIEmbeddings(
                        model=emb_model,
                        google_api_key=gemini_key,
                    )
                    probe = gemini_emb.embed_query("ExamPulse probe")
                    self._embeddings = gemini_emb
                    self._embedding_mode = f"gemini ({emb_model})"
                    self._vector_size = len(probe)
                    self._collection_name = f"{self._collection_base}_gemini_{self._vector_size}"
                    break
                except Exception as exc:
                    logger.warning("Gemini embedding %s unavailable (%s).", emb_model, exc)

        if self._embeddings is None:
            self._embeddings = LocalHashEmbeddings(dimension=384)
            self._embedding_mode = "local-hash"
            self._vector_size = 384
            self._collection_name = f"{self._collection_base}_local_384"

        qdrant_url = os.getenv("QDRANT_URL", "").strip()
        qdrant_api_key = os.getenv("QDRANT_API_KEY", "").strip() or None

        if qdrant_url:
            try:
                self._client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key, timeout=15.0)
                self._client.get_collections()
                self._qdrant_mode = "cloud"
            except Exception as exc:
                logger.warning("Qdrant Cloud unavailable (%s); falling back to :memory:.", exc)
                self._client = QdrantClient(":memory:")
                self._qdrant_mode = "memory"
        else:
            self._client = QdrantClient(":memory:")
            self._qdrant_mode = "memory"

        self._ensure_collection()

    @property
    def qdrant_mode(self) -> str:
        return self._qdrant_mode

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

        if self._qdrant_mode == "cloud":
            for field in ("metadata.session_id", "metadata.source", "metadata.paper_name"):
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
        conditions = [FieldCondition(key="metadata.session_id", match=MatchValue(value=session_id))]
        if source:
            conditions.append(FieldCondition(key="metadata.source", match=MatchValue(value=source)))
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
        k: int = 4,
    ) -> List[Tuple[Document, float]]:
        vs = self._vector_store()
        q_filter = self._build_filter(session_id=session_id, source=source)
        return vs.similarity_search_with_score(query=query, k=k, filter=q_filter)

    def get_session_documents(
        self,
        session_id: str,
        source: Optional[str] = None,
        limit: int = 300,
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


def extract_pdf_text(file_bytes: bytes, filename: str) -> str:
    """Extract selectable text page-by-page from a PDF byte buffer via PyMuPDF."""
    pages: List[str] = []
    with fitz.open(stream=file_bytes, filetype="pdf") as pdf_doc:
        for page_idx, page in enumerate(pdf_doc, start=1):
            text = page.get_text("text").strip()
            if text:
                pages.append(f"[Page {page_idx} | {filename}]\n{text}")
    return "\n\n".join(pages)


def chunk_document_text(
    text: str,
    metadata: Dict[str, Any],
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
) -> List[Document]:
    """Chunk text using RecursiveCharacterTextSplitter and attach source metadata."""
    cleaned = text.strip()
    if not cleaned:
        return []
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = splitter.split_text(cleaned)
    docs: List[Document] = []
    for idx, chunk in enumerate(chunks):
        meta = dict(metadata)
        meta["chunk_index"] = idx
        docs.append(Document(page_content=chunk, metadata=meta))
    return docs


ingestion_engine = QdrantIngestionEngine()


def ingest_dual_texts(
    session_id: str,
    syllabus_text: str,
    syllabus_filename: str,
    pyq_items: List[Tuple[str, str]],
) -> Dict[str, Any]:
    """Chunk, tag, embed, and upsert syllabus + PYQ texts into Qdrant."""
    syllabus_docs = chunk_document_text(
        syllabus_text,
        metadata={"source": "syllabus", "paper_name": syllabus_filename, "session_id": session_id},
        chunk_size=1000,
        chunk_overlap=200,
    )

    pyq_docs: List[Document] = []
    pyq_files: List[str] = []
    for fname, ptext in pyq_items:
        docs = chunk_document_text(
            ptext,
            metadata={"source": "pyq", "paper_name": fname, "session_id": session_id},
            chunk_size=1000,
            chunk_overlap=200,
        )
        if docs:
            pyq_docs.extend(docs)
            pyq_files.append(fname)

    ingestion_engine.upsert_documents(session_id=session_id, docs=syllabus_docs + pyq_docs)

    return {
        "session_id": session_id,
        "syllabus_chunks_count": len(syllabus_docs),
        "pyq_chunks_count": len(pyq_docs),
        "pyq_files": pyq_files,
        "qdrant_mode": ingestion_engine.qdrant_mode,
        "embedding_mode": ingestion_engine.embedding_mode,
        "raw_syllabus_text": syllabus_text,
    }


def ingest_dual_pdfs(
    session_id: str,
    syllabus_bytes: bytes,
    syllabus_filename: str,
    pyq_uploads: List[Tuple[str, bytes]],
) -> Dict[str, Any]:
    """Extract PDFs via PyMuPDF and upsert tagged chunks into Qdrant."""
    syllabus_text = extract_pdf_text(syllabus_bytes, syllabus_filename)
    if not syllabus_text.strip():
        raise ValueError("Could not extract selectable text from the syllabus PDF.")

    pyq_items: List[Tuple[str, str]] = []
    for fname, raw_bytes in pyq_uploads:
        text = extract_pdf_text(raw_bytes, fname)
        if text.strip():
            pyq_items.append((fname, text))

    if not pyq_items:
        raise ValueError("Could not extract selectable text from any uploaded PYQ PDF.")

    return ingest_dual_texts(
        session_id=session_id,
        syllabus_text=syllabus_text,
        syllabus_filename=syllabus_filename,
        pyq_items=pyq_items,
    )
