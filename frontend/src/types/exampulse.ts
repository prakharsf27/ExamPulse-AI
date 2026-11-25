export type LearningStyle = "Crash Course" | "Conceptual" | "Numerical-Heavy";

export type PriorityTier = "Critical" | "High" | "Medium" | "Low";

export interface SyllabusUnit {
  unit_number: string;
  unit_title: string;
  topics: string[];
}

export interface ParsedSyllabus {
  course_title: string;
  units: SyllabusUnit[];
}

export interface WorkflowTraceEntry {
  step: number;
  node: string;
  title: string;
  detail: string;
  timestamp: string;
  chunk_count?: number | null;
  status: "completed" | "fallback";
}

export interface IngestResponse {
  session_id: string;
  syllabus: ParsedSyllabus;
  stats: {
    syllabus_chunks_count?: number;
    pyq_chunks_count?: number;
    syllabus_chunks: number;
    pyq_chunks: number;
    pyq_files: string[];
    qdrant_mode?: string;
    embedding_mode?: string;
    is_demo?: boolean;
  };
  workflow_trace?: WorkflowTraceEntry[];
}

export interface MatchedPYQ {
  question_snippet: string;
  source_file: string;
  relevance_score: number;
}

export interface PrioritizedTopic {
  topic: string;
  unit_title: string;
  priority_rank: number;
  priority_tier: PriorityTier;
  pyq_frequency: number;
  relevance_score: number;
  allocated_hours: number;
  rationale: string;
  matched_pyqs: MatchedPYQ[];
}

export interface PrioritizeResponse {
  session_id: string;
  hours_remaining: number;
  learning_style: LearningStyle;
  strategy_note: string;
  prioritized_topics: PrioritizedTopic[];
  workflow_trace?: WorkflowTraceEntry[];
}

export interface WorkedExample {
  title: string;
  problem_statement: string;
  given_data: string[];
  formulae_used: string[];
  steps: string[];
  final_answer: string;
  exam_tip: string;
}

export interface QuizQuestion {
  id: number;
  question: string;
  options: string[];
  correct_index: number;
  explanation: string;
  pyq_tag?: string | null;
}

export interface TwistedQuestion {
  question: string;
  marks: string;
  twist_hint: string;
  model_answer: string;
}

export interface RetrievedSource {
  source: "syllabus" | "pyq";
  paper_name: string;
  excerpt: string;
  score: number;
  chunk_index?: number;
}

export interface StudyPackResponse {
  session_id: string;
  topic: string;
  learning_style: LearningStyle;
  summary: string;
  worked_examples: WorkedExample[];
  twisted_questions?: TwistedQuestion[];
  quiz: QuizQuestion[];
  cheat_sheet_markdown: string;
  retrieved_sources: RetrievedSource[];
  workflow_trace: WorkflowTraceEntry[];
  notes_model?: string;
  generation_mode: string;
}

export interface BackendHealth {
  status: string;
  qdrant_mode: string;
  embedding_mode: string;
  persistence_mode: string;
  gemini_configured: boolean;
  groq_configured: boolean;
}

export interface UnitKeypoint {
  unit: string;
  key_concepts: string[];
  must_remember_formulas: string[];
  exam_tip: string;
}

export interface SubjectSummaryResponse {
  session_id: string;
  subject_title: string;
  executive_overview: string;
  unit_keypoints: UnitKeypoint[];
  high_probability_takeaways: string[];
  last_15_min_checklist: string[];
  full_markdown: string;
  model_used: string;
}

export interface EmailSummaryResponse {
  status: string;
  recipient: string;
}
