import type {
  BackendHealth,
  EmailSummaryResponse,
  IngestResponse,
  LearningStyle,
  PrioritizeResponse,
  StudyPackResponse,
  SubjectSummaryResponse,
} from "@/types/exampulse";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") || "http://127.0.0.1:8000";

async function parseJsonOrThrow<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const errBody = await response.json();
      if (errBody?.detail) {
        message =
          typeof errBody.detail === "string"
            ? errBody.detail
            : JSON.stringify(errBody.detail);
      }
    } catch {
      // Keep default status message
    }
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}

export async function fetchBackendHealth(): Promise<BackendHealth> {
  const res = await fetch(`${API_BASE}/api/health`, { cache: "no-store" });
  return parseJsonOrThrow<BackendHealth>(res);
}

export async function ingestStudyFiles(
  syllabusPdf: File,
  pyqPdfs: File[]
): Promise<IngestResponse> {
  const formData = new FormData();
  formData.append("syllabus_pdf", syllabusPdf);
  for (const file of pyqPdfs) {
    formData.append("pyq_pdfs", file);
  }
  const res = await fetch(`${API_BASE}/api/ingest`, {
    method: "POST",
    body: formData,
  });
  return parseJsonOrThrow<IngestResponse>(res);
}

export async function loadDemoSession(): Promise<IngestResponse> {
  const res = await fetch(`${API_BASE}/api/load-demo`, {
    method: "POST",
  });
  return parseJsonOrThrow<IngestResponse>(res);
}

export async function prioritizeStudyPlan(params: {
  session_id: string;
  unchecked_topics: string[];
  hours_remaining: number;
  learning_style: LearningStyle;
}): Promise<PrioritizeResponse> {
  const res = await fetch(`${API_BASE}/api/prioritize`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  return parseJsonOrThrow<PrioritizeResponse>(res);
}

export async function generateStudyPack(params: {
  session_id: string;
  topic: string;
  hours_remaining: number;
  learning_style: LearningStyle;
}): Promise<StudyPackResponse> {
  const res = await fetch(`${API_BASE}/api/generate-study-pack`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  return parseJsonOrThrow<StudyPackResponse>(res);
}

export async function generateSubjectSummary(params: {
  session_id: string;
  learning_style: LearningStyle;
  hours_remaining: number;
}): Promise<SubjectSummaryResponse> {
  const res = await fetch(`${API_BASE}/api/generate-subject-summary`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  return parseJsonOrThrow<SubjectSummaryResponse>(res);
}

export async function emailSubjectSummary(params: {
  recipient_email: string;
  subject_title: string;
  summary_data: SubjectSummaryResponse;
  full_markdown: string;
}): Promise<EmailSummaryResponse> {
  const res = await fetch(`${API_BASE}/api/email-summary`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  return parseJsonOrThrow<EmailSummaryResponse>(res);
}
