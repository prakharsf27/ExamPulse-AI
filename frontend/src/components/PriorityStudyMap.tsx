"use client";

import React, { useState } from "react";
import {
  ArrowLeft,
  ArrowRight,
  BarChart3,
  ChevronDown,
  ChevronUp,
  Clock,
  FileSearch,
  Flame,
  Loader2,
  TrendingUp,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import type { PrioritizeResponse, PriorityTier } from "@/types/exampulse";

interface PriorityStudyMapProps {
  plan: PrioritizeResponse;
  selectedTopic: string | null;
  onSelectTopic: (topic: string) => void;
  onEditConstraints: () => void;
  onOpenSubjectSummary: () => void;
  isGeneratingTopic: string | null;
  isGeneratingSummary?: boolean;
}

function tierTone(tier: PriorityTier): "coral" | "navy" | "amber" | "slate" {
  switch (tier) {
    case "Critical":
      return "coral";
    case "High":
      return "navy";
    case "Medium":
      return "amber";
    default:
      return "slate";
  }
}

export function PriorityStudyMap({
  plan,
  selectedTopic,
  onSelectTopic,
  onEditConstraints,
  onOpenSubjectSummary,
  isGeneratingTopic,
  isGeneratingSummary = false,
}: PriorityStudyMapProps) {
  const [expandedPyq, setExpandedPyq] = useState<string | null>(null);
  const [showAllTopics, setShowAllTopics] = useState(false);

  const visibleTopics = showAllTopics
    ? plan.prioritized_topics
    : plan.prioritized_topics.slice(0, 8);
  const hiddenCount = Math.max(0, plan.prioritized_topics.length - 8);

  return (
    <div className="mx-auto max-w-6xl space-y-5">
      {/* Compact Top Summary Bar */}
      <Card className="border-[#1E3A8A]/15">
        <CardHeader className="py-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="space-y-1">
              <div className="flex flex-wrap items-center gap-2">
                <CardTitle className="flex items-center gap-2 text-lg text-[#1E3A8A]">
                  <TrendingUp className="h-5 w-5 text-[#E17055]" />
                  AI Priority Study Map
                </CardTitle>
                <Badge tone="navy">{plan.learning_style}</Badge>
                <Badge tone="coral">{plan.hours_remaining}h Budget</Badge>
              </div>
              <p className="text-xs text-slate-600">{plan.strategy_note}</p>
            </div>

            <div className="flex flex-wrap items-center gap-2 shrink-0">
              <Button
                variant="outline"
                size="sm"
                onClick={onEditConstraints}
              >
                <ArrowLeft className="h-3.5 w-3.5" />
                Edit Constraints
              </Button>
              <Button
                variant="primary"
                size="sm"
                disabled={isGeneratingSummary}
                onClick={onOpenSubjectSummary}
              >
                {isGeneratingSummary ? (
                  <>
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    Building Summary...
                  </>
                ) : (
                  <>
                    Finish &amp; View Full Subject Summary
                    <ArrowRight className="h-3.5 w-3.5" />
                  </>
                )}
              </Button>
            </div>
          </div>
        </CardHeader>
      </Card>

      {/* PYQ Weightage & Time Allocation Visual Chart */}
      {plan.prioritized_topics.length > 0 && (
        <Card className="border-[#1E3A8A]/15 bg-white">
          <CardHeader className="border-b border-slate-100 py-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <CardTitle className="flex items-center gap-2 text-sm text-[#1E3A8A]">
                <BarChart3 className="h-4 w-4 text-[#E17055]" />
                PYQ Weightage &amp; Time Allocation Chart (Top Topics)
              </CardTitle>
              <div className="flex items-center gap-4 text-[11px] font-semibold text-slate-600">
                <span className="flex items-center gap-1.5">
                  <span className="h-2.5 w-2.5 rounded-sm bg-[#E17055]" />
                  PYQ Recurrence
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="h-2.5 w-2.5 rounded-sm bg-[#1E3A8A]" />
                  Allocated Hours
                </span>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-2.5 py-4">
            {(() => {
              const chartTopics = plan.prioritized_topics.slice(0, 6);
              const maxFreq = Math.max(
                1,
                ...chartTopics.map((t) => t.pyq_frequency)
              );
              const maxHours = Math.max(
                0.5,
                ...chartTopics.map((t) => t.allocated_hours)
              );

              return chartTopics.map((t) => {
                const freqPct = Math.round((t.pyq_frequency / maxFreq) * 100);
                const hrsPct = Math.round((t.allocated_hours / maxHours) * 100);
                return (
                  <button
                    key={t.topic}
                    type="button"
                    disabled={isGeneratingTopic !== null}
                    onClick={() => onSelectTopic(t.topic)}
                    className="grid w-full grid-cols-12 items-center gap-3 rounded-lg px-2 py-1.5 text-left transition-colors hover:bg-[#FFFCF5]"
                  >
                    <div className="col-span-12 truncate text-xs font-semibold text-slate-800 sm:col-span-5">
                      <span className="mr-1.5 font-mono text-[11px] font-bold text-[#1E3A8A]">
                        #{t.priority_rank}
                      </span>
                      {t.topic}
                    </div>
                    <div className="col-span-9 space-y-1 sm:col-span-5">
                      <div className="h-2 w-full overflow-hidden rounded-full bg-slate-100">
                        <div
                          className="h-full rounded-full bg-[#E17055] transition-all"
                          style={{ width: `${Math.max(freqPct, 6)}%` }}
                        />
                      </div>
                      <div className="h-2 w-full overflow-hidden rounded-full bg-slate-100">
                        <div
                          className="h-full rounded-full bg-[#1E3A8A] transition-all"
                          style={{ width: `${Math.max(hrsPct, 8)}%` }}
                        />
                      </div>
                    </div>
                    <div className="col-span-3 text-right font-mono text-[11px] sm:col-span-2">
                      <span className="font-bold text-[#C85A40]">
                        {t.pyq_frequency}x
                      </span>{" "}
                      <span className="text-slate-400">·</span>{" "}
                      <span className="font-bold text-[#1E3A8A]">
                        {t.allocated_hours}h
                      </span>
                    </div>
                  </button>
                );
              });
            })()}
          </CardContent>
        </Card>
      )}

      {/* Clean 2-Column Ranked Topic Grid */}
      <div className="grid gap-4 md:grid-cols-2">
        {visibleTopics.map((item) => {
          const isSelected = selectedTopic === item.topic;
          const isLoading = isGeneratingTopic === item.topic;
          const isExpanded = expandedPyq === item.topic;
          const pct = Math.min(100, Math.round(item.relevance_score * 100));

          return (
            <Card
              key={item.topic}
              className={cn(
                "flex flex-col justify-between transition-all",
                isSelected
                  ? "border-[#1E3A8A] bg-[#EEF2FF]/35 ring-1 ring-[#1E3A8A]"
                  : "border-slate-200 bg-white hover:border-[#1E3A8A]/40"
              )}
            >
              <CardContent className="flex flex-1 flex-col justify-between p-4">
                <div className="space-y-2.5">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex flex-wrap items-center gap-1.5">
                      <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-[#1E3A8A] font-mono text-xs font-bold text-white">
                        #{item.priority_rank}
                      </span>
                      <Badge tone={tierTone(item.priority_tier)}>
                        {item.priority_tier === "Critical" && (
                          <Flame className="h-3 w-3" />
                        )}
                        {item.priority_tier}
                      </Badge>
                      <Badge tone={item.pyq_frequency > 0 ? "emerald" : "slate"}>
                        Asked {item.pyq_frequency}x in PYQs
                      </Badge>
                    </div>

                    <div className="flex items-center gap-1 rounded-md border border-slate-200 bg-[#FFFCF5] px-2.5 py-1 text-xs font-bold text-[#1E3A8A]">
                      <Clock className="h-3 w-3 text-[#E17055]" />
                      {item.allocated_hours}h
                    </div>
                  </div>

                  <div>
                    <p className="text-[11px] font-medium text-slate-500">
                      {item.unit_title}
                    </p>
                    <h4 className="mt-0.5 text-sm font-bold text-slate-900">
                      {item.topic}
                    </h4>
                  </div>

                  <p className="text-xs leading-relaxed text-slate-600">
                    {item.rationale}
                  </p>
                </div>

                <div className="mt-4 space-y-2.5 border-t border-slate-100 pt-3">
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex items-center gap-2">
                      <div className="h-1.5 w-24 overflow-hidden rounded-full bg-slate-200">
                        <div
                          className="h-full rounded-full bg-[#E17055]"
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                      <span className="font-mono text-[11px] text-slate-500">
                        {pct}% match
                      </span>
                    </div>

                    <Button
                      variant={isSelected ? "primary" : "accent"}
                      size="sm"
                      disabled={isGeneratingTopic !== null}
                      onClick={() => onSelectTopic(item.topic)}
                    >
                      {isLoading ? (
                        <>
                          <Loader2 className="h-3.5 w-3.5 animate-spin" />
                          Generating...
                        </>
                      ) : (
                        <>
                          Open Study Pack
                          <ArrowRight className="h-3.5 w-3.5" />
                        </>
                      )}
                    </Button>
                  </div>

                  {item.matched_pyqs.length > 0 && (
                    <div>
                      <button
                        type="button"
                        onClick={() =>
                          setExpandedPyq(isExpanded ? null : item.topic)
                        }
                        className="flex items-center gap-1.5 text-[11px] font-semibold text-[#1E3A8A] hover:underline"
                      >
                        <FileSearch className="h-3.5 w-3.5 text-[#E17055]" />
                        {isExpanded ? "Hide" : "Preview"} {item.matched_pyqs.length} Matched PYQ(s)
                        {isExpanded ? (
                          <ChevronUp className="h-3 w-3" />
                        ) : (
                          <ChevronDown className="h-3 w-3" />
                        )}
                      </button>

                      {isExpanded && (
                        <div className="mt-2 space-y-1.5">
                          {item.matched_pyqs.map((m, idx) => (
                            <div
                              key={idx}
                              className="rounded-lg border border-slate-200 bg-[#FFFCF5] p-2 text-[11px] text-slate-700"
                            >
                              <div className="mb-0.5 flex items-center justify-between font-mono font-semibold text-[#1E3A8A]">
                                <span>{m.source_file}</span>
                                <span>Score: {m.relevance_score}</span>
                              </div>
                              <p className="leading-relaxed">{m.question_snippet}</p>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {hiddenCount > 0 && (
        <div className="flex justify-center">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setShowAllTopics((v) => !v)}
          >
            {showAllTopics
              ? "Show Top 8 High-Yield Topics"
              : `Show All ${plan.prioritized_topics.length} Topics (+${hiddenCount} lower-priority)`}
          </Button>
        </div>
      )}
    </div>
  );
}
