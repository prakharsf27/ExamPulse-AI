"use client";

import React, { useState } from "react";
import {
  ArrowRight,
  ChevronDown,
  ChevronUp,
  Clock,
  FileSearch,
  Flame,
  TrendingUp,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import type { PrioritizeResponse, PriorityTier } from "@/types/exampulse";

interface PriorityStudyMapProps {
  plan: PrioritizeResponse;
  selectedTopic: string | null;
  onSelectTopic: (topic: string) => void;
  isGeneratingTopic: string | null;
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
  isGeneratingTopic,
}: PriorityStudyMapProps) {
  const [expandedPyq, setExpandedPyq] = useState<string | null>(null);

  return (
    <Card className="no-print border-[#1E3A8A]/15">
      <CardHeader className="border-b border-slate-100 pb-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <CardTitle className="flex items-center gap-2 text-lg text-[#1E3A8A]">
              <TrendingUp className="h-5 w-5 text-[#E17055]" />
              Priority Study Map
            </CardTitle>
            <p className="mt-1 text-xs text-slate-600">{plan.strategy_note}</p>
          </div>
          <div className="flex items-center gap-2">
            <Badge tone="navy">{plan.learning_style}</Badge>
            <Badge tone="coral">{plan.hours_remaining}h Budget</Badge>
          </div>
        </div>
      </CardHeader>

      <CardContent className="pt-4">
        <div className="space-y-3">
          {plan.prioritized_topics.map((item) => {
            const isSelected = selectedTopic === item.topic;
            const isLoading = isGeneratingTopic === item.topic;
            const isExpanded = expandedPyq === item.topic;
            const pct = Math.min(100, Math.round(item.relevance_score * 100));

            return (
              <div
                key={item.topic}
                className={cn(
                  "rounded-xl border transition-all",
                  isSelected
                    ? "border-[#1E3A8A] bg-[#EEF2FF]/50 ring-1 ring-[#1E3A8A]"
                    : "border-slate-200 bg-white hover:border-slate-300"
                )}
              >
                <div
                  role="button"
                  tabIndex={0}
                  onClick={() => onSelectTopic(item.topic)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      onSelectTopic(item.topic);
                    }
                  }}
                  className="flex cursor-pointer flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between"
                >
                  <div className="min-w-0 flex-1 space-y-1.5">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-[#1E3A8A] font-mono text-xs font-bold text-white">
                        #{item.priority_rank}
                      </span>
                      <Badge tone={tierTone(item.priority_tier)}>
                        {item.priority_tier === "Critical" && (
                          <Flame className="h-3 w-3" />
                        )}
                        {item.priority_tier} Priority
                      </Badge>
                      <Badge tone={item.pyq_frequency > 0 ? "emerald" : "slate"}>
                        Asked {item.pyq_frequency}x in PYQs
                      </Badge>
                      <span className="text-[11px] font-medium text-slate-500">
                        {item.unit_title}
                      </span>
                    </div>

                    <h4 className="text-sm font-bold text-slate-900 sm:text-base">
                      {item.topic}
                    </h4>
                    <p className="text-xs text-slate-600">{item.rationale}</p>

                    <div className="flex items-center gap-3 pt-1">
                      <div className="h-1.5 w-32 overflow-hidden rounded-full bg-slate-200">
                        <div
                          className="h-full rounded-full bg-[#E17055]"
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                      <span className="font-mono text-[11px] text-slate-500">
                        {pct}% PYQ match
                      </span>
                    </div>
                  </div>

                  <div className="flex shrink-0 items-center gap-3 sm:flex-col sm:items-end">
                    <div className="flex items-center gap-1.5 rounded-lg bg-[#FFFCF5] px-3 py-1.5 text-sm font-bold text-[#1E3A8A] border border-slate-200">
                      <Clock className="h-3.5 w-3.5 text-[#E17055]" />
                      {item.allocated_hours} hrs
                    </div>
                    <span className="inline-flex items-center gap-1 text-xs font-semibold text-[#E17055]">
                      {isLoading ? "Generating..." : isSelected ? "Active Pack" : "Open Study Pack"}
                      <ArrowRight className="h-3.5 w-3.5" />
                    </span>
                  </div>
                </div>

                {item.matched_pyqs.length > 0 && (
                  <div className="border-t border-slate-100 px-4 py-2">
                    <button
                      type="button"
                      onClick={() =>
                        setExpandedPyq(isExpanded ? null : item.topic)
                      }
                      className="flex items-center gap-1.5 text-xs font-semibold text-[#1E3A8A] hover:underline"
                    >
                      <FileSearch className="h-3.5 w-3.5 text-[#E17055]" />
                      {isExpanded ? "Hide" : "Preview"} {item.matched_pyqs.length} Matched PYQ Excerpt(s)
                      {isExpanded ? (
                        <ChevronUp className="h-3.5 w-3.5" />
                      ) : (
                        <ChevronDown className="h-3.5 w-3.5" />
                      )}
                    </button>

                    {isExpanded && (
                      <div className="mt-2 space-y-2 pb-1">
                        {item.matched_pyqs.map((m, idx) => (
                          <div
                            key={idx}
                            className="rounded-lg border border-slate-200 bg-[#FFFCF5] p-2.5 text-xs text-slate-700"
                          >
                            <div className="mb-1 flex items-center justify-between font-mono text-[11px] font-semibold text-[#1E3A8A]">
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
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}
