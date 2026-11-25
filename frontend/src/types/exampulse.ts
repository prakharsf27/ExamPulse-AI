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

export interface IngestResponse {
  session_id: string;
  syllabus: ParsedSyllabus;
  stats: {
    syllabus_chunks: number;
    pyq_chunks: number;
    pyq_files: string[];
    qdrant_mode?: string;
    is_demo?: boolean;
  };
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

export interface GroundedSource {
  source: "syllabus" | "pyq";
  filename: string;
  excerpt: string;
  score: number;
}

export interface StudyPackResponse {
  session_id: string;
  topic: string;
  learning_style: LearningStyle;
  summary: string;
  worked_examples: WorkedExample[];
  quiz: QuizQuestion[];
  cheat_sheet_markdown: string;
  grounded_sources: GroundedSource[];
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
