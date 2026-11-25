from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from ingest import ingest_dual_pdfs, ingest_dual_texts, ingestion_engine
from workflow import (
    LearningStyle,
    ParsedSyllabus,
    PrioritizedTopic,
    QuizQuestion,
    RetrievedSource,
    TwistedQuestion,
    WorkedExample,
    WorkflowTraceEntry,
    agentic_rag_graph,
    make_trace,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# In-memory session state (stores parsed syllabus & cumulative workflow trace)
SESSION_STORE: Dict[str, Dict[str, Any]] = {}


class IngestResponse(BaseModel):
    session_id: str
    syllabus: ParsedSyllabus
    stats: Dict[str, Any]
    workflow_trace: List[WorkflowTraceEntry] = Field(default_factory=list)


class PrioritizeRequest(BaseModel):
    session_id: str
    unchecked_topics: List[str] = Field(..., min_length=1)
    hours_remaining: float = Field(..., ge=0.5, le=72.0)
    learning_style: LearningStyle = "Conceptual"


class PrioritizeResponse(BaseModel):
    session_id: str
    hours_remaining: float
    learning_style: LearningStyle
    strategy_note: str
    prioritized_topics: List[PrioritizedTopic]
    workflow_trace: List[WorkflowTraceEntry] = Field(default_factory=list)


class StudyPackRequest(BaseModel):
    session_id: str
    topic: str = Field(..., min_length=1)
    hours_remaining: float = Field(default=6.0, ge=0.5, le=72.0)
    learning_style: LearningStyle = "Conceptual"


class StudyPackResponse(BaseModel):
    session_id: str
    topic: str
    learning_style: LearningStyle
    summary: str
    worked_examples: List[WorkedExample]
    twisted_questions: List[TwistedQuestion] = Field(default_factory=list)
    quiz: List[QuizQuestion]
    cheat_sheet_markdown: str
    retrieved_sources: List[RetrievedSource] = Field(default_factory=list)
    workflow_trace: List[WorkflowTraceEntry] = Field(default_factory=list)
    notes_model: str = "Groq"
    generation_mode: str = "grounded-local-fallback"


DEMO_OS_SYLLABUS = """
CS-302: OPERATING SYSTEMS — B.TECH PRESCRIBED SYLLABUS
Credits: 4 | End-Semester Exam: 3 Hours

UNIT 1: Process Management & CPU Scheduling
- Process Control Block (PCB), Process States & Context Switching
- CPU Scheduling Criteria (Turnaround Time, Waiting Time, Response Time)
- Non-Preemptive Scheduling: FCFS (Convoy Effect) and SJF
- Preemptive Scheduling: SRTF, Round Robin (Time Quantum q), and Priority Aging

UNIT 2: Process Synchronization & Deadlocks
- Critical Section Requirements, Semaphores & Producer-Consumer Problem
- Deadlock Characterization (4 Coffman Conditions) & Resource Allocation Graphs
- Banker's Algorithm for Deadlock Avoidance (Safety & Resource-Request)
- Deadlock Prevention, Detection & Recovery

UNIT 3: Memory Management & Paging
- Contiguous Allocation (First Fit, Best Fit, Worst Fit) & Fragmentation
- Paging Hardware, Page Tables & Translation Lookaside Buffer (TLB EMAT)
- Multi-level Paging, Segmentation & Inverted Page Tables

UNIT 4: Virtual Memory & Disk Scheduling
- Demand Paging, Page Fault Handling & Effective Access Time (EAT)
- Page Replacement Algorithms: FIFO (Belady's Anomaly), Optimal (OPT) & LRU
- Frame Allocation, Thrashing & Working Set Model
- Disk Scheduling Algorithms: SSTF, SCAN & C-SCAN
""".strip()

DEMO_OS_PYQS = [
    (
        "OS_PYQ_2025_EndSem.pdf",
        """
[End-Semester Examination 2025 | CS-302 Operating Systems]
Q1 (10 Marks): P1(AT=0, BT=8), P2(AT=1, BT=4), P3(AT=2, BT=9), P4(AT=3, BT=5). Draw Gantt chart and compute Avg Waiting Time and Avg Turnaround Time using SRTF and Round Robin (q=3). Explain FCFS Convoy Effect.
Q2 (10 Marks): 5 processes P0..P4, resources A=10, B=5, C=7. Using Banker's Algorithm, compute Need matrix, Available vector, Safe Sequence, and check if P1 request (1,0,2) is granted.
Q3 (8 Marks): TLB access = 15 ns, main memory = 120 ns, hit ratio = 90%. Calculate EMAT and 32-bit Page Table size for 4 KB pages.
Q4 (8 Marks): Page reference string 7, 0, 1, 2, 0, 3, 0, 4, 2, 3, 0, 3, 2 with 3 frames. Find page faults for FIFO, Optimal, and LRU.
""",
    ),
    (
        "OS_PYQ_2024_EndSem.pdf",
        """
[End-Semester Examination 2024 | CS-302 Operating Systems]
Q1 (10 Marks): State the four Coffman conditions for Deadlock. How does Deadlock Prevention break Circular Wait? Verify safety sequence using Banker's Algorithm.
Q2 (10 Marks): Compare Priority Scheduling with Aging and Round Robin for Starvation, Response Time, and Context Switch overhead. Solve SRTF for P1(0,10), P2(1,5), P3(2,2).
Q3 (8 Marks): Memory access = 100 ns, TLB = 20 ns. What hit ratio gives EMAT <= 125 ns?
Q4 (8 Marks): Demonstrate Belady's Anomaly on 1,2,3,4,1,2,5,1,2,3,4,5 (3 vs 4 frames) and explain Thrashing.
""",
    ),
    (
        "OS_PYQ_2023_EndSem.pdf",
        """
[End-Semester Examination 2023 | CS-302 Operating Systems]
Q1 (10 Marks): Compare FCFS, SJF, and Round Robin (q=4). Why does small quantum degrade Round Robin?
Q2 (8 Marks): Draw a multi-instance Resource Allocation Graph with a cycle that is NOT a deadlock. Compare Deadlock Avoidance (Banker's Algorithm) vs Detection.
Q3 (8 Marks): Place 212 KB, 417 KB, 112 KB, 426 KB into partitions 100, 500, 200, 300, 600 KB using First Fit, Best Fit, and Worst Fit.
Q4 (10 Marks): Memory access = 200 ns, page fault service = 8 ms, fault rate p = 0.0001. Compute Effective Access Time (EAT) under Demand Paging.
""",
    ),
]


app = FastAPI(
    title="ExamPulse AI Backend",
    description="Constraint-aware Agentic RAG learning companion with LangGraph trace & grounded retrieval.",
    version="2.0.0",
)

cors_origins = [
    o.strip()
    for o in os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
    if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins or ["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health_check() -> Dict[str, Any]:
    return {
        "status": "ok",
        "qdrant_mode": ingestion_engine.qdrant_mode,
        "embedding_mode": ingestion_engine.embedding_mode,
        "persistence_mode": "memory",
        "gemini_configured": bool(os.getenv("GEMINI_API_KEY", "").strip()),
        "groq_configured": bool(os.getenv("GROQ_API_KEY", "").strip()),
    }


@app.post("/api/ingest", response_model=IngestResponse)
async def ingest_endpoint(
    syllabus_pdf: UploadFile = File(...),
    pyq_pdfs: List[UploadFile] = File(...),
) -> IngestResponse:
    if not syllabus_pdf.filename or not syllabus_pdf.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="syllabus_pdf must be a valid PDF file.")
    if not pyq_pdfs:
        raise HTTPException(status_code=400, detail="At least one PYQ PDF is required.")

    session_id = str(uuid4())
    syllabus_bytes = await syllabus_pdf.read()
    pyq_uploads = []
    for pyq in pyq_pdfs:
        if pyq.filename:
            pyq_uploads.append((pyq.filename, await pyq.read()))

    try:
        ingest_stats = ingest_dual_pdfs(
            session_id=session_id,
            syllabus_bytes=syllabus_bytes,
            syllabus_filename=syllabus_pdf.filename,
            pyq_uploads=pyq_uploads,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    initial_trace = make_trace(
        [],
        "ingest_dual_pdfs",
        "Indexed Syllabus & PYQs in Qdrant",
        f"Chunked & upserted {ingest_stats['syllabus_chunks_count']} syllabus chunks and {ingest_stats['pyq_chunks_count']} PYQ chunks ({ingest_stats['embedding_mode']}).",
        chunk_count=ingest_stats["syllabus_chunks_count"] + ingest_stats["pyq_chunks_count"],
    )

    graph_out = agentic_rag_graph.invoke(
        {
            "action": "parse_syllabus",
            "session_id": session_id,
            "raw_syllabus_text": ingest_stats["raw_syllabus_text"],
            "workflow_trace": initial_trace,
        }
    )
    parsed_syllabus: ParsedSyllabus = graph_out["parsed_syllabus"]
    trace: List[WorkflowTraceEntry] = graph_out["workflow_trace"]

    stats_payload = {
        "syllabus_chunks_count": ingest_stats["syllabus_chunks_count"],
        "pyq_chunks_count": ingest_stats["pyq_chunks_count"],
        "syllabus_chunks": ingest_stats["syllabus_chunks_count"],
        "pyq_chunks": ingest_stats["pyq_chunks_count"],
        "pyq_files": ingest_stats["pyq_files"],
        "qdrant_mode": ingest_stats["qdrant_mode"],
        "embedding_mode": ingest_stats["embedding_mode"],
    }

    SESSION_STORE[session_id] = {
        "syllabus": parsed_syllabus,
        "stats": stats_payload,
        "base_trace": trace,
        "priority_trace": [],
    }

    return IngestResponse(
        session_id=session_id,
        syllabus=parsed_syllabus,
        stats=stats_payload,
        workflow_trace=trace,
    )


@app.post("/api/load-demo", response_model=IngestResponse)
def load_demo_endpoint() -> IngestResponse:
    session_id = f"demo-{uuid4().hex[:8]}"
    ingest_stats = ingest_dual_texts(
        session_id=session_id,
        syllabus_text=DEMO_OS_SYLLABUS,
        syllabus_filename="CS302_OS_Syllabus.pdf",
        pyq_items=DEMO_OS_PYQS,
    )

    initial_trace = make_trace(
        [],
        "ingest_dual_texts",
        "Loaded OS Syllabus & 3 PYQ Papers into Qdrant",
        f"Upserted {ingest_stats['syllabus_chunks_count']} syllabus chunks and {ingest_stats['pyq_chunks_count']} PYQ chunks into Qdrant ({ingest_stats['qdrant_mode']}).",
        chunk_count=ingest_stats["syllabus_chunks_count"] + ingest_stats["pyq_chunks_count"],
    )

    graph_out = agentic_rag_graph.invoke(
        {
            "action": "parse_syllabus",
            "session_id": session_id,
            "raw_syllabus_text": DEMO_OS_SYLLABUS,
            "workflow_trace": initial_trace,
        }
    )
    parsed_syllabus: ParsedSyllabus = graph_out["parsed_syllabus"]
    trace: List[WorkflowTraceEntry] = graph_out["workflow_trace"]

    stats_payload = {
        "syllabus_chunks_count": ingest_stats["syllabus_chunks_count"],
        "pyq_chunks_count": ingest_stats["pyq_chunks_count"],
        "syllabus_chunks": ingest_stats["syllabus_chunks_count"],
        "pyq_chunks": ingest_stats["pyq_chunks_count"],
        "pyq_files": ingest_stats["pyq_files"],
        "qdrant_mode": ingest_stats["qdrant_mode"],
        "embedding_mode": ingest_stats["embedding_mode"],
        "is_demo": True,
    }

    SESSION_STORE[session_id] = {
        "syllabus": parsed_syllabus,
        "stats": stats_payload,
        "base_trace": trace,
        "priority_trace": [],
    }

    return IngestResponse(
        session_id=session_id,
        syllabus=parsed_syllabus,
        stats=stats_payload,
        workflow_trace=trace,
    )


@app.post("/api/prioritize", response_model=PrioritizeResponse)
def prioritize_endpoint(req: PrioritizeRequest) -> PrioritizeResponse:
    session = SESSION_STORE.get(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found. Upload PDFs or load demo first.")

    topic_unit_map: Dict[str, str] = {}
    parsed: ParsedSyllabus = session["syllabus"]
    for unit in parsed.units:
        label = f"{unit.unit_number}: {unit.unit_title}"
        for t in unit.topics:
            topic_unit_map[t] = label

    base_trace: List[WorkflowTraceEntry] = list(session.get("base_trace", []))
    graph_out = agentic_rag_graph.invoke(
        {
            "action": "prioritize",
            "session_id": req.session_id,
            "unchecked_topics": req.unchecked_topics,
            "topic_unit_map": topic_unit_map,
            "hours_remaining": req.hours_remaining,
            "learning_style": req.learning_style,
            "workflow_trace": base_trace,
        }
    )

    session["priority_trace"] = graph_out["workflow_trace"]

    return PrioritizeResponse(
        session_id=req.session_id,
        hours_remaining=req.hours_remaining,
        learning_style=req.learning_style,
        strategy_note=graph_out["strategy_note"],
        prioritized_topics=graph_out["prioritized_topics"],
        workflow_trace=graph_out["workflow_trace"],
    )


@app.post("/api/generate-study-pack", response_model=StudyPackResponse)
def generate_study_pack_endpoint(req: StudyPackRequest) -> StudyPackResponse:
    session = SESSION_STORE.get(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found. Upload PDFs or load demo first.")

    prior_trace: List[WorkflowTraceEntry] = list(
        session.get("priority_trace") or session.get("base_trace") or []
    )
    graph_out = agentic_rag_graph.invoke(
        {
            "action": "generate_study_pack",
            "session_id": req.session_id,
            "topic": req.topic,
            "hours_remaining": req.hours_remaining,
            "learning_style": req.learning_style,
            "workflow_trace": prior_trace,
        }
    )

    return StudyPackResponse(
        session_id=req.session_id,
        topic=req.topic,
        learning_style=req.learning_style,
        summary=graph_out["summary"],
        worked_examples=graph_out["worked_examples"],
        twisted_questions=graph_out.get("twisted_questions", []),
        quiz=graph_out["quiz"],
        cheat_sheet_markdown=graph_out["cheat_sheet_markdown"],
        retrieved_sources=graph_out["retrieved_sources"],
        workflow_trace=graph_out["workflow_trace"],
        notes_model=graph_out.get("notes_model", "Gemini (gemini-3.5-flash-lite)"),
        generation_mode=graph_out.get("generation_mode", "grounded-local-fallback"),
    )
