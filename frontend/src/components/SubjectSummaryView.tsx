"use client";

import React, { useState } from "react";
import {
  ArrowLeft,
  BookOpenCheck,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Download,
  Flame,
  Lightbulb,
  Loader2,
  Mail,
  Printer,
  RefreshCw,
  Send,
  Sparkles,
  XCircle,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/controls";
import { NotesAudioPlayer } from "@/components/NotesAudioPlayer";
import { emailSubjectSummary } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { SubjectSummaryResponse } from "@/types/exampulse";

interface SubjectSummaryViewProps {
  summary: SubjectSummaryResponse | null;
  isLoading: boolean;
  onRegenerate: () => void;
  onBack: () => void;
}

export function SubjectSummaryView({
  summary,
  isLoading,
  onRegenerate,
  onBack,
}: SubjectSummaryViewProps) {
  const [recipientEmail, setRecipientEmail] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [toast, setToast] = useState<{
    type: "success" | "error";
    message: string;
  } | null>(null);
  const [collapsedUnits, setCollapsedUnits] = useState<Record<number, boolean>>({});
  const [checkedRecall, setCheckedRecall] = useState<Set<number>>(new Set());

  if (isLoading) {
    return (
      <div className="mx-auto max-w-6xl">
        <Card className="border-[#1E3A8A]/15">
          <CardContent className="flex flex-col items-center justify-center py-20 text-center">
            <Loader2 className="h-9 w-9 animate-spin text-[#E17055]" />
            <h3 className="mt-4 text-base font-bold text-[#1E3A8A]">
              Compiling Master Subject Revision Summary
            </h3>
            <p className="mt-1 max-w-md text-xs text-slate-500">
              Synthesizing unit-by-unit keypoints, must-remember formulas, PYQ takeaways,
              and your last 15-minute exam hall checklist...
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (!summary) {
    return (
      <div className="mx-auto max-w-6xl">
        <Card className="border-dashed border-slate-300 bg-white/80">
          <CardContent className="py-16 text-center">
            <BookOpenCheck className="mx-auto h-8 w-8 text-[#1E3A8A]/50" />
            <h3 className="mt-3 text-base font-bold text-slate-800">
              No subject summary generated yet
            </h3>
            <Button variant="primary" size="sm" className="mt-4" onClick={onBack}>
              <ArrowLeft className="h-3.5 w-3.5" />
              Back to Study Map
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  const handleSendEmail = async (e: React.FormEvent) => {
    e.preventDefault();
    const email = recipientEmail.trim();
    if (!email) return;

    setIsSending(true);
    setToast(null);
    try {
      const res = await emailSubjectSummary({
        recipient_email: email,
        subject_title: summary.subject_title,
        summary_data: summary,
        full_markdown: summary.full_markdown,
      });
      setToast({
        type: "success",
        message: `Revision summary sent cleanly to ${res.recipient}!`,
      });
    } catch (err) {
      setToast({
        type: "error",
        message:
          err instanceof Error ? err.message : "Failed to send email summary.",
      });
    } finally {
      setIsSending(false);
    }
  };

  const handleDownloadMarkdown = () => {
    const blob = new Blob([summary.full_markdown], {
      type: "text/markdown;charset=utf-8",
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    const slug = summary.subject_title
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/(^-|-$)/g, "");
    link.href = url;
    link.download = `${slug || "exampulse"}-master-summary.md`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  };

  const toggleRecallItem = (idx: number) => {
    setCheckedRecall((prev) => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx);
      else next.add(idx);
      return next;
    });
  };

  const totalChecklist = summary.last_15_min_checklist.length;
  const doneChecklist = checkedRecall.size;

  return (
    <div className="mx-auto max-w-6xl space-y-5">
      {/* 1. Email Action Card (Top Banner) */}
      <Card className="no-print border-[#1E3A8A]/20 bg-gradient-to-r from-[#1E3A8A] to-[#172554] text-white shadow-md">
        <CardContent className="p-5 sm:p-6">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div className="space-y-1">
              <div className="flex flex-wrap items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={onBack}
                  className="h-7 border-white/25 bg-white/10 px-2.5 text-xs text-white hover:bg-white/20 hover:text-white"
                >
                  <ArrowLeft className="h-3.5 w-3.5" />
                  Back
                </Button>
                <Badge className="border-white/20 bg-white/15 text-white">
                  <Sparkles className="h-3 w-3 text-[#E17055]" />
                  {summary.model_used}
                </Badge>
              </div>
              <h2 className="text-lg font-extrabold tracking-tight sm:text-xl">
                Send This Master Summary to Your Inbox
              </h2>
              <p className="text-xs text-blue-100">
                Email a formatted HTML revision brief via Gmail SMTP, export Markdown, or print as PDF.
              </p>
            </div>

            <form
              onSubmit={handleSendEmail}
              className="flex flex-col gap-2 sm:flex-row sm:items-center"
            >
              <div className="relative">
                <Mail className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
                <input
                  type="email"
                  required
                  value={recipientEmail}
                  onChange={(e) => setRecipientEmail(e.target.value)}
                  placeholder="student@university.edu"
                  className="h-10 w-full rounded-lg border border-white/20 bg-white pl-9 pr-3 text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-[#E17055] sm:w-64"
                />
              </div>
              <Button
                type="submit"
                variant="accent"
                size="md"
                disabled={isSending || !recipientEmail.trim()}
                className="shrink-0 font-bold"
              >
                {isSending ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Sending...
                  </>
                ) : (
                  <>
                    <Send className="h-4 w-4" />
                    Email Summary to Me
                  </>
                )}
              </Button>
            </form>
          </div>

          <div className="mt-4 flex flex-wrap items-center justify-between gap-2 border-t border-white/15 pt-3">
            <div className="flex flex-wrap items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={handleDownloadMarkdown}
                className="border-white/25 bg-white/10 text-white hover:bg-white/20 hover:text-white"
              >
                <Download className="h-3.5 w-3.5" />
                Download Markdown
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => window.print()}
                className="border-white/25 bg-white/10 text-white hover:bg-white/20 hover:text-white"
              >
                <Printer className="h-3.5 w-3.5" />
                Download / Print PDF
              </Button>
            </div>

            <Button
              variant="outline"
              size="sm"
              onClick={onRegenerate}
              className="border-white/25 bg-white/10 text-white hover:bg-white/20 hover:text-white"
            >
              <RefreshCw className="h-3.5 w-3.5" />
              Regenerate Summary
            </Button>
          </div>

          {toast && (
            <div
              className={cn(
                "mt-3 flex items-center gap-2 rounded-lg border px-3.5 py-2.5 text-xs font-semibold",
                toast.type === "success"
                  ? "border-emerald-300 bg-emerald-50 text-emerald-900"
                  : "border-red-300 bg-red-50 text-red-900"
              )}
            >
              {toast.type === "success" ? (
                <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-600" />
              ) : (
                <XCircle className="h-4 w-4 shrink-0 text-red-600" />
              )}
              <span>{toast.message}</span>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Printable Master Summary Body */}
      <div className="print-cheat-sheet space-y-5">
        <NotesAudioPlayer
          text={summary.full_markdown}
          title={summary.subject_title}
        />

        {/* 2. Executive Subject Overview */}
        <Card className="border-[#1E3A8A]/15">
          <CardHeader className="pb-2">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <CardTitle className="text-xl text-[#1E3A8A]">
                {summary.subject_title}
              </CardTitle>
              <Badge tone="navy">Executive Overview</Badge>
            </div>
          </CardHeader>
          <CardContent>
            <p className="text-sm leading-relaxed text-slate-700">
              {summary.executive_overview}
            </p>
          </CardContent>
        </Card>

        {/* 3. Unit-by-Unit Keypoints Accordion/Cards */}
        <div className="space-y-3">
          <h3 className="text-base font-extrabold text-[#1E3A8A]">
            Unit-by-Unit Keypoints ({summary.unit_keypoints.length} Units)
          </h3>

          <div className="grid gap-4 md:grid-cols-2">
            {summary.unit_keypoints.map((uk, idx) => {
              const isCollapsed = !!collapsedUnits[idx];
              return (
                <Card key={idx} className="border-slate-200 bg-white">
                  <CardHeader className="border-b border-slate-100 py-3">
                    <button
                      type="button"
                      onClick={() =>
                        setCollapsedUnits((prev) => ({
                          ...prev,
                          [idx]: !prev[idx],
                        }))
                      }
                      className="flex w-full items-center justify-between gap-2 text-left"
                    >
                      <span className="text-sm font-bold text-[#1E3A8A]">
                        {uk.unit}
                      </span>
                      {isCollapsed ? (
                        <ChevronDown className="h-4 w-4 shrink-0 text-slate-400" />
                      ) : (
                        <ChevronUp className="h-4 w-4 shrink-0 text-slate-400" />
                      )}
                    </button>
                  </CardHeader>

                  {!isCollapsed && (
                    <CardContent className="space-y-3 pt-3.5">
                      {uk.key_concepts.length > 0 && (
                        <div>
                          <p className="text-[11px] font-bold uppercase tracking-wider text-slate-500">
                            Key Concepts
                          </p>
                          <ul className="mt-1.5 list-disc space-y-1 pl-4 text-xs leading-relaxed text-slate-700">
                            {uk.key_concepts.map((kc, kIdx) => (
                              <li key={kIdx}>{kc}</li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {uk.must_remember_formulas.length > 0 && (
                        <div>
                          <p className="text-[11px] font-bold uppercase tracking-wider text-slate-500">
                            Must-Remember Formulas &amp; Rules
                          </p>
                          <div className="mt-1.5 flex flex-wrap gap-1.5">
                            {uk.must_remember_formulas.map((fm, fIdx) => (
                              <span
                                key={fIdx}
                                className="rounded-md border border-[#C7D2FE] bg-[#EEF2FF] px-2 py-0.5 font-mono text-[11px] font-medium text-[#1E3A8A]"
                              >
                                {fm}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}

                      {uk.exam_tip && (
                        <div className="flex items-start gap-2 rounded-lg border border-[#FADFD7] bg-[#FDF3F0] px-3 py-2 text-xs text-[#9C3E27]">
                          <Lightbulb className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[#E17055]" />
                          <span>
                            <strong>Examiner Tip: </strong>
                            {uk.exam_tip}
                          </span>
                        </div>
                      )}
                    </CardContent>
                  )}
                </Card>
              );
            })}
          </div>
        </div>

        {/* 4. High-Probability Takeaways & Last 15-Minute Rapid Recall Checklist */}
        <div className="grid gap-5 lg:grid-cols-2">
          <Card className="border-[#1E3A8A]/15">
            <CardHeader className="pb-2">
              <CardTitle className="flex items-center gap-2 text-[#1E3A8A]">
                <Flame className="h-4 w-4 text-[#E17055]" />
                High-Probability Exam Takeaways
              </CardTitle>
            </CardHeader>
            <CardContent>
              <ul className="space-y-2">
                {summary.high_probability_takeaways.map((item, idx) => (
                  <li
                    key={idx}
                    className="flex items-start gap-2.5 rounded-lg border border-slate-100 bg-[#FFFCF5] p-2.5 text-xs leading-relaxed text-slate-800"
                  >
                    <span className="inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-[#1E3A8A] font-mono text-[10px] font-bold text-white">
                      {idx + 1}
                    </span>
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>

          <Card className="border-[#E17055]/30">
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between gap-2">
                <CardTitle className="flex items-center gap-2 text-[#1E3A8A]">
                  <CheckCircle2 className="h-4 w-4 text-[#E17055]" />
                  Last 15-Minute Rapid Recall Checklist
                </CardTitle>
                <Badge tone="coral">
                  {doneChecklist}/{totalChecklist} Checked
                </Badge>
              </div>
            </CardHeader>
            <CardContent className="space-y-2">
              {summary.last_15_min_checklist.map((item, idx) => {
                const checked = checkedRecall.has(idx);
                return (
                  <label
                    key={idx}
                    className={cn(
                      "flex cursor-pointer items-start gap-2.5 rounded-lg border px-3 py-2.5 text-xs transition-colors",
                      checked
                        ? "border-emerald-200 bg-emerald-50/60 text-slate-500 line-through"
                        : "border-slate-200 bg-white text-slate-800 hover:bg-[#FFFCF5]"
                    )}
                  >
                    <Checkbox
                      checked={checked}
                      onCheckedChange={() => toggleRecallItem(idx)}
                      className="mt-0.5"
                    />
                    <span className="leading-relaxed">{item}</span>
                  </label>
                );
              })}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
