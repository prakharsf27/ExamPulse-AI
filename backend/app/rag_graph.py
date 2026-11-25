from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional, TypedDict

from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph

from app.config import settings
from app.models import (
    GroundedSource,
    LearningStyle,
    MatchedPYQ,
    ParsedSyllabus,
    PrioritizedTopic,
    PriorityTier,
    QuizQuestion,
    StudyPackResponse,
    SyllabusUnit,
    WorkedExample,
)
from app.qdrant_store import qdrant_store

logger = logging.getLogger(__name__)


def _get_gemini_llm(temperature: float = 0.0):
    if not settings.has_gemini:
        return None
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=settings.gemini_model,
            google_api_key=settings.gemini_api_key,
            temperature=temperature,
        )
    except Exception as exc:
        logger.warning("Failed to initialize Gemini LLM: %s", exc)
        return None


def _get_groq_llm(temperature: float = 0.0):
    if not settings.has_groq:
        return None
    try:
        from langchain_groq import ChatGroq

        return ChatGroq(
            model=settings.groq_model,
            groq_api_key=settings.groq_api_key,
            temperature=temperature,
        )
    except Exception as exc:
        logger.warning("Failed to initialize Groq LLM: %s", exc)
        return None


def _strip_json_fences(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


# ---------------------------------------------------------------------------
# 1. Syllabus Parser LangGraph
# ---------------------------------------------------------------------------


class SyllabusParserState(TypedDict):
    raw_text: str
    parsed: Optional[ParsedSyllabus]


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
    current_unit_num = ""
    current_unit_title = ""
    current_topics: List[str] = []

    unit_header_re = re.compile(
        r"^(?:UNIT|MODULE|CHAPTER)\s*[-–:]?\s*([IVX\d]+)\s*[-–:]?\s*(.+)$",
        re.IGNORECASE,
    )

    def flush_unit() -> None:
        nonlocal current_unit_num, current_unit_title, current_topics
        if current_unit_title and current_topics:
            deduped = list(dict.fromkeys(current_topics))
            units.append(
                SyllabusUnit(
                    unit_number=current_unit_num or f"Unit {len(units) + 1}",
                    unit_title=current_unit_title,
                    topics=deduped[:10],
                )
            )
        current_topics = []

    for ln in lines:
        if ln.startswith("[Page "):
            continue
        m = unit_header_re.match(ln)
        if m:
            flush_unit()
            current_unit_num = f"Unit {m.group(1).strip()}"
            current_unit_title = m.group(2).strip(" :-")
            continue

        if current_unit_title:
            cleaned = re.sub(r"^[-*•\d.)]+\s*", "", ln).strip()
            if len(cleaned) < 4:
                continue
            current_topics.append(cleaned[:95].rstrip("."))

    flush_unit()

    if not units:
        units = [
            SyllabusUnit(
                unit_number="Unit 1",
                unit_title="Core Syllabus Topics",
                topics=[
                    ln[:80]
                    for ln in lines
                    if not ln.startswith("[Page ") and len(ln) > 8
                ][:8]
                or ["Core Fundamentals"],
            )
        ]

    return ParsedSyllabus(course_title=course_title, units=units)


def _syllabus_parser_node(state: SyllabusParserState) -> Dict[str, Any]:
    raw_text = state["raw_text"]
    llm = _get_gemini_llm(temperature=0.0)
    if llm is not None:
        try:
            structured_llm = llm.with_structured_output(ParsedSyllabus)
            prompt = (
                "You are an academic syllabus parser. Extract a clean, structured syllabus "
                "from the provided text. Group topics under their Units/Modules. Keep each topic "
                "concise (3-8 words), exam-ready, and faithful ONLY to the provided syllabus text. "
                "Do not invent topics not present in the text.\n\n"
                f"SYLLABUS TEXT:\n{raw_text[:18000]}"
            )
            parsed = structured_llm.invoke(prompt)
            if parsed and parsed.units:
                return {"parsed": parsed}
        except Exception as exc:
            logger.warning("LLM syllabus parsing failed (%s); using deterministic parser.", exc)

    return {"parsed": _deterministic_parse_syllabus(raw_text)}


_syllabus_builder = StateGraph(SyllabusParserState)
_syllabus_builder.add_node("parse_syllabus", _syllabus_parser_node)
_syllabus_builder.add_edge(START, "parse_syllabus")
_syllabus_builder.add_edge("parse_syllabus", END)
syllabus_parser_graph = _syllabus_builder.compile()


# ---------------------------------------------------------------------------
# 2. PYQ Weightage Mapper & Prioritizer LangGraph
# ---------------------------------------------------------------------------


class PrioritizeState(TypedDict):
    session_id: str
    unchecked_topics: List[str]
    topic_unit_map: Dict[str, str]
    hours_remaining: float
    learning_style: LearningStyle
    raw_scores: List[Dict[str, Any]]
    prioritized_topics: List[PrioritizedTopic]
    strategy_note: str


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


def _pyq_weightage_mapper_node(state: PrioritizeState) -> Dict[str, Any]:
    session_id = state["session_id"]
    unchecked = state["unchecked_topics"]
    unit_map = state["topic_unit_map"]
    learning_style = state["learning_style"]

    all_pyq_docs = qdrant_store.get_session_documents(session_id=session_id, source="pyq", limit=300)
    raw_scores: List[Dict[str, Any]] = []

    numerical_indicators = ("calculate", "compute", "gantt", "waiting time", "need matrix", "emat", "hit ratio", "page fault", "cylinders", "seek", "banker", "fit")

    for topic in unchecked:
        keywords = _extract_keywords(topic)
        hits = qdrant_store.search(session_id=session_id, query=topic, source="pyq", k=6)

        matched_files: set[str] = set()
        matched_snippets: List[MatchedPYQ] = []
        seen_snips: set[str] = set()
        semantic_scores: List[float] = []

        # Combine vector search results with direct PYQ paper cross-check for exact frequency
        for doc, vec_score in hits:
            doc_low = doc.page_content.lower()
            kw_hits = sum(1 for kw in keywords if kw in doc_low)
            kw_ratio = kw_hits / max(len(keywords), 1)
            combined = 0.55 * float(max(0.0, min(vec_score, 1.0))) + 0.45 * kw_ratio

            if combined >= 0.30 or kw_hits >= max(1, len(keywords) // 2):
                fname = str(doc.metadata.get("filename", "PYQ.pdf"))
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

        # Also count distinct PYQ files mentioning the topic's core keywords
        numerical_hits = 0
        for pdoc in all_pyq_docs:
            plow = pdoc.page_content.lower()
            kw_hits = sum(1 for kw in keywords if kw in plow)
            threshold = 1 if len(keywords) <= 2 else 2
            if kw_hits >= threshold:
                fname = str(pdoc.metadata.get("filename", "PYQ.pdf"))
                matched_files.add(fname)
                if any(ind in plow for ind in numerical_indicators):
                    numerical_hits += 1

        freq = len(matched_files)
        avg_rel = sum(semantic_scores) / len(semantic_scores) if semantic_scores else 0.18
        if freq == 0 and semantic_scores and max(semantic_scores) >= 0.35:
            freq = 1

        style_multiplier = 1.0
        if learning_style == "Numerical-Heavy" and numerical_hits > 0:
            style_multiplier = 1.25
        elif learning_style == "Crash Course":
            style_multiplier = 1.15 if freq >= 2 else 0.85

        composite = (freq * 1.4 + avg_rel * 2.2) * style_multiplier

        raw_scores.append(
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

    return {"raw_scores": raw_scores}


def _allocate_hours_node(state: PrioritizeState) -> Dict[str, Any]:
    raw_scores = sorted(state["raw_scores"], key=lambda x: (-x["composite"], -x["pyq_frequency"]))
    hours_remaining = state["hours_remaining"]
    learning_style = state["learning_style"]

    total_topics = len(raw_scores)
    # In Crash Course with tight time, allocate slightly sharper weights to top topics
    exponent = 1.35 if learning_style == "Crash Course" else 1.0
    weights = [max(0.25, item["composite"]) ** exponent for item in raw_scores]
    weight_sum = sum(weights) or 1.0

    prioritized: List[PrioritizedTopic] = []
    allocated_sum = 0.0

    for idx, item in enumerate(raw_scores):
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

        if freq > 0:
            rationale = (
                f"Appeared across {freq} past exam paper(s) "
                + ("with calculation-heavy numericals." if item["numerical_hits"] > 0 else "with recurring conceptual questions.")
            )
        else:
            rationale = "Low direct PYQ recurrence; keep as quick revision after high-yield topics."

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
    style_desc = {
        "Crash Course": f"Focused rapid-revision split prioritizing top recurring topics ({top_names}) within your {hours_remaining}h window.",
        "Conceptual": f"Balanced conceptual mastery plan across {total_topics} remaining topics led by {top_names}.",
        "Numerical-Heavy": f"Problem-solving weighted plan boosting calculation-dense PYQ topics ({top_names}).",
    }[learning_style]

    return {"prioritized_topics": prioritized, "strategy_note": style_desc}


_prio_builder = StateGraph(PrioritizeState)
_prio_builder.add_node("map_pyq_weightage", _pyq_weightage_mapper_node)
_prio_builder.add_node("allocate_study_hours", _allocate_hours_node)
_prio_builder.add_edge(START, "map_pyq_weightage")
_prio_builder.add_edge("map_pyq_weightage", "allocate_study_hours")
_prio_builder.add_edge("allocate_study_hours", END)
prioritize_graph = _prio_builder.compile()


# ---------------------------------------------------------------------------
# 3. Grounded Content Generator LangGraph
# ---------------------------------------------------------------------------


class StudyPackState(TypedDict):
    session_id: str
    topic: str
    hours_remaining: float
    learning_style: LearningStyle
    syllabus_chunks: List[Document]
    pyq_chunks: List[Document]
    grounded_sources: List[GroundedSource]
    summary: str
    worked_examples: List[WorkedExample]
    cheat_sheet_markdown: str
    quiz: List[QuizQuestion]
    generation_mode: str


def _retrieve_context_node(state: StudyPackState) -> Dict[str, Any]:
    session_id = state["session_id"]
    topic = state["topic"]

    syl_hits = qdrant_store.search(session_id=session_id, query=topic, source="syllabus", k=4)
    pyq_hits = qdrant_store.search(session_id=session_id, query=topic, source="pyq", k=5)

    syl_docs = [d for d, _ in syl_hits]
    pyq_docs = [d for d, _ in pyq_hits]

    sources: List[GroundedSource] = []
    for d, s in syl_hits[:3]:
        sources.append(
            GroundedSource(
                source="syllabus",
                filename=str(d.metadata.get("filename", "Syllabus.pdf")),
                excerpt=re.sub(r"\s+", " ", d.page_content)[:200] + "...",
                score=round(float(s), 3),
            )
        )
    for d, s in pyq_hits[:4]:
        sources.append(
            GroundedSource(
                source="pyq",
                filename=str(d.metadata.get("filename", "PYQ.pdf")),
                excerpt=re.sub(r"\s+", " ", d.page_content)[:200] + "...",
                score=round(float(s), 3),
            )
        )

    return {
        "syllabus_chunks": syl_docs,
        "pyq_chunks": pyq_docs,
        "grounded_sources": sources,
    }


def _format_context_blocks(syl_docs: List[Document], pyq_docs: List[Document]) -> str:
    parts = ["=== RETRIEVED SYLLABUS CONTEXT ==="]
    for i, d in enumerate(syl_docs, 1):
        parts.append(f"[Syllabus #{i} | {d.metadata.get('filename', 'Syllabus')}]\n{d.page_content}")
    parts.append("\n=== RETRIEVED PREVIOUS YEAR QUESTION (PYQ) CONTEXT ===")
    for i, d in enumerate(pyq_docs, 1):
        parts.append(f"[PYQ #{i} | {d.metadata.get('filename', 'PYQ')}]\n{d.page_content}")
    return "\n\n".join(parts)


def _fallback_study_pack_content(
    topic: str,
    learning_style: LearningStyle,
    hours_remaining: float,
    syl_docs: List[Document],
    pyq_docs: List[Document],
) -> Dict[str, Any]:
    """Deterministic, strictly context-grounded fallback when no LLM API key is configured."""
    t_low = topic.lower()
    syl_text = "\n".join(d.page_content for d in syl_docs)
    pyq_text = "\n".join(d.page_content for d in pyq_docs)

    if any(k in t_low for k in ("scheduling", "fcfs", "sjf", "srtf", "round robin", "cpu")):
        summary = (
            f"### {topic} ({learning_style} Mode — {hours_remaining}h Window)\n\n"
            "**Syllabus Grounding:** Focuses on scheduling metrics—Turnaround Time ($TAT = CT - AT$), "
            "Waiting Time ($WT = TAT - BT$), Response Time, Throughput—and comparing FCFS, SJF, SRTF, Priority (with Aging), and Round Robin.\n\n"
            "- **FCFS:** Non-preemptive; suffers from the **Convoy Effect** when short processes wait behind one long CPU-bound process.\n"
            "- **SJF / SRTF:** Minimizes average waiting time; SRTF is preemptive and checks burst remaining on every new arrival.\n"
            "- **Round Robin (RR):** Preemptive with time quantum $q$. Large $q$ degrades to FCFS; tiny $q$ increases context-switch overhead.\n"
            "- **Priority Scheduling:** Can cause **Starvation** for low-priority jobs; mitigated via **Aging**."
        )
        examples = [
            WorkedExample(
                title="PYQ 2025: SRTF vs Round Robin (q = 3 ms)",
                problem_statement="Processes: P1(AT=0, BT=8), P2(AT=1, BT=4), P3(AT=2, BT=9), P4(AT=3, BT=5). Find Average Waiting Time under Preemptive SJF (SRTF).",
                given_data=["P1: AT=0, BT=8", "P2: AT=1, BT=4", "P3: AT=2, BT=9", "P4: AT=3, BT=5"],
                formulae_used=["TAT = Completion Time (CT) - Arrival Time (AT)", "WT = Turnaround Time (TAT) - Burst Time (BT)"],
                steps=[
                    "t=0->1: P1 runs (remaining BT=7). At t=1, P2 arrives with BT=4 < 7 -> preempt P1.",
                    "t=1->5: P2 runs to completion (CT_P2 = 5). Meanwhile P3(9) and P4(5) arrive.",
                    "t=5->10: Remaining bursts: P1=7, P3=9, P4=5. Shortest is P4 -> P4 finishes at CT_P4 = 10.",
                    "t=10->17: Next shortest is P1(7) -> P1 finishes at CT_P1 = 17.",
                    "t=17->26: P3(9) runs last -> CT_P3 = 26.",
                    "TAT: P1=17-0=17, P2=5-1=4, P3=26-2=24, P4=10-3=7. WT: P1=9, P2=0, P3=15, P4=2.",
                ],
                final_answer="Average WT = (9 + 0 + 15 + 2) / 4 = 6.5 ms | Average TAT = 13.0 ms",
                exam_tip="Always draw the Gantt timeline tick-by-tick at arrival instants before computing CT.",
            ),
            WorkedExample(
                title="PYQ 2023/2024: Round Robin Turnaround Analysis",
                problem_statement="Using P1(0,10), P2(1,5), P3(2,2) with Round Robin time quantum q = 2 ms, compute Completion and Waiting Times.",
                given_data=["P1: AT=0, BT=10", "P2: AT=1, BT=5", "P3: AT=2, BT=2", "Time Quantum q = 2 ms"],
                formulae_used=["Ready Queue FIFO rotation every q ms", "WT = CT - AT - BT"],
                steps=[
                    "t=0->2: P1 runs (rem=8); P2 arrives at 1, P3 arrives at 2. Queue: [P2, P3, P1].",
                    "t=2->4: P2 runs (rem=3). Queue: [P3, P1, P2].",
                    "t=4->6: P3 runs (rem=0, CT_P3=6). Queue: [P1, P2].",
                    "t=6->8: P1 runs (rem=6); t=8->10: P2 runs (rem=1); t=10->12: P1(4); t=12->13: P2 finishes (CT_P2=13).",
                    "t=13->17: P1 finishes remaining 4 ms (CT_P1=17).",
                ],
                final_answer="WT: P1=7, P2=7, P3=2 -> Average WT = 5.33 ms",
                exam_tip="Newly arrived processes enter the ready queue BEFORE the preempted running process is re-appended.",
            ),
        ]
        cheat = (
            f"# 1-Page Cheat Sheet: {topic}\n\n"
            "## Core Formulae\n"
            "- **Turnaround Time:** `TAT = CT - AT`\n"
            "- **Waiting Time:** `WT = TAT - BT`\n"
            "- **Response Time:** `RT = First_CPU_Time - AT`\n\n"
            "## Algorithm Comparison\n"
            "| Algorithm | Preemptive? | Optimal Avg WT? | Main Risk |\n"
            "|---|---|---|---|\n"
            "| FCFS | No | No | Convoy Effect |\n"
            "| SJF / SRTF | No / Yes | Yes | Starvation of long jobs |\n"
            "| Priority | Optional | No | Starvation (fix: Aging) |\n"
            "| Round Robin | Yes (q) | No (best RT) | High context-switch if q tiny |\n\n"
            "## PYQ Checklist\n"
            "- Mention **Convoy Effect** explicitly in FCFS theory questions.\n"
            "- For **Aging**, state that priority increases gradually with waiting time."
        )
        quiz = [
            QuizQuestion(
                id=1,
                question="Which CPU scheduling algorithm minimizes average waiting time for a given set of processes?",
                options=["First-Come First-Served (FCFS)", "Round Robin (RR)", "Shortest Remaining Time First (SRTF)", "Multilevel Queue"],
                correct_index=2,
                explanation="SRTF (preemptive SJF) is provably optimal for minimizing average waiting time.",
                pyq_tag="PYQ 2025",
            ),
            QuizQuestion(
                id=2,
                question="The Convoy Effect is primarily associated with which scheduling algorithm?",
                options=["FCFS", "SRTF", "Round Robin", "Priority with Aging"],
                correct_index=0,
                explanation="In FCFS, short processes get stuck waiting behind a single long CPU-bound process.",
                pyq_tag="PYQ 2023/2025",
            ),
            QuizQuestion(
                id=3,
                question="What technique prevents indefinite blocking (starvation) in Priority Scheduling?",
                options=["Compaction", "Aging", "Belady's Anomaly", "Swapping"],
                correct_index=1,
                explanation="Aging gradually increases the priority of processes that wait in the ready queue for a long time.",
                pyq_tag="PYQ 2024",
            ),
            QuizQuestion(
                id=4,
                question="If the time quantum q in Round Robin approaches infinity, Round Robin behaves like:",
                options=["SJF", "SRTF", "FCFS", "Priority Scheduling"],
                correct_index=2,
                explanation="With an arbitrarily large quantum, every process finishes within its first slice in arrival order (FCFS).",
                pyq_tag="PYQ 2023",
            ),
            QuizQuestion(
                id=5,
                question="Given Arrival Time = 2 ms, Burst Time = 6 ms, Completion Time = 13 ms, what is the Waiting Time?",
                options=["5 ms", "7 ms", "11 ms", "4 ms"],
                correct_index=0,
                explanation="TAT = CT - AT = 13 - 2 = 11 ms. WT = TAT - BT = 11 - 6 = 5 ms.",
                pyq_tag="PYQ 2024",
            ),
        ]
    elif any(k in t_low for k in ("banker", "deadlock", "coffman", "avoidance", "prevention")):
        summary = (
            f"### {topic} ({learning_style} Mode — {hours_remaining}h Window)\n\n"
            "**Syllabus Grounding:** Deadlock occurs iff all **4 Coffman Conditions** hold simultaneously: *Mutual Exclusion, Hold and Wait, No Preemption, Circular Wait*.\n\n"
            "- **Prevention:** Invalidate at least one Coffman condition (e.g., impose total ordering of resource types to break Circular Wait).\n"
            "- **Avoidance (Banker's Algorithm):** Uses `Need[i] = Max[i] - Allocation[i]` and runs the Safety Algorithm (`Need[i] <= Work`) before granting requests.\n"
            "- **Resource Allocation Graph (RAG):** Single-instance cycle => deadlock; multi-instance cycle => necessary but NOT sufficient condition."
        )
        examples = [
            WorkedExample(
                title="PYQ 2025: Banker's Safety & Resource-Request Check",
                problem_statement="5 processes (P0-P4), resources A=10, B=5, C=7. Allocation total = (7,2,5). Determine Available, Need matrix, Safe Sequence, and whether P1 request (1,0,2) is granted.",
                given_data=["Total=(10,5,7)", "Sum(Alloc)=(7,2,5)", "P0 Need=(7,4,3), P1 Need=(1,2,2), P2 Need=(6,0,0), P3 Need=(0,1,1), P4 Need=(4,3,1)"],
                formulae_used=["Available = Total - Sum(Allocation)", "Need[i] = Max[i] - Allocation[i]", "Safety condition: Need[i] <= Work"],
                steps=[
                    "Available = (10,5,7) - (7,2,5) = (3,3,2). Initialize Work = (3,3,2).",
                    "P1 Need(1,2,2) <= (3,3,2) -> run P1 -> Work = (3,3,2)+(2,0,0) = (5,3,2).",
                    "P3 Need(0,1,1) <= (5,3,2) -> run P3 -> Work = (7,4,3).",
                    "P4 Need(4,3,1) <= (7,4,3) -> run P4 -> Work = (7,4,5).",
                    "P0 Need(7,4,3) <= (7,4,5) -> run P0 -> Work = (7,5,5); finally P2 Need(6,0,0) <= (7,5,5).",
                    "For P1 request (1,0,2): Request <= Need(1,2,2) and Request <= Available(3,3,2). Tentatively Available=(2,3,0), P1 Alloc=(3,0,2), P1 Need=(0,2,0) -> safe sequence <P1, P3, P4, P0, P2> still holds!",
                ],
                final_answer="Safe Sequence: <P1, P3, P4, P0, P2>. Request (1,0,2) by P1 CAN be granted immediately.",
                exam_tip="Always check BOTH Request <= Need AND Request <= Available before running the Safety Algorithm.",
            )
        ]
        cheat = (
            f"# 1-Page Cheat Sheet: {topic}\n\n"
            "## 4 Coffman Conditions (All 4 Required)\n"
            "1. **Mutual Exclusion** | 2. **Hold & Wait** | 3. **No Preemption** | 4. **Circular Wait**\n\n"
            "## Banker's Algorithm Equations\n"
            "- `Need[i][j] = Max[i][j] - Allocation[i][j]`\n"
            "- **Safety Step:** Find `i` with `Finish[i] == False` and `Need[i] <= Work`; set `Work += Allocation[i]`.\n"
            "- **Request Check:** `Request[i] <= Need[i]` and `Request[i] <= Available`.\n\n"
            "## PYQ Trap\n"
            "- A cycle in a **multi-instance** RAG does *not* guarantee deadlock."
        )
        quiz = [
            QuizQuestion(
                id=1,
                question="Which of the following is NOT one of the four Coffman conditions for deadlock?",
                options=["Mutual Exclusion", "Hold and Wait", "Circular Wait", "Starvation"],
                correct_index=3,
                explanation="The four Coffman conditions are Mutual Exclusion, Hold and Wait, No Preemption, and Circular Wait.",
                pyq_tag="PYQ 2024",
            ),
            QuizQuestion(
                id=2,
                question="In Banker's Algorithm, how is the Need matrix computed?",
                options=["Allocation - Max", "Max - Allocation", "Available + Allocation", "Max - Available"],
                correct_index=1,
                explanation="Need[i] = Max[i] - Allocation[i] represents remaining resource demand for process i.",
                pyq_tag="PYQ 2022/2025",
            ),
            QuizQuestion(
                id=3,
                question="Imposing a strict linear ordering on all resource types breaks which deadlock condition?",
                options=["Mutual Exclusion", "No Preemption", "Circular Wait", "Hold and Wait"],
                correct_index=2,
                explanation="If processes only request resources in strictly increasing order, no circular wait cycle can form.",
                pyq_tag="PYQ 2024",
            ),
            QuizQuestion(
                id=4,
                question="A cycle in a Resource Allocation Graph (RAG) guarantees deadlock when:",
                options=["Every resource type has a single instance", "Resources have multiple instances", "Banker's Algorithm is active", "Preemption is enabled"],
                correct_index=0,
                explanation="A cycle is both necessary and sufficient for deadlock only when each resource has a single instance.",
                pyq_tag="PYQ 2023",
            ),
            QuizQuestion(
                id=5,
                question="Before tentatively granting Request[i] in Banker's Resource-Request Algorithm, which condition must hold?",
                options=["Request[i] > Need[i]", "Request[i] <= Need[i] and Request[i] <= Available", "Work == 0", "All processes finished"],
                correct_index=1,
                explanation="A process cannot exceed its declared maximum need, nor can the OS grant more than currently available.",
                pyq_tag="PYQ 2022/2025",
            ),
        ]
    elif any(k in t_low for k in ("paging", "tlb", "emat", "memory", "fragmentation", "page replacement", "belady", "lru", "fifo", "demand")):
        summary = (
            f"### {topic} ({learning_style} Mode — {hours_remaining}h Window)\n\n"
            "**Syllabus Grounding:** Covers logical-to-physical translation $(p, d) \\to (f, d)$, **TLB** speedups, and **Page Replacement** (FIFO, OPT, LRU) under Demand Paging.\n\n"
            "- **EMAT Formula:** $\\text{EMAT} = h(t_{\\text{TLB}} + t_{\\text{mem}}) + (1 - h)(t_{\\text{TLB}} + 2t_{\\text{mem}})$.\n"
            "- **Page Fault EAT:** $\\text{EAT} = (1 - p) \\cdot ma + p \\cdot \\text{PageFaultServiceTime}$.\n"
            "- **Belady's Anomaly:** Under FIFO, increasing physical frames can paradoxically *increase* page faults; OPT and LRU are stack algorithms and are immune."
        )
        examples = [
            WorkedExample(
                title="PYQ 2025: TLB Effective Memory Access Time & Page Table Size",
                problem_statement="TLB access = 15 ns, main memory = 120 ns, TLB hit ratio h = 90%. Find EMAT. Also find Page Table size for 32-bit address, 4 KB page, 4-byte PTE.",
                given_data=["t_TLB = 15 ns", "t_mem = 120 ns", "h = 0.90", "32-bit VA, Page Size = 4 KB = 2^12 B, PTE = 4 B"],
                formulae_used=["EMAT = h*(t_TLB + t_mem) + (1-h)*(t_TLB + 2*t_mem)", "Num Pages = 2^(32 - 12) = 2^20"],
                steps=[
                    "Hit access time = 15 + 120 = 135 ns.",
                    "Miss access time (TLB lookup + page table access + data access) = 15 + 2*120 = 255 ns.",
                    "EMAT = 0.90*(135) + 0.10*(255) = 121.5 + 25.5 = 147 ns.",
                    "Number of pages = 2^32 / 2^12 = 2^20 (1M entries). Page Table Size = 2^20 * 4 bytes = 4 MB.",
                ],
                final_answer="EMAT = 147 ns | Page Table Size = 4 MB",
                exam_tip="On a TLB miss, do not forget to still add t_TLB once before the two memory accesses!",
            )
        ]
        cheat = (
            f"# 1-Page Cheat Sheet: {topic}\n\n"
            "## Key Equations\n"
            "- **EMAT:** `h*(t_TLB + t_mem) + (1 - h)*(t_TLB + 2*t_mem)`\n"
            "- **Demand Paging EAT:** `(1 - p)*ma + p*(PF_service_time)`\n"
            "- **Page Offset Bits:** `log2(Page_Size)`\n\n"
            "## Page Replacement Summary\n"
            "- **FIFO:** Simple queue; suffers from **Belady's Anomaly**.\n"
            "- **Optimal (OPT):** Replaces page unused longest in future; lowest faults (theoretical benchmark).\n"
            "- **LRU:** Replaces least recently used; stack algorithm (no Belady's Anomaly)."
        )
        quiz = [
            QuizQuestion(
                id=1,
                question="With TLB access = 20 ns, memory = 100 ns, and hit ratio 80%, what is the EMAT?",
                options=["120 ns", "140 ns", "160 ns", "180 ns"],
                correct_index=1,
                explanation="EMAT = 0.8*(20+100) + 0.2*(20+200) = 96 + 44 = 140 ns.",
                pyq_tag="PYQ 2024/2025",
            ),
            QuizQuestion(
                id=2,
                question="Which page replacement algorithm can exhibit Belady's Anomaly?",
                options=["Optimal (OPT)", "LRU", "FIFO", "Clock (with stack property)"],
                correct_index=2,
                explanation="FIFO is not a stack algorithm, so allocating more frames can sometimes cause more page faults.",
                pyq_tag="PYQ 2024",
            ),
            QuizQuestion(
                id=3,
                question="For a 32-bit virtual address and 4 KB page size, how many bits are used for the page offset?",
                options=["10 bits", "12 bits", "16 bits", "20 bits"],
                correct_index=1,
                explanation="4 KB = 4096 = 2^12 bytes, so the page offset d requires 12 bits.",
                pyq_tag="PYQ 2025",
            ),
            QuizQuestion(
                id=4,
                question="Paging completely eliminates which type of fragmentation?",
                options=["Internal Fragmentation", "External Fragmentation", "Thrashing", "Page Faults"],
                correct_index=1,
                explanation="Any free frame can be allocated to any process, eliminating external fragmentation (though the last page may have internal fragmentation).",
                pyq_tag="PYQ 2023",
            ),
            QuizQuestion(
                id=5,
                question="What happens during Thrashing?",
                options=["CPU utilization is 100%", "System spends more time paging than executing", "TLB hit ratio becomes 100%", "Disk seek time drops to zero"],
                correct_index=1,
                explanation="When active processes lack enough frames for their working set, constant page faults cause CPU utilization to plummet.",
                pyq_tag="PYQ 2024",
            ),
        ]
    else:
        # Dynamic chunk-grounded synthesis for any custom syllabus/PYQ PDF
        syl_excerpt = re.sub(r"\s+", " ", syl_text)[:700] if syl_text else "See uploaded syllabus."
        pyq_excerpt = re.sub(r"\s+", " ", pyq_text)[:550] if pyq_text else "No direct PYQ match found; focus on core syllabus definitions."
        summary = (
            f"### {topic} ({learning_style} Mode — {hours_remaining}h Window)\n\n"
            f"**Grounded Syllabus Scope:** {syl_excerpt}\n\n"
            f"**Exam Trend from PYQs:** {pyq_excerpt}\n\n"
            "> *Tip: Add a `GEMINI_API_KEY` (and optional `GROQ_API_KEY`) in `.env` for live AI-synthesized numericals and custom MCQs tailored to any uploaded PDF.*"
        )
        examples = [
            WorkedExample(
                title=f"PYQ-Grounded Walkthrough: {topic}",
                problem_statement=pyq_excerpt[:240],
                given_data=["Extracted directly from uploaded Syllabus & PYQ chunks"],
                formulae_used=["Refer to retrieved syllabus definitions and boundary conditions"],
                steps=[
                    "Step 1: Identify key parameters and constraints stated in the exam question.",
                    "Step 2: Apply the exact syllabus definition/algorithm retrieved for this topic.",
                    "Step 3: Verify boundary cases and units before writing the final answer.",
                ],
                final_answer="Verify step-by-step calculations against the retrieved PYQ rubric.",
                exam_tip="Clearly state assumptions and equations before substituting values for partial credit.",
            )
        ]
        cheat = (
            f"# 1-Page Cheat Sheet: {topic}\n\n"
            f"## Syllabus Summary\n- {syl_excerpt[:350]}\n\n"
            f"## Key PYQ Focus\n- {pyq_excerpt[:350]}\n"
        )
        quiz = [
            QuizQuestion(
                id=i,
                question=f"[{topic}] Which exam strategy best aligns with '{learning_style}' preparation based on the retrieved PYQs?",
                options=[
                    "Derive answers directly from syllabus definitions and verify with PYQ constraints",
                    "Skip core syllabus boundaries and memorize unrelated topics",
                    "Ignore units, assumptions, and intermediate steps",
                    "Omit checking edge cases in multi-part exam questions",
                ],
                correct_index=0,
                explanation="Strictly grounding answers in the prescribed syllabus definitions and PYQ patterns maximizes exam accuracy.",
                pyq_tag="Grounded Check",
            )
            for i in range(1, 6)
        ]

    return {
        "summary": summary,
        "worked_examples": examples,
        "cheat_sheet_markdown": cheat,
        "quiz": quiz,
    }


def _generate_notes_and_examples_node(state: StudyPackState) -> Dict[str, Any]:
    topic = state["topic"]
    hours = state["hours_remaining"]
    style = state["learning_style"]
    syl_docs = state["syllabus_chunks"]
    pyq_docs = state["pyq_chunks"]

    context = _format_context_blocks(syl_docs, pyq_docs)
    llm = _get_gemini_llm(temperature=0.0)

    if llm is not None and (syl_docs or pyq_docs):
        try:
            system_msg = SystemMessage(
                content=(
                    "You are ExamPulse AI, a strictly syllabus-grounded engineering tutor. "
                    "Use ONLY the retrieved Syllabus and PYQ context provided below. "
                    "Do NOT introduce external topics or facts outside the provided context. "
                    "If the context lacks something, stay strictly within what is present. "
                    "Return ONLY valid JSON matching the exact schema requested."
                )
            )
            human_msg = HumanMessage(
                content=(
                    f"Target Topic: {topic}\n"
                    f"Hours Remaining: {hours}\n"
                    f"Learning Style: {style}\n\n"
                    "Adaptation rules:\n"
                    "- Crash Course: ultra-concise bullet points, high-yield exam triggers, formulas first.\n"
                    "- Conceptual: clear intuition, definitions, comparisons, and why-it-works explanations.\n"
                    "- Numerical-Heavy: emphasize equations, units, edge cases, and detailed step-by-step solved numericals.\n\n"
                    f"{context}\n\n"
                    "Respond with a single JSON object containing:\n"
                    "{\n"
                    '  "summary": "Markdown string tailored to learning_style & hours_remaining (use $...$ or $$...$$ for math)",\n'
                    '  "worked_examples": [\n'
                    "    {\n"
                    '      "title": "...",\n'
                    '      "problem_statement": "...",\n'
                    '      "given_data": ["..."],\n'
                    '      "formulae_used": ["..."],\n'
                    '      "steps": ["Step 1...", "Step 2..."],\n'
                    '      "final_answer": "...",\n'
                    '      "exam_tip": "..."\n'
                    "    }\n"
                    "  ],\n"
                    '  "cheat_sheet_markdown": "Dense 1-page Markdown revision sheet with headings, formulas, tables, and exam traps"\n'
                    "}"
                )
            )
            resp = llm.invoke([system_msg, human_msg])
            data = json.loads(_strip_json_fences(str(resp.content)))
            examples = [WorkedExample(**ex) for ex in data.get("worked_examples", [])]
            if data.get("summary") and examples and data.get("cheat_sheet_markdown"):
                return {
                    "summary": data["summary"],
                    "worked_examples": examples,
                    "cheat_sheet_markdown": data["cheat_sheet_markdown"],
                    "generation_mode": f"gemini ({settings.gemini_model})",
                }
        except Exception as exc:
            logger.warning("Gemini content generation failed (%s); using grounded fallback.", exc)

    fb = _fallback_study_pack_content(topic, style, hours, syl_docs, pyq_docs)
    return {
        "summary": fb["summary"],
        "worked_examples": fb["worked_examples"],
        "cheat_sheet_markdown": fb["cheat_sheet_markdown"],
        "generation_mode": "grounded-local-fallback",
    }


def _generate_pyq_quiz_node(state: StudyPackState) -> Dict[str, Any]:
    topic = state["topic"]
    syl_docs = state["syllabus_chunks"]
    pyq_docs = state["pyq_chunks"]
    context = _format_context_blocks(syl_docs, pyq_docs)

    quiz_llm = _get_groq_llm(temperature=0.0)
    quiz_provider = f"groq ({settings.groq_model})"
    if quiz_llm is None:
        quiz_llm = _get_gemini_llm(temperature=0.0)
        quiz_provider = f"gemini ({settings.gemini_model})"

    if quiz_llm is not None and (syl_docs or pyq_docs):
        try:
            system_msg = SystemMessage(
                content=(
                    "You are an engineering exam question setter. Generate exactly 5 PYQ-style "
                    "multiple-choice questions grounded ONLY in the provided Syllabus and PYQ context. "
                    "Return ONLY valid JSON."
                )
            )
            human_msg = HumanMessage(
                content=(
                    f"Topic: {topic}\n\n{context}\n\n"
                    "Return a JSON object with key 'quiz' containing 5 items:\n"
                    "{\n"
                    '  "quiz": [\n'
                    "    {\n"
                    '      "id": 1,\n'
                    '      "question": "...",\n'
                    '      "options": ["opt A", "opt B", "opt C", "opt D"],\n'
                    '      "correct_index": 0,\n'
                    '      "explanation": "Brief syllabus-grounded explanation",\n'
                    '      "pyq_tag": "e.g. PYQ 2024 or Concept Check"\n'
                    "    }\n"
                    "  ]\n"
                    "}"
                )
            )
            resp = quiz_llm.invoke([system_msg, human_msg])
            data = json.loads(_strip_json_fences(str(resp.content)))
            questions = [QuizQuestion(**q) for q in data.get("quiz", [])[:5]]
            if len(questions) >= 3:
                mode = state.get("generation_mode", "rag")
                if "fallback" not in mode:
                    mode = f"{mode} + quiz:{quiz_provider}"
                return {"quiz": questions, "generation_mode": mode}
        except Exception as exc:
            logger.warning("Quiz LLM generation failed (%s); using grounded fallback quiz.", exc)

    fb = _fallback_study_pack_content(
        topic,
        state["learning_style"],
        state["hours_remaining"],
        syl_docs,
        pyq_docs,
    )
    return {"quiz": fb["quiz"]}


_pack_builder = StateGraph(StudyPackState)
_pack_builder.add_node("retrieve_context", _retrieve_context_node)
_pack_builder.add_node("generate_notes_and_examples", _generate_notes_and_examples_node)
_pack_builder.add_node("generate_pyq_quiz", _generate_pyq_quiz_node)
_pack_builder.add_edge(START, "retrieve_context")
_pack_builder.add_edge("retrieve_context", "generate_notes_and_examples")
_pack_builder.add_edge("generate_notes_and_examples", "generate_pyq_quiz")
_pack_builder.add_edge("generate_pyq_quiz", END)
study_pack_graph = _pack_builder.compile()


def run_study_pack_workflow(
    session_id: str,
    topic: str,
    hours_remaining: float,
    learning_style: LearningStyle,
) -> StudyPackResponse:
    result = study_pack_graph.invoke(
        {
            "session_id": session_id,
            "topic": topic,
            "hours_remaining": hours_remaining,
            "learning_style": learning_style,
            "syllabus_chunks": [],
            "pyq_chunks": [],
            "grounded_sources": [],
            "summary": "",
            "worked_examples": [],
            "cheat_sheet_markdown": "",
            "quiz": [],
            "generation_mode": "rag",
        }
    )
    return StudyPackResponse(
        session_id=session_id,
        topic=topic,
        learning_style=learning_style,
        summary=result["summary"],
        worked_examples=result["worked_examples"],
        quiz=result["quiz"],
        cheat_sheet_markdown=result["cheat_sheet_markdown"],
        grounded_sources=result["grounded_sources"],
        generation_mode=result["generation_mode"],
    )
