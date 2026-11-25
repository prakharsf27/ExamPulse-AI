from __future__ import annotations

import logging
from typing import Dict, List
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.demo_data import DEMO_PYQ_PAPERS, DEMO_SYLLABUS_TEXT
from app.models import (
    IngestResponse,
    ParsedSyllabus,
    PrioritizeRequest,
    PrioritizeResponse,
    StudyPackRequest,
    StudyPackResponse,
)
from app.pdf_parser import chunk_text, extract_text_from_pdf
from app.qdrant_store import qdrant_store
from app.rag_graph import (
    prioritize_graph,
    run_study_pack_workflow,
    syllabus_parser_graph,
)
from app.state_store import state_store

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="ExamPulse AI Backend",
    description="Constraint-aware Agentic RAG learning companion for engineering exam preparation.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health_check() -> Dict[str, object]:
    return {
        "status": "ok",
        "qdrant_mode": qdrant_store.mode,
        "embedding_mode": qdrant_store.embedding_mode,
        "persistence_mode": state_store.mode,
        "gemini_configured": settings.has_gemini,
        "groq_configured": settings.has_groq,
    }


@app.post("/api/ingest", response_model=IngestResponse)
async def ingest_documents(
    syllabus_pdf: UploadFile = File(...),
    pyq_pdfs: List[UploadFile] = File(...),
) -> IngestResponse:
    if not syllabus_pdf.filename or not syllabus_pdf.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="syllabus_pdf must be a valid PDF file.")
    if not pyq_pdfs:
        raise HTTPException(status_code=400, detail="At least one PYQ PDF is required.")

    session_id = str(uuid4())

    syllabus_bytes = await syllabus_pdf.read()
    syllabus_text = extract_text_from_pdf(syllabus_bytes, syllabus_pdf.filename)
    if not syllabus_text.strip():
        raise HTTPException(
            status_code=400,
            detail="Could not extract selectable text from syllabus PDF. Ensure it is not a scanned image-only PDF.",
        )

    all_docs = chunk_text(
        syllabus_text,
        metadata={"source": "syllabus", "filename": syllabus_pdf.filename},
        chunk_size=1000,
        chunk_overlap=200,
    )
    syllabus_chunk_count = len(all_docs)

    pyq_filenames: List[str] = []
    pyq_chunk_count = 0
    for pyq in pyq_pdfs:
        if not pyq.filename:
            continue
        pyq_bytes = await pyq.read()
        pyq_text = extract_text_from_pdf(pyq_bytes, pyq.filename)
        if not pyq_text.strip():
            continue
        pyq_docs = chunk_text(
            pyq_text,
            metadata={"source": "pyq", "filename": pyq.filename},
            chunk_size=1000,
            chunk_overlap=200,
        )
        all_docs.extend(pyq_docs)
        pyq_chunk_count += len(pyq_docs)
        pyq_filenames.append(pyq.filename)

    if pyq_chunk_count == 0:
        raise HTTPException(
            status_code=400,
            detail="Could not extract text from any of the uploaded PYQ PDFs.",
        )

    qdrant_store.upsert_documents(session_id=session_id, docs=all_docs)

    parser_result = syllabus_parser_graph.invoke({"raw_text": syllabus_text, "parsed": None})
    parsed_syllabus: ParsedSyllabus = parser_result["parsed"]

    state_store.save_session(
        session_id,
        {
            "session_id": session_id,
            "is_demo": False,
            "syllabus": parsed_syllabus.model_dump(),
            "stats": {
                "syllabus_chunks": syllabus_chunk_count,
                "pyq_chunks": pyq_chunk_count,
                "pyq_files": pyq_filenames,
            },
        },
    )

    return IngestResponse(
        session_id=session_id,
        syllabus=parsed_syllabus,
        stats={
            "syllabus_chunks": syllabus_chunk_count,
            "pyq_chunks": pyq_chunk_count,
            "pyq_files": pyq_filenames,
            "qdrant_mode": qdrant_store.mode,
        },
    )


