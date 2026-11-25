"use client";

import React, { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import {
  BookOpen,
  Calculator,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Download,
  FileCheck2,
  FileSpreadsheet,
  HelpCircle,
  Loader2,
  Printer,
  RefreshCw,
  ShieldCheck,
  XCircle,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/controls";
import { cn } from "@/lib/utils";
import type { StudyPackResponse } from "@/types/exampulse";

interface StudyWorkspaceProps {
  studyPack: StudyPackResponse | null;
  isLoading: boolean;
  loadingTopic: string | null;
  onRegenerate: (topic: string) => void;
}

export function StudyWorkspace({
  studyPack,
  isLoading,
  loadingTopic,
  onRegenerate,
}: StudyWorkspaceProps) {
  const [activeTab, setActiveTab] = useState("notes");
  const [openSolutions, setOpenSolutions] = useState<Record<number, boolean>>({ 0: true });
  const [answers, setAnswers] = useState<Record<number, number>>({});
  const [quizSubmitted, setQuizSubmitted] = useState(false);
  const [showSources, setShowSources] = useState(false);

  // Reset quiz & solution state whenever a new topic pack loads
  useEffect(() => {
    setAnswers({});
    setQuizSubmitted(false);
    setOpenSolutions({ 0: true });
    setShowSources(false);
  }, [studyPack?.topic, studyPack?.learning_style]);

  if (isLoading) {
    return (
      <Card className="border-[#1E3A8A]/15">
        <CardContent className="flex flex-col items-center justify-center py-16 text-center">
          <Loader2 className="h-9 w-9 animate-spin text-[#E17055]" />
          <h3 className="mt-4 text-base font-bold text-[#1E3A8A]">
            Synthesizing Grounded Study Pack for &ldquo;{loadingTopic}&rdquo;
          </h3>
          <p className="mt-1 max-w-md text-xs text-slate-500">
            Retrieving syllabus boundaries and PYQ chunks from Qdrant, solving numericals,
            creating 5 PYQ-style MCQs, and compiling your 1-page cheat sheet...
          </p>
        </CardContent>
      </Card>
    );
  }

  if (!studyPack) {
    return (
      <Card className="border-dashed border-slate-300 bg-white/70">
        <CardContent className="py-12 text-center">
          <BookOpen className="mx-auto h-8 w-8 text-[#1E3A8A]/50" />
          <h3 className="mt-3 text-base font-bold text-slate-800">
            Select any topic from the Priority Study Map above
          </h3>
          <p className="mt-1 text-xs text-slate-500">
            ExamPulse will generate tailored notes, step-by-step worked numericals,
            an auto-graded PYQ quiz, and a printable 1-page cheat sheet.
          </p>
        </CardContent>
      </Card>
    );
  }

  const totalQuestions = studyPack.quiz.length;
  const correctCount = studyPack.quiz.filter(
    (q) => answers[q.id] === q.correct_index
  ).length;
  const answeredCount = Object.keys(answers).length;

  const handleDownloadMarkdown = () => {
    const blob = new Blob([studyPack.cheat_sheet_markdown], {
      type: "text/markdown;charset=utf-8",
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    const slug = studyPack.topic
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/(^-|-$)/g, "");
    link.href = url;
    link.download = `${slug || "exampulse"}-cheat-sheet.md`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  };

  const handlePrintPdf = () => {
    setActiveTab("cheatsheet");
    setTimeout(() => window.print(), 120);
  };

  return (
    <Card className="border-[#1E3A8A]/15">
      <CardHeader className="no-print border-b border-slate-100 pb-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone="navy">{studyPack.learning_style}</Badge>
              <Badge tone="emerald">
                <ShieldCheck className="h-3 w-3" />
                Syllabus Grounded
              </Badge>
              <Badge tone="slate">{studyPack.generation_mode}</Badge>
            </div>
            <CardTitle className="mt-2 text-xl text-[#1E3A8A]">
              {studyPack.topic}
            </CardTitle>
          </div>

          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowSources((v) => !v)}
            >
              <FileCheck2 className="h-3.5 w-3.5 text-[#1E3A8A]" />
              Sources ({studyPack.grounded_sources.length})
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => onRegenerate(studyPack.topic)}
            >
              <RefreshCw className="h-3.5 w-3.5" />
              Refresh
            </Button>
          </div>
        </div>

        {showSources && studyPack.grounded_sources.length > 0 && (
          <div className="mt-3 grid gap-2 rounded-xl border border-slate-200 bg-[#FFFCF5] p-3 sm:grid-cols-2">
            {studyPack.grounded_sources.map((src, idx) => (
              <div
                key={idx}
                className="rounded-lg border border-slate-200 bg-white p-2.5 text-xs"
              >
                <div className="mb-1 flex items-center justify-between">
                  <Badge tone={src.source === "syllabus" ? "navy" : "coral"}>
                    {src.source.toUpperCase()}
                  </Badge>
                  <span className="font-mono text-[11px] text-slate-500">
                    {src.filename}
                  </span>
                </div>
                <p className="line-clamp-3 text-slate-600">{src.excerpt}</p>
              </div>
            ))}
          </div>
        )}
      </CardHeader>

      <CardContent className="pt-4">
        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="no-print">
            <TabsTrigger value="notes">
              <BookOpen className="h-4 w-4" />
              Tailored Notes
            </TabsTrigger>
            <TabsTrigger value="examples">
              <Calculator className="h-4 w-4" />
              Worked Examples ({studyPack.worked_examples.length})
            </TabsTrigger>
            <TabsTrigger value="quiz">
              <HelpCircle className="h-4 w-4" />
              PYQ Quiz ({studyPack.quiz.length})
            </TabsTrigger>
            <TabsTrigger value="cheatsheet">
              <FileSpreadsheet className="h-4 w-4" />
              1-Page Cheat Sheet
            </TabsTrigger>
          </TabsList>

          {/* Tab 1: Tailored Notes */}
          <TabsContent value="notes" className="no-print">
            <div className="prose prose-slate max-w-none rounded-xl border border-slate-200/80 bg-[#FFFCF5] p-5 prose-headings:text-[#1E3A8A] prose-strong:text-slate-900 prose-code:rounded prose-code:bg-slate-100 prose-code:px-1 prose-code:text-[#C85A40]">
              <ReactMarkdown
                remarkPlugins={[remarkGfm, remarkMath]}
                rehypePlugins={[rehypeKatex]}
              >
                {studyPack.summary}
              </ReactMarkdown>
            </div>
          </TabsContent>

          {/* Tab 2: Worked Examples & Numericals */}
          <TabsContent value="examples" className="no-print space-y-4">
            {studyPack.worked_examples.map((ex, idx) => {
              const isOpen = !!openSolutions[idx];
              return (
                <div
                  key={idx}
                  className="overflow-hidden rounded-xl border border-slate-200 bg-white"
                >
                  <div className="border-b border-slate-100 bg-[#FFFCF5] p-4">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <h4 className="text-sm font-bold text-[#1E3A8A] sm:text-base">
                        {ex.title}
                      </h4>
                      <Badge tone="coral">Solved Example #{idx + 1}</Badge>
                    </div>
                    <p className="mt-2 text-sm leading-relaxed text-slate-800">
                      {ex.problem_statement}
                    </p>

                    {ex.given_data.length > 0 && (
                      <div className="mt-3 flex flex-wrap gap-1.5">
                        {ex.given_data.map((g, gIdx) => (
                          <span
                            key={gIdx}
                            className="rounded-md border border-slate-200 bg-white px-2 py-0.5 font-mono text-xs text-slate-700"
                          >
                            {g}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>

                  <div className="p-4">
                    <button
                      type="button"
                      onClick={() =>
                        setOpenSolutions((prev) => ({
                          ...prev,
                          [idx]: !prev[idx],
                        }))
                      }
                      className="flex w-full items-center justify-between rounded-lg border border-slate-200 bg-slate-50 px-3.5 py-2 text-xs font-bold text-[#1E3A8A] hover:bg-slate-100"
                    >
                      <span>
                        {isOpen ? "Hide" : "Reveal"} Step-by-Step Solution ({ex.steps.length} steps)
                      </span>
                      {isOpen ? (
                        <ChevronUp className="h-4 w-4" />
                      ) : (
                        <ChevronDown className="h-4 w-4" />
                      )}
                    </button>

                    {isOpen && (
                      <div className="mt-4 space-y-3">
                        {ex.formulae_used.length > 0 && (
                          <div className="rounded-lg border border-[#1E3A8A]/20 bg-[#EEF2FF]/60 p-3">
                            <p className="text-[11px] font-bold uppercase tracking-wider text-[#1E3A8A]">
                              Formulae Used
                            </p>
                            <ul className="mt-1 list-disc space-y-1 pl-4 font-mono text-xs text-slate-800">
                              {ex.formulae_used.map((f, fIdx) => (
                                <li key={fIdx}>{f}</li>
                              ))}
                            </ul>
                          </div>
                        )}

                        <ol className="space-y-2">
                          {ex.steps.map((step, sIdx) => (
                            <li
                              key={sIdx}
                              className="flex gap-3 rounded-lg border border-slate-100 bg-[#FFFCF5] p-3 text-sm text-slate-800"
                            >
                              <span className="inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-[#1E3A8A] font-mono text-[11px] font-bold text-white">
                                {sIdx + 1}
                              </span>
                              <span className="leading-relaxed">{step}</span>
                            </li>
                          ))}
                        </ol>

                        <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm font-bold text-emerald-900">
                          Final Answer: {ex.final_answer}
                        </div>

                        {ex.exam_tip && (
                          <div className="rounded-lg border border-[#FADFD7] bg-[#FDF3F0] p-3 text-xs text-[#9C3E27]">
                            <span className="font-bold">Exam Tip: </span>
                            {ex.exam_tip}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </TabsContent>

          {/* Tab 3: Auto-Graded PYQ Quiz */}
          <TabsContent value="quiz" className="no-print space-y-4">
            {quizSubmitted && (
              <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-[#1E3A8A]/20 bg-[#EEF2FF] p-4">
                <div>
                  <p className="text-xs font-bold uppercase tracking-wider text-[#1E3A8A]">
                    Quiz Score
                  </p>
                  <p className="text-xl font-extrabold text-slate-900">
                    {correctCount} / {totalQuestions} Correct (
                    {Math.round((correctCount / Math.max(1, totalQuestions)) * 100)}%)
                  </p>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    setAnswers({});
                    setQuizSubmitted(false);
                  }}
                >
                  <RefreshCw className="h-3.5 w-3.5" />
                  Retake Quiz
                </Button>
              </div>
            )}

            <div className="space-y-4">
              {studyPack.quiz.map((q, qIdx) => {
                const selected = answers[q.id];
                const isCorrect = selected === q.correct_index;

                return (
                  <div
                    key={q.id}
                    className="rounded-xl border border-slate-200 bg-white p-4"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="font-mono text-xs font-bold text-[#1E3A8A]">
                        Question {qIdx + 1} of {totalQuestions}
                      </span>
                      {q.pyq_tag && <Badge tone="coral">{q.pyq_tag}</Badge>}
                    </div>
                    <p className="mt-2 text-sm font-semibold text-slate-900">
                      {q.question}
                    </p>

                    <div className="mt-3 grid gap-2">
                      {q.options.map((opt, optIdx) => {
                        const chosen = selected === optIdx;
                        const isRightOpt = optIdx === q.correct_index;

                        let optStyle =
                          "border-slate-200 bg-[#FFFCF5] hover:border-[#1E3A8A]/50";
                        if (!quizSubmitted && chosen) {
                          optStyle =
                            "border-[#1E3A8A] bg-[#EEF2FF] ring-1 ring-[#1E3A8A]";
                        } else if (quizSubmitted && isRightOpt) {
                          optStyle = "border-emerald-500 bg-emerald-50 text-emerald-900";
                        } else if (quizSubmitted && chosen && !isRightOpt) {
                          optStyle = "border-red-400 bg-red-50 text-red-900";
                        }

                        return (
                          <label
                            key={optIdx}
                            className={cn(
                              "flex cursor-pointer items-center gap-3 rounded-lg border px-3.5 py-2.5 text-sm transition-all",
                              optStyle,
                              quizSubmitted && "cursor-default"
                            )}
                          >
                            <input
                              type="radio"
                              name={`quiz-q-${q.id}`}
                              checked={chosen}
                              disabled={quizSubmitted}
                              onChange={() =>
                                setAnswers((prev) => ({ ...prev, [q.id]: optIdx }))
                              }
                              className="h-4 w-4 accent-[#1E3A8A]"
                            />
                            <span className="font-mono text-xs font-bold text-slate-500">
                              {String.fromCharCode(65 + optIdx)}.
                            </span>
                            <span className="flex-1">{opt}</span>
                            {quizSubmitted && isRightOpt && (
                              <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-600" />
                            )}
                            {quizSubmitted && chosen && !isRightOpt && (
                              <XCircle className="h-4 w-4 shrink-0 text-red-500" />
                            )}
                          </label>
                        );
                      })}
                    </div>

                    {quizSubmitted && (
                      <div
                        className={cn(
                          "mt-3 rounded-lg border px-3 py-2 text-xs",
                          isCorrect
                            ? "border-emerald-200 bg-emerald-50 text-emerald-900"
                            : "border-amber-200 bg-amber-50 text-amber-950"
                        )}
                      >
                        <span className="font-bold">Explanation: </span>
                        {q.explanation}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>

            {!quizSubmitted && (
              <div className="flex items-center justify-between rounded-xl border border-slate-200 bg-[#FFFCF5] px-4 py-3">
                <span className="text-xs font-medium text-slate-600">
                  Answered {answeredCount} of {totalQuestions} questions
                </span>
                <Button
                  variant="primary"
                  disabled={answeredCount === 0}
                  onClick={() => setQuizSubmitted(true)}
                >
                  Submit &amp; Auto-Grade Quiz
                </Button>
              </div>
            )}
          </TabsContent>

          {/* Tab 4: 1-Page Cheat Sheet */}
          <TabsContent value="cheatsheet">
            <div className="no-print mb-4 flex flex-wrap items-center justify-between gap-2 rounded-xl border border-slate-200 bg-[#FFFCF5] px-4 py-3">
              <p className="text-xs font-medium text-slate-600">
                High-density revision sheet formatted for single-page A4 printing.
              </p>
              <div className="flex items-center gap-2">
                <Button variant="outline" size="sm" onClick={handleDownloadMarkdown}>
                  <Download className="h-3.5 w-3.5" />
                  Download Markdown
                </Button>
                <Button variant="accent" size="sm" onClick={handlePrintPdf}>
                  <Printer className="h-3.5 w-3.5" />
                  Print / Save PDF
                </Button>
              </div>
            </div>

            <div className="print-cheat-sheet prose prose-sm prose-slate max-w-none rounded-xl border border-slate-200 bg-white p-6 shadow-sm prose-headings:text-[#1E3A8A] prose-table:text-xs prose-th:bg-slate-100 prose-th:px-3 prose-th:py-1.5 prose-td:px-3 prose-td:py-1.5">
              <ReactMarkdown
                remarkPlugins={[remarkGfm, remarkMath]}
                rehypePlugins={[rehypeKatex]}
              >
                {studyPack.cheat_sheet_markdown}
              </ReactMarkdown>
            </div>
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  );
}
