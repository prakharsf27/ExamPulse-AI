"use client";

import React, { useRef, useState } from "react";
import {
  BookOpenCheck,
  FileText,
  Files,
  Loader2,
  Rocket,
  Sparkles,
  Trash2,
  UploadCloud,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

interface UploadPanelProps {
  onIngest: (syllabus: File, pyqs: File[]) => Promise<void>;
  onLoadDemo: () => Promise<void>;
  isLoading: boolean;
  loadingLabel: string;
  error: string | null;
}

export function UploadPanel({
  onIngest,
  onLoadDemo,
  isLoading,
  loadingLabel,
  error,
}: UploadPanelProps) {
  const [syllabusFile, setSyllabusFile] = useState<File | null>(null);
  const [pyqFiles, setPyqFiles] = useState<File[]>([]);
  const [dragTarget, setDragTarget] = useState<"syllabus" | "pyq" | null>(null);

  const syllabusInputRef = useRef<HTMLInputElement>(null);
  const pyqInputRef = useRef<HTMLInputElement>(null);

  const handleSyllabusSelect = (files: FileList | null) => {
    if (!files || files.length === 0) return;
    const pdf = Array.from(files).find((f) => f.name.toLowerCase().endsWith(".pdf"));
    if (pdf) setSyllabusFile(pdf);
  };

  const handlePyqSelect = (files: FileList | null) => {
    if (!files || files.length === 0) return;
    const pdfs = Array.from(files).filter((f) => f.name.toLowerCase().endsWith(".pdf"));
    if (pdfs.length === 0) return;
    setPyqFiles((prev) => {
      const existing = new Set(prev.map((p) => `${p.name}-${p.size}`));
      const next = [...prev];
      for (const f of pdfs) {
        if (!existing.has(`${f.name}-${f.size}`)) next.push(f);
      }
      return next;
    });
  };

  const handleSubmit = async () => {
    if (!syllabusFile || pyqFiles.length === 0) return;
    await onIngest(syllabusFile, pyqFiles);
  };

  return (
    <div className="mx-auto max-w-5xl space-y-6 py-4">
      {/* Hero + 1-Click Demo Banner */}
      <div className="relative overflow-hidden rounded-2xl border border-[#1E3A8A]/15 bg-gradient-to-br from-[#1E3A8A] via-[#1E3A8A] to-[#172554] p-6 sm:p-8 text-white shadow-lg">
        <div className="relative z-10 flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
          <div className="max-w-2xl space-y-3">
            <Badge className="border-white/20 bg-white/15 text-white">
              <Sparkles className="h-3.5 w-3.5 text-[#E17055]" />
              Constraint-Aware Agentic RAG
            </Badge>
            <h1 className="text-2xl font-extrabold tracking-tight sm:text-3xl">
              Study Only What Matters for Tomorrow&apos;s Exam
            </h1>
            <p className="text-sm leading-relaxed text-blue-100 sm:text-base">
              Upload your university syllabus and Previous Year Question Papers (PYQs).
              ExamPulse cross-references unchecked topics against historical exam frequency,
              budgets your remaining hours, and generates strictly syllabus-grounded notes,
              worked numericals, quizzes, and a 1-page cheat sheet.
            </p>
          </div>

          <div className="shrink-0 rounded-xl border border-white/15 bg-white/10 p-4 backdrop-blur-sm lg:w-72">
            <p className="text-xs font-semibold uppercase tracking-wider text-blue-100">
              Instant Evaluation
            </p>
            <p className="mt-1 text-sm text-white/90">
              No PDFs handy? Load CS-302 Operating Systems + 4 End-Sem PYQs immediately.
            </p>
            <Button
              variant="accent"
              size="lg"
              onClick={onLoadDemo}
              disabled={isLoading}
              className="mt-3 w-full font-bold shadow-md"
            >
              {isLoading && loadingLabel.includes("demo") ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Rocket className="h-4 w-4" />
              )}
              Load 1-Click Demo (OS)
            </Button>
          </div>
        </div>
      </div>

      {error && (
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm font-medium text-red-800">
          {error}
        </div>
      )}

      {/* Upload Dropzones */}
      <div className="grid gap-5 md:grid-cols-2">
        {/* Syllabus PDF */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-[#1E3A8A]">
              <BookOpenCheck className="h-5 w-5 text-[#E17055]" />
              1. Prescribed Syllabus PDF
            </CardTitle>
            <p className="text-xs text-slate-500">
              Used to extract Units &amp; Topics and enforce strict grounding boundaries.
            </p>
          </CardHeader>
          <CardContent>
            <div
              onDragOver={(e) => {
                e.preventDefault();
                setDragTarget("syllabus");
              }}
              onDragLeave={() => setDragTarget(null)}
              onDrop={(e) => {
                e.preventDefault();
                setDragTarget(null);
                handleSyllabusSelect(e.dataTransfer.files);
              }}
              onClick={() => syllabusInputRef.current?.click()}
              className={cn(
                "flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed p-6 text-center transition-colors",
                dragTarget === "syllabus"
                  ? "border-[#E17055] bg-[#FDF3F0]"
                  : "border-slate-300 bg-[#FFFCF5] hover:border-[#1E3A8A] hover:bg-slate-50"
              )}
            >
              <UploadCloud className="h-8 w-8 text-[#1E3A8A]/70" />
              <p className="mt-2 text-sm font-semibold text-slate-800">
                Drop your Syllabus PDF here, or click to browse
              </p>
              <p className="mt-1 text-xs text-slate-500">Single PDF with selectable text</p>
              <input
                ref={syllabusInputRef}
                type="file"
                accept=".pdf,application/pdf"
                className="hidden"
                onChange={(e) => handleSyllabusSelect(e.target.files)}
              />
            </div>

            {syllabusFile && (
              <div className="mt-3 flex items-center justify-between rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm">
                <div className="flex items-center gap-2 truncate">
                  <FileText className="h-4 w-4 shrink-0 text-[#1E3A8A]" />
                  <span className="truncate font-medium text-slate-800">
                    {syllabusFile.name}
                  </span>
                  <span className="text-xs text-slate-500">
                    ({Math.max(1, Math.round(syllabusFile.size / 1024))} KB)
                  </span>
                </div>
                <button
                  type="button"
                  onClick={() => setSyllabusFile(null)}
                  className="text-slate-400 hover:text-red-600"
                  aria-label="Remove syllabus file"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            )}
          </CardContent>
        </Card>

        {/* PYQ PDFs */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-[#1E3A8A]">
              <Files className="h-5 w-5 text-[#E17055]" />
              2. Previous Year Question Papers (PYQs)
            </CardTitle>
            <p className="text-xs text-slate-500">
              Upload 1 or more past exam papers to compute frequency &amp; question weightage.
            </p>
          </CardHeader>
          <CardContent>
            <div
              onDragOver={(e) => {
                e.preventDefault();
                setDragTarget("pyq");
              }}
              onDragLeave={() => setDragTarget(null)}
              onDrop={(e) => {
                e.preventDefault();
                setDragTarget(null);
                handlePyqSelect(e.dataTransfer.files);
              }}
              onClick={() => pyqInputRef.current?.click()}
              className={cn(
                "flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed p-6 text-center transition-colors",
                dragTarget === "pyq"
                  ? "border-[#E17055] bg-[#FDF3F0]"
                  : "border-slate-300 bg-[#FFFCF5] hover:border-[#1E3A8A] hover:bg-slate-50"
              )}
            >
              <UploadCloud className="h-8 w-8 text-[#E17055]/80" />
              <p className="mt-2 text-sm font-semibold text-slate-800">
                Drop one or multiple PYQ PDFs here
              </p>
              <p className="mt-1 text-xs text-slate-500">
                Supports multiple End-Sem / Mid-Sem papers
              </p>
              <input
                ref={pyqInputRef}
                type="file"
                multiple
                accept=".pdf,application/pdf"
                className="hidden"
                onChange={(e) => handlePyqSelect(e.target.files)}
              />
            </div>

            {pyqFiles.length > 0 && (
              <div className="mt-3 max-h-36 space-y-1.5 overflow-y-auto pr-1">
                {pyqFiles.map((file, idx) => (
                  <div
                    key={`${file.name}-${idx}`}
                    className="flex items-center justify-between rounded-lg border border-slate-200 bg-slate-50 px-3 py-1.5 text-sm"
                  >
                    <div className="flex items-center gap-2 truncate">
                      <FileText className="h-4 w-4 shrink-0 text-[#E17055]" />
                      <span className="truncate font-medium text-slate-800">{file.name}</span>
                    </div>
                    <button
                      type="button"
                      onClick={() =>
                        setPyqFiles((prev) => prev.filter((_, i) => i !== idx))
                      }
                      className="text-slate-400 hover:text-red-600"
                      aria-label={`Remove ${file.name}`}
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Primary Ingest Action */}
      <div className="flex flex-col items-center justify-between gap-3 rounded-xl border border-slate-200 bg-white px-5 py-4 sm:flex-row">
        <div className="text-sm text-slate-600">
          {syllabusFile && pyqFiles.length > 0 ? (
            <span className="font-medium text-emerald-700">
              Ready to index 1 Syllabus + {pyqFiles.length} PYQ paper(s) into Qdrant.
            </span>
          ) : (
            <span>Select your Syllabus PDF and at least 1 PYQ PDF to begin.</span>
          )}
        </div>
        <Button
          variant="primary"
          size="lg"
          disabled={!syllabusFile || pyqFiles.length === 0 || isLoading}
          onClick={handleSubmit}
        >
          {isLoading && !loadingLabel.includes("demo") ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              {loadingLabel || "Indexing PDFs..."}
            </>
          ) : (
            <>
              <Sparkles className="h-4 w-4" />
              Parse Syllabus &amp; Index PYQs
            </>
          )}
        </Button>
      </div>
    </div>
  );
}
