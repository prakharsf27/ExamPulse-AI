from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional, TypedDict

from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

from ingest import ingestion_engine

logger = logging.getLogger(__name__)

LearningStyle = Literal["Crash Course", "Conceptual", "Numerical-Heavy"]
PriorityTier = Literal["Critical", "High", "Medium", "Low"]


class SyllabusUnit(BaseModel):
    unit_number: str
    unit_title: str
    topics: List[str]


class ParsedSyllabus(BaseModel):
    course_title: str
    units: List[SyllabusUnit]


class MatchedPYQ(BaseModel):
    question_snippet: str
    source_file: str
    relevance_score: float


class PrioritizedTopic(BaseModel):
    topic: str
    unit_title: str
    priority_rank: int
    priority_tier: PriorityTier
    pyq_frequency: int
    relevance_score: float
    allocated_hours: float
    rationale: str
    matched_pyqs: List[MatchedPYQ] = Field(default_factory=list)


class WorkedExample(BaseModel):
    title: str = "Solved Exam Example"
    problem_statement: str
    given_data: List[str] = Field(default_factory=list)
    formulae_used: List[str] = Field(default_factory=list)
    steps: List[str]
    final_answer: str
    exam_tip: str = ""


class QuizQuestion(BaseModel):
    id: int = 1
    question: str
    options: List[str] = Field(..., min_length=4, max_length=4)
    correct_index: int = Field(..., ge=0, le=3)
    explanation: str
    pyq_tag: Optional[str] = None


class GeneratedNotesPack(BaseModel):
    summary: str = Field(..., description="Markdown summary tailored to learning_style and hours_remaining")
    worked_examples: List[WorkedExample] = Field(..., min_length=1, description="Step-by-step solved numericals/examples")
    cheat_sheet_markdown: str = Field(..., description="Dense 1-page formula and key-concept revision sheet in Markdown")


class GeneratedQuizPack(BaseModel):
    quiz: List[QuizQuestion] = Field(..., min_length=3, max_length=5, description="5 PYQ-style MCQs grounded in the context")


class RetrievedSource(BaseModel):
    source: Literal["syllabus", "pyq"]
    paper_name: str
    excerpt: str
    score: float
    chunk_index: int = 0


class WorkflowTraceEntry(BaseModel):
    step: int
    node: str
    title: str
    detail: str
    timestamp: str
    chunk_count: Optional[int] = None
    status: Literal["completed", "fallback"] = "completed"


class AgentState(TypedDict, total=False):
    action: Literal["parse_syllabus", "prioritize", "generate_study_pack"]
    session_id: str
    raw_syllabus_text: str
    parsed_syllabus: Optional[ParsedSyllabus]
    unchecked_topics: List[str]
    topic_unit_map: Dict[str, str]
    hours_remaining: float
    learning_style: LearningStyle
    prioritized_topics: List[PrioritizedTopic]
    strategy_note: str
    topic: str
    syllabus_chunks: List[Document]
    pyq_chunks: List[Document]
    retrieved_sources: List[RetrievedSource]
    summary: str
    worked_examples: List[WorkedExample]
    quiz: List[QuizQuestion]
    cheat_sheet_markdown: str
    generation_mode: str
    workflow_trace: List[WorkflowTraceEntry]


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%S UTC")


def make_trace(
    existing: List[WorkflowTraceEntry],
    node: str,
    title: str,
    detail: str,
    chunk_count: Optional[int] = None,
    status: Literal["completed", "fallback"] = "completed",
) -> List[WorkflowTraceEntry]:
    return [
        *existing,
        WorkflowTraceEntry(
            step=len(existing) + 1,
            node=node,
            title=title,
            detail=detail,
            timestamp=_now_iso(),
            chunk_count=chunk_count,
            status=status,
        ),
    ]


def _get_gemini_llm(model_name: str, temperature: float = 0.0, timeout: int = 18):
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        return None
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=api_key,
            temperature=temperature,
            max_retries=0,
            timeout=timeout,
        )
    except Exception as exc:
        logger.warning("Failed to initialize Gemini (%s): %s", model_name, exc)
        return None


def _get_groq_llm(temperature: float = 0.0, timeout: int = 15):
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        return None
    try:
        from langchain_groq import ChatGroq

        return ChatGroq(
            model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
            groq_api_key=api_key,
            temperature=temperature,
            max_retries=0,
            timeout=timeout,
        )
    except Exception as exc:
        logger.warning("Failed to initialize Groq: %s", exc)
        return None


