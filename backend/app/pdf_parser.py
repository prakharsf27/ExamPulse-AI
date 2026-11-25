from __future__ import annotations

from typing import Any, Dict, List
import fitz  # PyMuPDF
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter


def extract_text_from_pdf(file_bytes: bytes, filename: str) -> str:
    """Extract clean text page-by-page from a PDF byte buffer using PyMuPDF."""
    pages: List[str] = []
    with fitz.open(stream=file_bytes, filetype="pdf") as doc:
        for page_index, page in enumerate(doc, start=1):
            text = page.get_text("text").strip()
            if text:
                pages.append(f"[Page {page_index} | {filename}]\n{text}")
    return "\n\n".join(pages)


def chunk_text(
    text: str,
    metadata: Dict[str, Any],
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
) -> List[Document]:
    """Split text into overlapping LangChain Documents preserving metadata."""
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
        doc_meta = dict(metadata)
        doc_meta["chunk_index"] = idx
        docs.append(Document(page_content=chunk, metadata=doc_meta))
    return docs