@app.post("/api/load-demo", response_model=IngestResponse)
def load_demo_session() -> IngestResponse:
    session_id = f"demo-{uuid4().hex[:8]}"

    syllabus_docs = chunk_text(
        DEMO_SYLLABUS_TEXT,
        metadata={"source": "syllabus", "filename": "CS302_OS_Syllabus.pdf"},
        chunk_size=1000,
        chunk_overlap=200,
    )

    pyq_docs = []
    pyq_files = []
    for paper in DEMO_PYQ_PAPERS:
        pyq_files.append(paper["filename"])
        pyq_docs.extend(
            chunk_text(
                paper["text"],
                metadata={"source": "pyq", "filename": paper["filename"]},
                chunk_size=1000,
                chunk_overlap=200,
            )
        )

    qdrant_store.upsert_documents(session_id=session_id, docs=syllabus_docs + pyq_docs)

    parser_result = syllabus_parser_graph.invoke({"raw_text": DEMO_SYLLABUS_TEXT, "parsed": None})
    parsed_syllabus: ParsedSyllabus = parser_result["parsed"]

    stats = {
        "syllabus_chunks": len(syllabus_docs),
        "pyq_chunks": len(pyq_docs),
        "pyq_files": pyq_files,
        "qdrant_mode": qdrant_store.mode,
        "is_demo": True,
    }

    state_store.save_session(
        session_id,
        {
            "session_id": session_id,
            "is_demo": True,
            "syllabus": parsed_syllabus.model_dump(),
            "stats": stats,
        },
    )

    return IngestResponse(session_id=session_id, syllabus=parsed_syllabus, stats=stats)


@app.post("/api/prioritize", response_model=PrioritizeResponse)
def prioritize_topics(req: PrioritizeRequest) -> PrioritizeResponse:
    session = state_store.get_session(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found. Please upload PDFs or load the demo first.")

    # Verify Qdrant still has vectors for this session (e.g., if server restarted with :memory:)
    existing_docs = qdrant_store.get_session_documents(session_id=req.session_id, limit=1)
    if not existing_docs:
        raise HTTPException(
            status_code=409,
            detail="Vector index for this session expired (in-memory Qdrant reset). Please re-upload or reload demo.",
        )

    topic_unit_map: Dict[str, str] = {}
    for unit in session["syllabus"]["units"]:
        label = f"{unit['unit_number']}: {unit['unit_title']}"
        for t in unit["topics"]:
            topic_unit_map[t] = label

    result = prioritize_graph.invoke(
        {
            "session_id": req.session_id,
            "unchecked_topics": req.unchecked_topics,
            "topic_unit_map": topic_unit_map,
            "hours_remaining": req.hours_remaining,
            "learning_style": req.learning_style,
            "raw_scores": [],
            "prioritized_topics": [],
            "strategy_note": "",
        }
    )

    return PrioritizeResponse(
        session_id=req.session_id,
        hours_remaining=req.hours_remaining,
        learning_style=req.learning_style,
        strategy_note=result["strategy_note"],
        prioritized_topics=result["prioritized_topics"],
    )


@app.post("/api/generate-study-pack", response_model=StudyPackResponse)
def generate_study_pack(req: StudyPackRequest) -> StudyPackResponse:
    session = state_store.get_session(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found. Please upload PDFs or load the demo first.")

    existing_docs = qdrant_store.get_session_documents(session_id=req.session_id, limit=1)
    if not existing_docs:
        raise HTTPException(
            status_code=409,
            detail="Vector index for this session expired (in-memory Qdrant reset). Please re-upload or reload demo.",
        )

    return run_study_pack_workflow(
        session_id=req.session_id,
        topic=req.topic,
        hours_remaining=req.hours_remaining,
        learning_style=req.learning_style,
    )
