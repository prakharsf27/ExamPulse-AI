# ExamPulse AI

A constraint-aware **Agentic RAG** learning companion for engineering students preparing for university exams.

## Architecture
- **Frontend (`/frontend`)**: Next.js (App Router, TypeScript), Tailwind CSS, Lucide Icons, KaTeX math rendering.
- **Backend (`/backend`)**: FastAPI, PyMuPDF (`fitz`), LangGraph, LangChain (`langchain-google-genai`, `langchain-groq`, `langchain-qdrant`), Qdrant (`:memory:` fallback or Qdrant Cloud), and Supabase (with local JSON/in-memory fallback).

## Quick Start (Zero-Config Out of the Box)
Both servers start with automatic local fallbacks (`Qdrant :memory:` + local JSON session store + grounded fallback mode) and include a **1-Click Demo (Operating Systems)**. Add `GEMINI_API_KEY` (and optionally `GROQ_API_KEY`, `QDRANT_URL`, `SUPABASE_URL`) in `.env` to enable live Gemini/Groq generation and cloud persistence.

### 1. Start the Backend
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### 2. Start the Frontend
```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000` in your browser and click **Load 1-Click Demo (OS)** or upload your Syllabus & PYQ PDFs.
