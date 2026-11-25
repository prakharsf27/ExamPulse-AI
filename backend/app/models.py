from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field

LearningStyle = Literal["Crash Course", "Conceptual", "Numerical-Heavy"]
PriorityTier = Literal["Critical", "High", "Medium", "Low"]


class SyllabusUnit(BaseModel):
    unit_number: str = Field(..., description="Unit identifier such as 'Unit 1' or 'Module 1'")
    unit_title: str = Field(..., description="Descriptive title of the unit")
    topics: List[str] = Field(..., description="Clean list of distinct syllabus topics in this unit")


class ParsedSyllabus(BaseModel):
    course_title: str = Field(..., description="Detected course or subject title")
    units: List[SyllabusUnit] = Field(..., description="Structured list of syllabus units and topics")


class IngestResponse(BaseModel):
    session_id: str
    syllabus: ParsedSyllabus
    stats: Dict[str, Any]


class PrioritizeRequest(BaseModel):
    session_id: str
    unchecked_topics: List[str] = Field(..., min_length=1)
    hours_remaining: float = Field(..., ge=0.5, le=72.0)
    learning_style: LearningStyle = "Conceptual"


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


class PrioritizeResponse(BaseModel):
    session_id: str
    hours_remaining: float
    learning_style: LearningStyle
    strategy_note: str
    prioritized_topics: List[PrioritizedTopic]


class StudyPackRequest(BaseModel):
    session_id: str
    topic: str = Field(..., min_length=1)
    hours_remaining: float = Field(default=6.0, ge=0.5, le=72.0)
    learning_style: LearningStyle = "Conceptual"


class WorkedExample(BaseModel):
    title: str
    problem_statement: str
    given_data: List[str] = Field(default_factory=list)
    formulae_used: List[str] = Field(default_factory=list)
    steps: List[str]
    final_answer: str
    exam_tip: str = ""


class QuizQuestion(BaseModel):
    id: int
    question: str
    options: List[str] = Field(..., min_length=4, max_length=4)
    correct_index: int = Field(..., ge=0, le=3)
    explanation: str
    pyq_tag: Optional[str] = None


class GroundedSource(BaseModel):
    source: Literal["syllabus", "pyq"]
    filename: str
    excerpt: str
    score: float


class StudyPackResponse(BaseModel):
    session_id: str
    topic: str
    learning_style: LearningStyle
    summary: str
    worked_examples: List[WorkedExample]
    quiz: List[QuizQuestion]
    cheat_sheet_markdown: str
    grounded_sources: List[GroundedSource] = Field(default_factory=list)
    generation_mode: str = "rag"
