from __future__ import annotations

import html
import logging
import os
import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
import httpx
from pydantic import BaseModel, Field

from ingest import ingest_dual_pdfs, ingest_dual_texts, ingestion_engine
from workflow import (
    DoubtSource,
    LearningStyle,
    ParsedSyllabus,
    PrioritizedTopic,
    QuizQuestion,
    RetrievedSource,
    SubjectSummaryData,
    TwistedQuestion,
    UnitKeypoint,
    WorkedExample,
    WorkflowTraceEntry,
    agentic_rag_graph,
    ask_doubt_pipeline,
    generate_subject_summary_pipeline,
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


class SubjectSummaryRequest(BaseModel):
    session_id: str
    learning_style: LearningStyle = "Conceptual"
    hours_remaining: float = Field(default=8.0, ge=0.5, le=72.0)


class SubjectSummaryResponse(BaseModel):
    session_id: str
    subject_title: str
    executive_overview: str
    unit_keypoints: List[UnitKeypoint]
    high_probability_takeaways: List[str]
    last_15_min_checklist: List[str]
    full_markdown: str
    model_used: str


class EmailSummaryRequest(BaseModel):
    recipient_email: str
    subject_title: str
    summary_data: Optional[SubjectSummaryData] = None
    full_markdown: Optional[str] = None


class AskDoubtRequest(BaseModel):
    session_id: str
    topic: str = Field(..., min_length=1)
    question: str = Field(..., min_length=2)


class AskDoubtResponse(BaseModel):
    answer: str
    grounded: bool
    model_used: str
    sources: List[DoubtSource] = Field(default_factory=list)


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
frontend_url = os.getenv("FRONTEND_URL", "").strip().rstrip("/")
if frontend_url and frontend_url not in cors_origins:
    cors_origins.append(frontend_url)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins or ["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_origin_regex=r"https://.*\.vercel\.app",
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
    session["prioritized_topics"] = graph_out["prioritized_topics"]

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


@app.post("/api/generate-subject-summary", response_model=SubjectSummaryResponse)
def generate_subject_summary_endpoint(req: SubjectSummaryRequest) -> SubjectSummaryResponse:
    session = SESSION_STORE.get(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found. Upload PDFs or load demo first.")

    summary_data, model_used = generate_subject_summary_pipeline(
        session_id=req.session_id,
        syllabus=session["syllabus"],
        learning_style=req.learning_style,
        hours_remaining=req.hours_remaining,
        prioritized_topics=session.get("prioritized_topics"),
    )

    return SubjectSummaryResponse(
        session_id=req.session_id,
        subject_title=summary_data.subject_title,
        executive_overview=summary_data.executive_overview,
        unit_keypoints=summary_data.unit_keypoints,
        high_probability_takeaways=summary_data.high_probability_takeaways,
        last_15_min_checklist=summary_data.last_15_min_checklist,
        full_markdown=summary_data.full_markdown,
        model_used=model_used,
    )


def _render_summary_email_html(
    subject_title: str,
    summary_data: Optional[SubjectSummaryData],
    full_markdown: Optional[str],
) -> str:
    esc = html.escape
    if summary_data is None:
        body_text = esc(full_markdown or "").replace("\n", "<br/>")
        return f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 680px; margin: 0 auto; background: #FFFCF5; border: 1px solid #E2E8F0; border-radius: 12px; overflow: hidden;">
          <div style="background: #1E3A8A; color: #ffffff; padding: 24px;">
            <h1 style="margin: 0; font-size: 20px;">ExamPulse AI — Master Revision Summary</h1>
            <p style="margin: 6px 0 0; color: #DBEAFE; font-size: 14px;">{esc(subject_title)}</p>
          </div>
          <div style="padding: 24px; color: #0F172A; font-size: 14px; line-height: 1.6;">{body_text}</div>
        </div>
        """

    units_html = []
    for uk in summary_data.unit_keypoints:
        concepts_li = "".join(
            f"<li style='margin-bottom:4px;'>{esc(c)}</li>" for c in uk.key_concepts
        )
        formulas_pills = "".join(
            f"<span style='display:inline-block; background:#EEF2FF; color:#1E3A8A; border:1px solid #C7D2FE; border-radius:6px; padding:3px 8px; margin:3px 4px 3px 0; font-family:monospace; font-size:12px;'>{esc(f)}</span>"
            for f in uk.must_remember_formulas
        )
        tip_block = (
            f"<div style='margin-top:10px; padding:8px 12px; background:#FDF3F0; border-left:3px solid #E17055; color:#9C3E27; font-size:12px;'><strong>Examiner Tip:</strong> {esc(uk.exam_tip)}</div>"
            if uk.exam_tip
            else ""
        )
        units_html.append(
            f"""
            <div style="background:#ffffff; border:1px solid #E2E8F0; border-radius:10px; padding:16px; margin-bottom:14px;">
              <h3 style="margin:0 0 10px; color:#1E3A8A; font-size:15px;">{esc(uk.unit)}</h3>
              <ul style="margin:0 0 8px; padding-left:18px; color:#334155; font-size:13px;">{concepts_li}</ul>
              {f"<div style='margin-top:8px;'>{formulas_pills}</div>" if formulas_pills else ""}
              {tip_block}
            </div>
            """
        )

    takeaways_li = "".join(
        f"<li style='margin-bottom:6px;'>{esc(t)}</li>"
        for t in summary_data.high_probability_takeaways
    )
    checklist_li = "".join(
        f"<li style='margin-bottom:6px;'>&#9744; {esc(c)}</li>"
        for c in summary_data.last_15_min_checklist
    )

    return f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 700px; margin: 0 auto; background: #FFFCF5; border: 1px solid #E2E8F0; border-radius: 14px; overflow: hidden;">
      <div style="background: #1E3A8A; color: #ffffff; padding: 24px 28px;">
        <div style="font-size: 11px; letter-spacing: 1px; text-transform: uppercase; color: #FDBA74; font-weight: 700;">ExamPulse AI · Last-Minute Revision Brief</div>
        <h1 style="margin: 6px 0 0; font-size: 22px;">{esc(summary_data.subject_title or subject_title)}</h1>
      </div>

      <div style="padding: 24px 28px; color: #0F172A;">
        <div style="background: #ffffff; border: 1px solid #E2E8F0; border-radius: 10px; padding: 16px; margin-bottom: 18px;">
          <h2 style="margin: 0 0 8px; color: #1E3A8A; font-size: 15px;">Executive Overview</h2>
          <p style="margin: 0; color: #334155; font-size: 13.5px; line-height: 1.6;">{esc(summary_data.executive_overview)}</p>
        </div>

        <h2 style="margin: 0 0 12px; color: #1E3A8A; font-size: 16px;">Unit-by-Unit Keypoints</h2>
        {"".join(units_html)}

        <div style="background: #EEF2FF; border: 1px solid #C7D2FE; border-radius: 10px; padding: 16px; margin-top: 18px;">
          <h2 style="margin: 0 0 8px; color: #1E3A8A; font-size: 15px;">High-Probability Exam Takeaways</h2>
          <ul style="margin: 0; padding-left: 18px; color: #1E293B; font-size: 13px;">{takeaways_li}</ul>
        </div>

        <div style="background: #FDF3F0; border: 1px solid #FADFD7; border-radius: 10px; padding: 16px; margin-top: 14px;">
          <h2 style="margin: 0 0 8px; color: #C85A40; font-size: 15px;">Last 15-Minute Exam Hall Checklist</h2>
          <ul style="margin: 0; padding-left: 18px; list-style: none; color: #1E293B; font-size: 13px;">{checklist_li}</ul>
        </div>
      </div>

      <div style="background: #F8FAFC; padding: 14px 28px; text-align: center; color: #64748B; font-size: 11px; border-top: 1px solid #E2E8F0;">
        Generated by ExamPulse AI · Syllabus-Grounded Agentic RAG
      </div>
    </div>
    """


@app.post("/api/email-summary")
def email_summary_endpoint(req: EmailSummaryRequest) -> Dict[str, str]:
    recipient = req.recipient_email.strip()
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", recipient):
        raise HTTPException(status_code=400, detail="Please enter a valid recipient email address.")

    if req.summary_data is None and not (req.full_markdown and req.full_markdown.strip()):
        raise HTTPException(status_code=400, detail="Summary content is required to send an email.")

    brevo_api_key = os.getenv("BREVO_API_KEY", "").strip()
    smtp_email = os.getenv("SMTP_EMAIL", "").strip()
    smtp_password = os.getenv("SMTP_APP_PASSWORD", "").strip()

    plain_text = (
        (req.summary_data.full_markdown if req.summary_data else "")
        or req.full_markdown
        or req.subject_title
    )
    html_body = _render_summary_email_html(req.subject_title, req.summary_data, req.full_markdown)

    if brevo_api_key:
        if not smtp_email:
            raise HTTPException(
                status_code=400,
                detail="Sender email is not configured on the server (missing SMTP_EMAIL for Brevo sender).",
            )
        try:
            brevo_resp = httpx.post(
                "https://api.brevo.com/v3/smtp/email",
                headers={
                    "api-key": brevo_api_key,
                    "Content-Type": "application/json",
                },
                json={
                    "sender": {"name": "ExamPulse AI", "email": smtp_email},
                    "to": [{"email": recipient}],
                    "subject": f"ExamPulse AI — Master Revision Summary: {req.subject_title}",
                    "htmlContent": html_body,
                },
                timeout=20.0,
            )
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to connect to Brevo API: {exc}",
            ) from exc

        if brevo_resp.status_code >= 400:
            raise HTTPException(
                status_code=brevo_resp.status_code if brevo_resp.status_code < 500 else 502,
                detail=f"Brevo API error ({brevo_resp.status_code}): {brevo_resp.text}",
            )

        return {"status": "sent", "recipient": recipient}


@app.post("/api/ask-doubt", response_model=AskDoubtResponse)
def ask_doubt_endpoint(req: AskDoubtRequest) -> AskDoubtResponse:
    session = SESSION_STORE.get(req.session_id)
    if not session:
        raise HTTPException(
            status_code=404,
            detail="Session not found. Upload PDFs or load the demo first.",
        )

    result = ask_doubt_pipeline(
        session_id=req.session_id,
        topic=req.topic,
        question=req.question,
    )
    return AskDoubtResponse(**result)

    if not smtp_email or not smtp_password:
        raise HTTPException(
            status_code=400,
            detail="Email delivery is not configured on the server (set BREVO_API_KEY + SMTP_EMAIL, or SMTP_EMAIL + SMTP_APP_PASSWORD).",
        )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"ExamPulse AI Revision Summary: {req.subject_title}"
    msg["From"] = f"ExamPulse AI <{smtp_email}>"
    msg["To"] = recipient
    msg.attach(MIMEText(plain_text, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=20) as server:
            server.login(smtp_email, smtp_password)
            server.sendmail(smtp_email, [recipient], msg.as_string())
    except smtplib.SMTPAuthenticationError as exc:
        raise HTTPException(
            status_code=400,
            detail="Gmail SMTP authentication failed. Verify SMTP_EMAIL and your 16-character Gmail App Password.",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to send email via Gmail SMTP: {exc}",
        ) from exc

    return {"status": "sent", "recipient": recipient}


@app.post("/api/ask-doubt", response_model=AskDoubtResponse)
def ask_doubt_endpoint(req: AskDoubtRequest) -> AskDoubtResponse:
    session = SESSION_STORE.get(req.session_id)
    if not session:
        raise HTTPException(
            status_code=404,
            detail="Session not found. Upload PDFs or load the demo first.",
        )

    result = ask_doubt_pipeline(
        session_id=req.session_id,
        topic=req.topic,
        question=req.question,
    )
    return AskDoubtResponse(**result)