def _strip_json_fences(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        return m.group(0).strip()
    return text.strip()


def _deterministic_parse_syllabus(raw_text: str) -> ParsedSyllabus:
    lines = [ln.strip() for ln in raw_text.splitlines() if ln.strip()]
    course_title = "Engineering Course Syllabus"
    for ln in lines[:6]:
        if "unit" not in ln.lower() and "module" not in ln.lower() and len(ln) > 6:
            cleaned = re.sub(r"^\[Page.*?\]\s*", "", ln).strip()
            if cleaned and not cleaned.lower().startswith("credits"):
                course_title = cleaned[:100]
                break

    units: List[SyllabusUnit] = []
    current_num = ""
    current_title = ""
    current_topics: List[str] = []
    unit_re = re.compile(
        r"^(?:UNIT|MODULE|CHAPTER)\s*[-–:]?\s*([IVX\d]+)\s*[-–:]?\s*(.+)$",
        re.IGNORECASE,
    )

    def flush() -> None:
        nonlocal current_num, current_title, current_topics
        if current_title and current_topics:
            units.append(
                SyllabusUnit(
                    unit_number=current_num or f"Unit {len(units) + 1}",
                    unit_title=current_title,
                    topics=list(dict.fromkeys(current_topics))[:10],
                )
            )
        current_topics = []

    for ln in lines:
        if ln.startswith("[Page "):
            continue
        m = unit_re.match(ln)
        if m:
            flush()
            current_num = f"Unit {m.group(1).strip()}"
            current_title = m.group(2).strip(" :-")
            continue
        if current_title:
            cleaned = re.sub(r"^[-*•\d.)]+\s*", "", ln).strip()
            if len(cleaned) >= 4:
                current_topics.append(cleaned[:95].rstrip("."))
    flush()

    if not units:
        units = [
            SyllabusUnit(
                unit_number="Unit 1",
                unit_title="Core Syllabus Topics",
                topics=[ln[:85] for ln in lines if not ln.startswith("[Page ") and len(ln) > 8][:8]
                or ["Core Fundamentals"],
            )
        ]
    return ParsedSyllabus(course_title=course_title, units=units)


# ---------------------------------------------------------------------------
# Node 1: parse_syllabus_node
# ---------------------------------------------------------------------------


def parse_syllabus_node(state: AgentState) -> Dict[str, Any]:
    raw_text = state.get("raw_syllabus_text", "")
    trace = list(state.get("workflow_trace") or [])
    parser_model = os.getenv("GEMINI_PARSER_MODEL", "gemini-3.5-flash-lite")

    llm = _get_gemini_llm(parser_model, temperature=0.0)
    if llm is not None:
        try:
            structured = llm.with_structured_output(ParsedSyllabus)
            parsed = structured.invoke(
                "Extract a clean structured university syllabus with Units and concise Topics "
                "using ONLY the provided syllabus text.\n\n"
                f"SYLLABUS:\n{raw_text[:18000]}"
            )
            if parsed and parsed.units:
                topic_count = sum(len(u.topics) for u in parsed.units)
                return {
                    "parsed_syllabus": parsed,
                    "workflow_trace": make_trace(
                        trace,
                        "parse_syllabus_node",
                        "Parsed Syllabus Structure",
                        f"Extracted {len(parsed.units)} units and {topic_count} topics via {parser_model}.",
                        chunk_count=topic_count,
                    ),
                }
        except Exception as exc:
            logger.warning("Gemini parser (%s) failed (%s); falling back to deterministic parser.", parser_model, exc)

    parsed = _deterministic_parse_syllabus(raw_text)
    topic_count = sum(len(u.topics) for u in parsed.units)
    return {
        "parsed_syllabus": parsed,
        "workflow_trace": make_trace(
            trace,
            "parse_syllabus_node",
            "Parsed Syllabus Structure",
            f"Extracted {len(parsed.units)} units and {topic_count} topics from syllabus text.",
            chunk_count=topic_count,
            status="fallback" if not os.getenv("GEMINI_API_KEY") else "completed",
        ),
    }


# ---------------------------------------------------------------------------
# Node 2: map_pyq_priority_node
# ---------------------------------------------------------------------------

_STOPWORDS = {
    "and", "the", "for", "with", "using", "from", "into", "vs", "of", "in", "to", "a", "an",
    "on", "by", "its", "their", "problem", "problems", "concept", "concepts", "algorithms",
    "algorithm", "handling", "routine", "structure", "structures", "model", "hardware",
    "process", "processes", "system", "systems", "time", "data", "type", "types", "management",
}


def _extract_keywords(topic: str) -> List[str]:
    tokens = re.findall(r"[a-zA-Z0-9]+", topic.lower())
    filtered = [t for t in tokens if len(t) >= 3 and t not in _STOPWORDS]
    return filtered or [t for t in tokens if len(t) >= 3]


def _extract_question_snippet(chunk_text: str, keywords: List[str]) -> str:
    blocks = re.split(r"(?=\n?Q\d+\s*\()", chunk_text)
    best_block = chunk_text
    best_hits = -1
    for blk in blocks:
        low = blk.lower()
        hits = sum(1 for kw in keywords if kw in low)
        if hits > best_hits:
            best_hits = hits
            best_block = blk.strip()
    snippet = re.sub(r"\s+", " ", best_block).strip()
    return snippet[:260] + ("..." if len(snippet) > 260 else "")


def map_pyq_priority_node(state: AgentState) -> Dict[str, Any]:
    session_id = state["session_id"]
    unchecked = state.get("unchecked_topics", [])
    unit_map = state.get("topic_unit_map", {})
    hours_remaining = float(state.get("hours_remaining", 8.0))
    learning_style: LearningStyle = state.get("learning_style", "Conceptual")
    trace = list(state.get("workflow_trace") or [])

    all_pyq_docs = ingestion_engine.get_session_documents(session_id=session_id, source="pyq", limit=300)
    numerical_indicators = (
        "calculate", "compute", "gantt", "waiting time", "need matrix", "emat",
        "hit ratio", "page fault", "cylinders", "seek", "banker", "fit",
    )

    scored: List[Dict[str, Any]] = []
    for topic in unchecked:
        keywords = _extract_keywords(topic)
        hits = ingestion_engine.search(session_id=session_id, query=topic, source="pyq", k=5)

        matched_files: set[str] = set()
        matched_snippets: List[MatchedPYQ] = []
        seen_snips: set[str] = set()
        semantic_scores: List[float] = []

        for doc, vec_score in hits:
            doc_low = doc.page_content.lower()
            kw_hits = sum(1 for kw in keywords if kw in doc_low)
            kw_ratio = kw_hits / max(len(keywords), 1)
            combined = 0.55 * float(max(0.0, min(vec_score, 1.0))) + 0.45 * kw_ratio
            if combined >= 0.30 or kw_hits >= max(1, len(keywords) // 2):
                fname = str(doc.metadata.get("paper_name", "PYQ.pdf"))
                matched_files.add(fname)
                semantic_scores.append(combined)
                snip = _extract_question_snippet(doc.page_content, keywords)
                if snip not in seen_snips and len(matched_snippets) < 3:
                    seen_snips.add(snip)
                    matched_snippets.append(
                        MatchedPYQ(
                            question_snippet=snip,
                            source_file=fname,
                            relevance_score=round(combined, 3),
                        )
                    )

        numerical_hits = 0
        for pdoc in all_pyq_docs:
            plow = pdoc.page_content.lower()
            kw_hits = sum(1 for kw in keywords if kw in plow)
            threshold = 1 if len(keywords) <= 2 else 2
            if kw_hits >= threshold:
                matched_files.add(str(pdoc.metadata.get("paper_name", "PYQ.pdf")))
                if any(ind in plow for ind in numerical_indicators):
                    numerical_hits += 1

        freq = len(matched_files)
        avg_rel = sum(semantic_scores) / len(semantic_scores) if semantic_scores else 0.18
        if freq == 0 and semantic_scores and max(semantic_scores) >= 0.35:
            freq = 1

        style_mult = 1.0
        if learning_style == "Numerical-Heavy" and numerical_hits > 0:
            style_mult = 1.25
        elif learning_style == "Crash Course":
            style_mult = 1.15 if freq >= 2 else 0.85

        composite = (freq * 1.4 + avg_rel * 2.2) * style_mult
        scored.append(
            {
                "topic": topic,
                "unit_title": unit_map.get(topic, "General Syllabus"),
                "pyq_frequency": freq,
                "relevance_score": round(min(0.99, avg_rel + freq * 0.12), 2),
                "composite": composite,
                "numerical_hits": numerical_hits,
                "matched_pyqs": matched_snippets,
            }
        )

    scored.sort(key=lambda x: (-x["composite"], -x["pyq_frequency"]))
    total_topics = len(scored)
    exponent = 1.35 if learning_style == "Crash Course" else 1.0
    weights = [max(0.25, item["composite"]) ** exponent for item in scored]
    weight_sum = sum(weights) or 1.0

    prioritized: List[PrioritizedTopic] = []
    allocated_sum = 0.0
    for idx, item in enumerate(scored):
        rank = idx + 1
        freq = item["pyq_frequency"]
        if freq >= 3 or (rank == 1 and freq >= 2):
            tier: PriorityTier = "Critical"
        elif freq == 2 or rank <= max(2, total_topics // 3):
            tier = "High"
        elif freq == 1 or rank <= max(3, (2 * total_topics) // 3):
            tier = "Medium"
        else:
            tier = "Low"

        if idx == total_topics - 1:
            alloc = round(max(0.2, hours_remaining - allocated_sum), 1)
        else:
            alloc = round(max(0.2, hours_remaining * (weights[idx] / weight_sum)), 1)
            allocated_sum += alloc

        rationale = (
            f"Matched across {freq} PYQ paper(s) "
            + ("with calculation-heavy numericals." if item["numerical_hits"] > 0 else "with recurring theory questions.")
            if freq > 0
            else "Lower historical recurrence; review after critical PYQ topics."
        )

        prioritized.append(
            PrioritizedTopic(
                topic=item["topic"],
                unit_title=item["unit_title"],
                priority_rank=rank,
                priority_tier=tier,
                pyq_frequency=freq,
                relevance_score=item["relevance_score"],
                allocated_hours=alloc,
                rationale=rationale,
                matched_pyqs=item["matched_pyqs"],
            )
        )

    top_names = ", ".join(p.topic for p in prioritized[:3])
    strategy_note = {
        "Crash Course": f"Focused rapid-revision split prioritizing top recurring PYQ topics ({top_names}) in {hours_remaining}h.",
        "Conceptual": f"Balanced conceptual plan across {total_topics} unchecked topics led by {top_names}.",
        "Numerical-Heavy": f"Problem-solving weighted plan boosting numerical PYQ topics ({top_names}).",
    }[learning_style]

    return {
        "prioritized_topics": prioritized,
        "strategy_note": strategy_note,
        "workflow_trace": make_trace(
            trace,
            "map_pyq_priority_node",
            "Mapped PYQ Weightage & Budgeted Time",
            f"Queried Qdrant (source=='pyq', {len(all_pyq_docs)} chunks) to rank {total_topics} topics across {hours_remaining}h.",
            chunk_count=len(all_pyq_docs),
        ),
    }


# ---------------------------------------------------------------------------
# Node 3: retrieve_and_rerank_node
# ---------------------------------------------------------------------------


def retrieve_and_rerank_node(state: AgentState) -> Dict[str, Any]:
    session_id = state["session_id"]
    topic = state["topic"]
    trace = list(state.get("workflow_trace") or [])
    keywords = _extract_keywords(topic)

    raw_syl = ingestion_engine.search(session_id=session_id, query=topic, source="syllabus", k=6)
    raw_pyq = ingestion_engine.search(session_id=session_id, query=topic, source="pyq", k=6)

    def rerank(items: List[tuple[Document, float]], top_k: int = 4) -> List[tuple[Document, float]]:
        scored_items: List[tuple[Document, float]] = []
        for doc, vec_score in items:
            low = doc.page_content.lower()
            kw_hits = sum(1 for kw in keywords if kw in low)
            kw_boost = kw_hits / max(len(keywords), 1)
            combined = 0.6 * float(max(0.0, min(vec_score, 1.0))) + 0.4 * kw_boost
            scored_items.append((doc, combined))
        scored_items.sort(key=lambda x: -x[1])
        return scored_items[:top_k]

    syl_top = rerank(raw_syl, top_k=4)
    pyq_top = rerank(raw_pyq, top_k=4)

    sources: List[RetrievedSource] = []
    for doc, score in syl_top:
        sources.append(
            RetrievedSource(
                source="syllabus",
                paper_name=str(doc.metadata.get("paper_name", "Syllabus.pdf")),
                excerpt=re.sub(r"\s+", " ", doc.page_content).strip()[:320],
                score=round(score, 3),
                chunk_index=int(doc.metadata.get("chunk_index", 0)),
            )
        )
    for doc, score in pyq_top:
        sources.append(
            RetrievedSource(
                source="pyq",
                paper_name=str(doc.metadata.get("paper_name", "PYQ.pdf")),
                excerpt=re.sub(r"\s+", " ", doc.page_content).strip()[:320],
                score=round(score, 3),
                chunk_index=int(doc.metadata.get("chunk_index", 0)),
            )
        )

    return {
        "syllabus_chunks": [d for d, _ in syl_top],
        "pyq_chunks": [d for d, _ in pyq_top],
        "retrieved_sources": sources,
        "workflow_trace": make_trace(
            trace,
            "retrieve_and_rerank_node",
            "Retrieved & Reranked Grounded Context",
            f"Retrieved {len(syl_top)} syllabus chunks + {len(pyq_top)} PYQ chunks from Qdrant for '{topic}'.",
            chunk_count=len(syl_top) + len(pyq_top),
        ),
    }


# ---------------------------------------------------------------------------
# Node 4: generate_study_pack_node
# ---------------------------------------------------------------------------


def _format_context(syl_docs: List[Document], pyq_docs: List[Document]) -> str:
    parts = ["=== SYLLABUS CONTEXT (GROUND TRUTH BOUNDARY) ==="]
    for i, d in enumerate(syl_docs, 1):
        parts.append(f"[Syllabus #{i} | {d.metadata.get('paper_name', 'Syllabus')}]\n{d.page_content}")
    parts.append("\n=== PREVIOUS YEAR QUESTION (PYQ) CONTEXT ===")
    for i, d in enumerate(pyq_docs, 1):
        parts.append(f"[PYQ #{i} | {d.metadata.get('paper_name', 'PYQ')}]\n{d.page_content}")
    return "\n\n".join(parts)


def _fallback_pack(
    topic: str,
    learning_style: LearningStyle,
    hours_remaining: float,
    syl_docs: List[Document],
    pyq_docs: List[Document],
) -> Dict[str, Any]:
    t_low = topic.lower()
    syl_text = "\n".join(d.page_content for d in syl_docs)
    pyq_text = "\n".join(d.page_content for d in pyq_docs)

    if any(k in t_low for k in ("scheduling", "fcfs", "sjf", "srtf", "round robin", "cpu")):
        summary = (
            f"### {topic} ({learning_style} Mode — {hours_remaining}h Budget)\n\n"
            "**Strictly Syllabus-Grounded Summary:**\n"
            "- **Metrics:** Turnaround Time $TAT = CT - AT$, Waiting Time $WT = TAT - BT$, and Response Time.\n"
            "- **FCFS:** Non-preemptive; exhibits the **Convoy Effect** when short jobs queue behind a long CPU-bound process.\n"
            "- **SJF / SRTF:** Minimizes average waiting time; SRTF preempts on arrival when remaining burst is shorter.\n"
            "- **Round Robin:** Preemptive with time quantum $q$; tiny $q$ increases context-switch overhead while huge $q$ reduces to FCFS.\n"
            "- **Priority + Aging:** Aging prevents starvation of low-priority processes."
        )
        examples = [
            WorkedExample(
                title="PYQ 2025: SRTF Average Waiting & Turnaround Time",
                problem_statement="P1(AT=0, BT=8), P2(AT=1, BT=4), P3(AT=2, BT=9), P4(AT=3, BT=5). Compute Avg WT and Avg TAT under Preemptive SJF (SRTF).",
                given_data=["P1(0,8)", "P2(1,4)", "P3(2,9)", "P4(3,5)"],
                formulae_used=["TAT = CT - AT", "WT = TAT - BT"],
                steps=[
                    "t=0->1: P1 runs (rem=7). At t=1, P2(BT=4) < 7 so P2 preempts P1.",
                    "t=1->5: P2 finishes at CT=5. Ready queue has P1(7), P3(9), P4(5).",
                    "t=5->10: P4(5) is shortest -> finishes at CT=10.",
                    "t=10->17: P1(7) finishes at CT=17; t=17->26: P3(9) finishes at CT=26.",
                    "WT: P1=9, P2=0, P3=15, P4=2 -> Avg WT = 26/4 = 6.5 ms.",
                ],
                final_answer="Average WT = 6.5 ms | Average TAT = 13.0 ms",
                exam_tip="Check remaining burst times at every new process arrival instant.",
            )
        ]
        cheat = (
            f"# 1-Page Cheat Sheet: {topic}\n\n"
            "## Key Equations\n- `TAT = CT - AT`\n- `WT = TAT - BT`\n\n"
            "## Quick Comparison\n"
            "| Algorithm | Preemptive | Optimal Avg WT | Watch Out |\n|---|---|---|---|\n"
            "| FCFS | No | No | Convoy Effect |\n| SRTF | Yes | Yes | Starvation |\n| Round Robin | Yes (q) | No (best RT) | Context Switch Overhead |\n| Priority | Optional | No | Fix Starvation with Aging |"
        )
        quiz = [
            QuizQuestion(id=1, question="Which algorithm minimizes average waiting time?", options=["FCFS", "Round Robin", "SRTF", "Multilevel Queue"], correct_index=2, explanation="SRTF (preemptive SJF) is optimal for minimizing average waiting time.", pyq_tag="PYQ 2025"),
            QuizQuestion(id=2, question="Convoy Effect occurs primarily in:", options=["FCFS", "SRTF", "Round Robin", "Aging"], correct_index=0, explanation="Short processes wait behind one long CPU-bound process in FCFS.", pyq_tag="PYQ 2023/2025"),
            QuizQuestion(id=3, question="Starvation in Priority Scheduling is solved by:", options=["Compaction", "Aging", "Swapping", "Thrashing"], correct_index=1, explanation="Aging gradually raises priority of waiting processes.", pyq_tag="PYQ 2024"),
            QuizQuestion(id=4, question="As Round Robin quantum q -> infinity, it behaves like:", options=["SJF", "SRTF", "FCFS", "Priority"], correct_index=2, explanation="Processes finish within their first slice in arrival order.", pyq_tag="PYQ 2023"),
            QuizQuestion(id=5, question="If AT=2, BT=6, CT=13, what is Waiting Time?", options=["5 ms", "7 ms", "11 ms", "4 ms"], correct_index=0, explanation="TAT = 13 - 2 = 11 ms; WT = 11 - 6 = 5 ms.", pyq_tag="PYQ 2024"),
        ]
    elif any(k in t_low for k in ("banker", "deadlock", "coffman", "avoidance", "prevention")):
        summary = (
            f"### {topic} ({learning_style} Mode — {hours_remaining}h Budget)\n\n"
            "**Strictly Syllabus-Grounded Summary:**\n"
            "- **4 Coffman Conditions:** Mutual Exclusion, Hold and Wait, No Preemption, Circular Wait.\n"
            "- **Banker's Algorithm:** Computes `Need[i] = Max[i] - Allocation[i]` and runs the Safety Algorithm (`Need[i] <= Work`).\n"
            "- **Resource-Request Rule:** Check `Request[i] <= Need[i]` and `Request[i] <= Available` before tentative allocation."
        )
        examples = [
            WorkedExample(
                title="PYQ 2025: Banker's Safety & Request Verification",
                problem_statement="Resources A=10, B=5, C=7; Sum(Alloc)=(7,2,5). Determine Safe Sequence and if P1 request (1,0,2) can be granted.",
                given_data=["Total=(10,5,7)", "Available=(3,3,2)", "P1 Need=(1,2,2), P3 Need=(0,1,1), P4 Need=(4,3,1)"],
                formulae_used=["Need[i] = Max[i] - Allocation[i]", "Available = Total - Sum(Allocation)"],
                steps=[
                    "Available = (10,5,7) - (7,2,5) = (3,3,2).",
                    "P1 Need(1,2,2) <= (3,3,2) -> Work becomes (5,3,2).",
                    "P3(0,1,1) -> Work=(7,4,3); P4(4,3,1) -> Work=(7,4,5); then P0 and P2 finish.",
                    "P1 request (1,0,2) <= Need(1,2,2) and <= Available(3,3,2); safe sequence <P1, P3, P4, P0, P2> still holds.",
                ],
                final_answer="Safe Sequence: <P1, P3, P4, P0, P2>; Request (1,0,2) GRANTED.",
                exam_tip="Never skip checking Request <= Need before checking Available.",
            )
        ]
        cheat = (
            f"# 1-Page Cheat Sheet: {topic}\n\n"
            "## Coffman Conditions\n1. Mutual Exclusion 2. Hold & Wait 3. No Preemption 4. Circular Wait\n\n"
            "## Banker's Formulas\n- `Need = Max - Allocation`\n- `Available = Total - Sum(Allocation)`\n- Safe iff all processes finish with `Need[i] <= Work`."
        )
        quiz = [
            QuizQuestion(id=1, question="Which is NOT one of the 4 Coffman deadlock conditions?", options=["Mutual Exclusion", "Hold and Wait", "Circular Wait", "Starvation"], correct_index=3, explanation="Starvation is indefinite postponement, not a Coffman deadlock condition.", pyq_tag="PYQ 2024"),
            QuizQuestion(id=2, question="How is the Need matrix defined in Banker's Algorithm?", options=["Allocation - Max", "Max - Allocation", "Available + Max", "Total - Need"], correct_index=1, explanation="Need[i] = Max[i] - Allocation[i].", pyq_tag="PYQ 2025"),
            QuizQuestion(id=3, question="Ordering all resource types linearly breaks which condition?", options=["Mutual Exclusion", "No Preemption", "Circular Wait", "Hold and Wait"], correct_index=2, explanation="Strict resource ordering makes circular wait cycles impossible.", pyq_tag="PYQ 2024"),
            QuizQuestion(id=4, question="A cycle in a RAG guarantees deadlock when:", options=["Each resource has a single instance", "Resources have multiple instances", "Banker's Algorithm runs", "Aging is disabled"], correct_index=0, explanation="With single instances, a cycle is both necessary and sufficient for deadlock.", pyq_tag="PYQ 2023"),
            QuizQuestion(id=5, question="Before tentative allocation in Resource-Request, what must hold?", options=["Request[i] > Need[i]", "Request[i] <= Need[i] and Request[i] <= Available", "Work == 0", "Finish[i] == True"], correct_index=1, explanation="Requests must stay within declared max need and currently available resources.", pyq_tag="PYQ 2025"),
        ]
    elif any(k in t_low for k in ("paging", "tlb", "emat", "memory", "fragmentation", "page replacement", "belady", "lru", "fifo", "demand")):
        summary = (
            f"### {topic} ({learning_style} Mode — {hours_remaining}h Budget)\n\n"
            "**Strictly Syllabus-Grounded Summary:**\n"
            "- **TLB EMAT:** $\\text{EMAT} = h(t_{\\text{TLB}} + t_{\\text{mem}}) + (1 - h)(t_{\\text{TLB}} + 2t_{\\text{mem}})$.\n"
            "- **Demand Paging EAT:** $(1 - p) \\cdot ma + p \\cdot \\text{PageFaultServiceTime}$.\n"
            "- **Page Replacement:** Optimal (OPT) is benchmark minimum; LRU is a stack algorithm; FIFO can exhibit **Belady's Anomaly**."
        )
        examples = [
            WorkedExample(
                title="PYQ 2025: TLB EMAT & Page Table Size",
                problem_statement="TLB = 15 ns, Memory = 120 ns, Hit ratio = 90%. Compute EMAT and Page Table size (32-bit VA, 4 KB page, 4 B PTE).",
                given_data=["t_TLB=15 ns", "t_mem=120 ns", "h=0.90", "Page=4 KB = 2^12 B"],
                formulae_used=["EMAT = h*(t_TLB+t_mem) + (1-h)*(t_TLB+2*t_mem)", "Entries = 2^(32-12)"],
                steps=[
                    "Hit time = 15 + 120 = 135 ns; Miss time = 15 + 240 = 255 ns.",
                    "EMAT = 0.90*135 + 0.10*255 = 121.5 + 25.5 = 147 ns.",
                    "Page table entries = 2^20; Size = 2^20 * 4 bytes = 4 MB.",
                ],
                final_answer="EMAT = 147 ns | Page Table Size = 4 MB",
                exam_tip="Always include TLB lookup time on misses too.",
            )
        ]
        cheat = (
            f"# 1-Page Cheat Sheet: {topic}\n\n"
            "- **EMAT:** `h*(t_TLB + t_mem) + (1-h)*(t_TLB + 2*t_mem)`\n"
            "- **EAT:** `(1-p)*ma + p*PF_service_time`\n"
            "- **Belady's Anomaly:** Occurs in FIFO; never in LRU or Optimal."
        )
        quiz = [
            QuizQuestion(id=1, question="With TLB=20 ns, Memory=100 ns, h=0.80, EMAT is:", options=["120 ns", "140 ns", "160 ns", "180 ns"], correct_index=1, explanation="0.8*(120) + 0.2*(220) = 96 + 44 = 140 ns.", pyq_tag="PYQ 2024"),
            QuizQuestion(id=2, question="Which algorithm can exhibit Belady's Anomaly?", options=["Optimal", "LRU", "FIFO", "LFU Stack"], correct_index=2, explanation="FIFO is not a stack algorithm, so more frames can yield more faults.", pyq_tag="PYQ 2024"),
            QuizQuestion(id=3, question="Offset bits for a 4 KB page size:", options=["10", "12", "16", "20"], correct_index=1, explanation="4 KB = 2^12 bytes -> 12 offset bits.", pyq_tag="PYQ 2025"),
            QuizQuestion(id=4, question="Paging eliminates which fragmentation?", options=["Internal", "External", "Thrashing", "Page faults"], correct_index=1, explanation="Non-contiguous frame allocation removes external fragmentation.", pyq_tag="PYQ 2023"),
            QuizQuestion(id=5, question="Thrashing happens when:", options=["CPU is 100% busy on compute", "System spends more time paging than executing", "TLB hit is 100%", "Disk seek is zero"], correct_index=1, explanation="Insufficient frames for working sets cause constant page faults.", pyq_tag="PYQ 2024"),
        ]
    else:
        syl_ex = re.sub(r"\s+", " ", syl_text)[:600] or "Refer to syllabus chunks."
        pyq_ex = re.sub(r"\s+", " ", pyq_text)[:500] or "Refer to PYQ chunks."
        summary = (
            f"### {topic} ({learning_style} Mode — {hours_remaining}h Budget)\n\n"
            f"**Grounded Syllabus Context:** {syl_ex}\n\n"
            f"**Grounded PYQ Context:** {pyq_ex}"
        )
        examples = [
            WorkedExample(
                title=f"Grounded Walkthrough: {topic}",
                problem_statement=pyq_ex[:240],
                given_data=["Extracted from retrieved syllabus & PYQ chunks"],
                formulae_used=["Derived directly from retrieved syllabus scope"],
                steps=["Identify given exam values.", "Apply prescribed syllabus formula/method.", "Verify units & edge cases."],
                final_answer="Cross-check final value against retrieved PYQ constraints.",
                exam_tip="Show every substitution step for partial credit.",
            )
        ]
        cheat = f"# 1-Page Cheat Sheet: {topic}\n\n## Syllabus\n{syl_ex[:300]}\n\n## PYQ Focus\n{pyq_ex[:300]}"
        quiz = [
            QuizQuestion(
                id=i,
                question=f"[{topic}] What ensures syllabus-grounded accuracy for '{learning_style}' prep?",
                options=[
                    "Applying exact retrieved syllabus definitions and PYQ patterns",
                    "Ignoring syllabus scope boundaries",
                    "Skipping units and boundary conditions",
                    "Omitting intermediate steps",
                ],
                correct_index=0,
                explanation="Staying strictly inside the prescribed syllabus and PYQ rubric ensures full exam alignment.",
                pyq_tag="Grounded Check",
            )
            for i in range(1, 6)
        ]

    return {"summary": summary, "worked_examples": examples, "cheat_sheet_markdown": cheat, "quiz": quiz}


def generate_study_pack_node(state: AgentState) -> Dict[str, Any]:
    topic = state["topic"]
    hours = float(state.get("hours_remaining", 6.0))
    style: LearningStyle = state.get("learning_style", "Conceptual")
    syl_docs = state.get("syllabus_chunks", [])
    pyq_docs = state.get("pyq_chunks", [])
    trace = list(state.get("workflow_trace") or [])
    context = _format_context(syl_docs, pyq_docs)

    gen_model = os.getenv("GEMINI_GENERATOR_MODEL", "gemini-3.5-flash-lite")
    if gen_model == "gemini-3.8-flash":
        gen_model = "gemini-3.5-flash-lite"
    parser_model = os.getenv("GEMINI_PARSER_MODEL", "gemini-3.5-flash-lite")

    summary = ""
    examples: List[WorkedExample] = []
    cheat_sheet = ""
    gen_mode = "grounded-local-fallback"

    candidates = [(gen_model, 25)]
    if parser_model != gen_model:
        candidates.append((parser_model, 25))

    for candidate_model, req_timeout in candidates:
        llm = _get_gemini_llm(candidate_model, temperature=0.0, timeout=req_timeout)
        if llm is None or not (syl_docs or pyq_docs):
            continue
        try:
            structured_notes = llm.with_structured_output(
                GeneratedNotesPack, method="json_schema"
            )
            parsed_pack: GeneratedNotesPack = structured_notes.invoke(
                [
                    SystemMessage(
                        content=(
                            "You are ExamPulse AI, a strictly syllabus-grounded engineering tutor. "
                            "Use ONLY the retrieved Syllabus and PYQ context below. Do NOT hallucinate "
                            "external topics or concepts outside the provided context."
                        )
                    ),
                    HumanMessage(
                        content=(
                            f"Topic: {topic}\nHours Remaining: {hours}\nLearning Style: {style}\n\n"
                            "Tailor depth:\n"
                            "- Crash Course: crisp bullet points, formulas first, high-yield exam triggers.\n"
                            "- Conceptual: clear intuition, definitions, comparisons.\n"
                            "- Numerical-Heavy: formulas, units, edge cases, and detailed step-by-step solved numericals.\n\n"
                            f"{context}"
                        )
                    ),
                ]
            )
            if parsed_pack and parsed_pack.summary and parsed_pack.worked_examples and parsed_pack.cheat_sheet_markdown:
                summary = parsed_pack.summary
                examples = parsed_pack.worked_examples
                cheat_sheet = parsed_pack.cheat_sheet_markdown
                gen_mode = candidate_model
                break
        except Exception as exc:
            logger.warning("Generator %s failed (%s)", candidate_model, exc)

    if not summary:
        fb = _fallback_pack(topic, style, hours, syl_docs, pyq_docs)
        summary = fb["summary"]
        examples = fb["worked_examples"]
        cheat_sheet = fb["cheat_sheet_markdown"]

    # Quiz generation: primary gemini-3.5-flash-lite with schema-enforced structured output
    quiz: List[QuizQuestion] = []
    quiz_attempts = []
    gemini_quiz_llm = _get_gemini_llm(gen_model, temperature=0.0, timeout=25)
    if gemini_quiz_llm is not None:
        quiz_attempts.append((gemini_quiz_llm, gen_model, "json_schema"))
    groq_llm = _get_groq_llm(temperature=0.0, timeout=12)
    if groq_llm is not None:
        quiz_attempts.append((groq_llm, f"groq/{os.getenv('GROQ_MODEL', 'llama-3.3-70b-versatile')}", None))

    for quiz_llm, quiz_provider, out_method in quiz_attempts:
        if not (syl_docs or pyq_docs):
            break
        try:
            structured_quiz = (
                quiz_llm.with_structured_output(GeneratedQuizPack, method=out_method)
                if out_method
                else quiz_llm.with_structured_output(GeneratedQuizPack)
            )
            q_pack: GeneratedQuizPack = structured_quiz.invoke(
                [
                    SystemMessage(
                        content="Generate 5 PYQ-style MCQs (with integer id 1..5, question, 4 options, 0-based correct_index, and brief explanation) grounded ONLY in the provided context."
                    ),
                    HumanMessage(content=f"Topic: {topic}\n\n{context}"),
                ]
            )
            if q_pack and len(q_pack.quiz) >= 3:
                for q_i, q_item in enumerate(q_pack.quiz[:5], start=1):
                    q_item.id = q_i
                quiz = q_pack.quiz[:5]
                if gen_mode == "grounded-local-fallback":
                    gen_mode = quiz_provider
                elif quiz_provider != gen_mode:
                    gen_mode = f"{gen_mode} + quiz:{quiz_provider}"
                break
        except Exception as exc:
            logger.warning("Quiz generator (%s) failed (%s)", quiz_provider, exc)

    if not quiz:
        quiz = _fallback_pack(topic, style, hours, syl_docs, pyq_docs)["quiz"]

    return {
        "summary": summary,
        "worked_examples": examples,
        "cheat_sheet_markdown": cheat_sheet,
        "quiz": quiz,
        "generation_mode": gen_mode,
        "workflow_trace": make_trace(
            trace,
            "generate_study_pack_node",
            "Generated Grounded Study Pack",
            f"Compiled {style} notes, {len(examples)} worked example(s), {len(quiz)} PYQ MCQs, and 1-page cheat sheet ({gen_mode}).",
            chunk_count=len(syl_docs) + len(pyq_docs),
            status="fallback" if gen_mode == "grounded-local-fallback" else "completed",
        ),
    }


# ---------------------------------------------------------------------------
# Compiled LangGraph StateGraph
# ---------------------------------------------------------------------------


def _route_action(state: AgentState) -> str:
    action = state.get("action", "generate_study_pack")
    if action == "parse_syllabus":
        return "parse_syllabus_node"
    if action == "prioritize":
        return "map_pyq_priority_node"
    return "retrieve_and_rerank_node"


_builder = StateGraph(AgentState)
_builder.add_node("parse_syllabus_node", parse_syllabus_node)
_builder.add_node("map_pyq_priority_node", map_pyq_priority_node)
_builder.add_node("retrieve_and_rerank_node", retrieve_and_rerank_node)
_builder.add_node("generate_study_pack_node", generate_study_pack_node)

_builder.add_conditional_edges(
    START,
    _route_action,
    {
        "parse_syllabus_node": "parse_syllabus_node",
        "map_pyq_priority_node": "map_pyq_priority_node",
        "retrieve_and_rerank_node": "retrieve_and_rerank_node",
    },
)
_builder.add_edge("parse_syllabus_node", END)
_builder.add_edge("map_pyq_priority_node", END)
_builder.add_edge("retrieve_and_rerank_node", "generate_study_pack_node")
_builder.add_edge("generate_study_pack_node", END)

agentic_rag_graph = _builder.compile()
