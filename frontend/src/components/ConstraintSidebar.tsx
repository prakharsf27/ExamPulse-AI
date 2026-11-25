"use client";

import React, { useMemo, useState } from "react";
import {
  ArrowRight,
  Calculator,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Clock,
  Layers,
  Lightbulb,
  Loader2,
  Search,
  Zap,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Checkbox, Slider } from "@/components/ui/controls";
import { cn } from "@/lib/utils";
import type { LearningStyle, ParsedSyllabus } from "@/types/exampulse";

interface ConstraintSidebarProps {
  syllabus: ParsedSyllabus;
  knownTopics: Set<string>;
  onToggleTopic: (topic: string) => void;
  onBulkCheck: (topics: string[], known: boolean) => void;
  hoursRemaining: number;
  onChangeHours: (hours: number) => void;
  learningStyle: LearningStyle;
  onChangeLearningStyle: (style: LearningStyle) => void;
  onPrioritize: () => void;
  isPrioritizing: boolean;
}

const STYLE_OPTIONS: {
  id: LearningStyle;
  label: string;
  desc: string;
  icon: React.ComponentType<{ className?: string }>;
}[] = [
  {
    id: "Crash Course",
    label: "Crash Course",
    desc: "Fast formulas & high-yield exam bullets",
    icon: Zap,
  },
  {
    id: "Conceptual",
    label: "Conceptual",
    desc: "Intuition, definitions & theory comparisons",
    icon: Lightbulb,
  },
  {
    id: "Numerical-Heavy",
    label: "Numerical-Heavy",
    desc: "Equations & step-by-step solved problems",
    icon: Calculator,
  },
];

export function ConstraintSidebar({
  syllabus,
  knownTopics,
  onToggleTopic,
  onBulkCheck,
  hoursRemaining,
  onChangeHours,
  learningStyle,
  onChangeLearningStyle,
  onPrioritize,
  isPrioritizing,
}: ConstraintSidebarProps) {
  const [filterText, setFilterText] = useState("");
  const [collapsedUnits, setCollapsedUnits] = useState<Set<string>>(new Set());

  const allTopics = useMemo(
    () => syllabus.units.flatMap((u) => u.topics),
    [syllabus]
  );
  const totalCount = allTopics.length;
  const knownCount = allTopics.filter((t) => knownTopics.has(t)).length;
  const uncheckedCount = totalCount - knownCount;
  const masteryPct = totalCount > 0 ? Math.round((knownCount / totalCount) * 100) : 0;

  const toggleUnitCollapse = (unitKey: string) => {
    setCollapsedUnits((prev) => {
      const next = new Set(prev);
      if (next.has(unitKey)) next.delete(unitKey);
      else next.add(unitKey);
      return next;
    });
  };

  return (
    <div className="mx-auto max-w-6xl space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-200 bg-white px-5 py-3.5 shadow-sm">
        <div>
          <h2 className="text-lg font-extrabold text-[#1E3A8A]">
            Step 2: Configure Constraints &amp; Syllabus Mastery
          </h2>
          <p className="text-xs text-slate-500">
            Set your available hours, pick your study depth, and check off topics you already know.
          </p>
        </div>
        <Badge tone="navy">
          {uncheckedCount} of {totalCount} topics queued for study
        </Badge>
      </div>

      <div className="grid gap-6 lg:grid-cols-12">
        {/* Left Column: Exam Constraints */}
        <div className="lg:col-span-5">
          <Card className="border-[#1E3A8A]/15">
            <CardHeader className="pb-2">
              <CardTitle className="flex items-center justify-between text-[#1E3A8A]">
                <span className="flex items-center gap-2">
                  <Clock className="h-4 w-4 text-[#E17055]" />
                  Exam Constraints
                </span>
                <Badge tone="coral">{hoursRemaining} hrs left</Badge>
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-5">
              <div>
                <div className="mb-1 flex items-center justify-between text-xs font-medium text-slate-600">
                  <span>Hours Remaining Before Exam</span>
                  <span className="font-mono font-bold text-[#1E3A8A]">
                    {hoursRemaining.toFixed(1)}h / 24h
                  </span>
                </div>
                <Slider
                  min={1}
                  max={24}
                  step={0.5}
                  value={[hoursRemaining]}
                  onValueChange={(vals) => onChangeHours(vals[0] ?? 8)}
                  aria-label="Hours remaining before exam"
                />
                <div className="mt-1.5 flex justify-between gap-2">
                  {[3, 6, 12, 18].map((preset) => (
                    <button
                      key={preset}
                      type="button"
                      onClick={() => onChangeHours(preset)}
                      className={cn(
                        "flex-1 rounded-md border py-1 text-xs font-semibold transition-colors",
                        hoursRemaining === preset
                          ? "border-[#1E3A8A] bg-[#EEF2FF] text-[#1E3A8A]"
                          : "border-slate-200 bg-slate-50 text-slate-600 hover:bg-slate-100"
                      )}
                    >
                      {preset}h
                    </button>
                  ))}
                </div>
              </div>

              <div className="space-y-2">
                <label className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Learning Depth
                </label>
                <div className="grid gap-2.5">
                  {STYLE_OPTIONS.map((opt) => {
                    const Icon = opt.icon;
                    const active = learningStyle === opt.id;
                    return (
                      <button
                        key={opt.id}
                        type="button"
                        onClick={() => onChangeLearningStyle(opt.id)}
                        className={cn(
                          "flex items-start gap-2.5 rounded-xl border p-3 text-left transition-all",
                          active
                            ? "border-[#1E3A8A] bg-[#EEF2FF]/70 shadow-sm"
                            : "border-slate-200 bg-white hover:border-slate-300"
                        )}
                      >
                        <Icon
                          className={cn(
                            "mt-0.5 h-4 w-4 shrink-0",
                            active ? "text-[#E17055]" : "text-slate-400"
                          )}
                        />
                        <div>
                          <div
                            className={cn(
                              "text-sm font-bold",
                              active ? "text-[#1E3A8A]" : "text-slate-800"
                            )}
                          >
                            {opt.label}
                          </div>
                          <div className="text-xs text-slate-500">{opt.desc}</div>
                        </div>
                      </button>
                    );
                  })}
                </div>
              </div>

              <Button
                variant="accent"
                size="lg"
                className="w-full font-bold"
                disabled={uncheckedCount === 0 || isPrioritizing}
                onClick={onPrioritize}
              >
                {isPrioritizing ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Mapping PYQ Weightage...
                  </>
                ) : (
                  <>
                    Generate Priority Study Plan ({uncheckedCount})
                    <ArrowRight className="h-4 w-4" />
                  </>
                )}
              </Button>
            </CardContent>
          </Card>
        </div>

        {/* Right Column: Interactive Syllabus Checklist */}
        <div className="lg:col-span-7">
          <Card className="h-full border-[#1E3A8A]/15">
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between gap-2">
                <CardTitle className="flex items-center gap-2 text-[#1E3A8A]">
                  <Layers className="h-4 w-4 text-[#E17055]" />
                  Interactive Syllabus Checklist
                </CardTitle>
                <Badge tone="emerald">{masteryPct}% Already Known</Badge>
              </div>
              <p className="text-xs text-slate-500">
                Check off topics you have mastered. Unchecked topics will be ranked by PYQ recurrence.
              </p>
              <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-slate-100">
                <div
                  className="h-full rounded-full bg-emerald-500 transition-all duration-300"
                  style={{ width: `${masteryPct}%` }}
                />
              </div>
            </CardHeader>

            <CardContent className="space-y-3">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="relative min-w-[200px] flex-1">
                  <Search className="pointer-events-none absolute left-2.5 top-2.5 h-3.5 w-3.5 text-slate-400" />
                  <input
                    type="text"
                    value={filterText}
                    onChange={(e) => setFilterText(e.target.value)}
                    placeholder="Filter syllabus topics..."
                    className="w-full rounded-lg border border-slate-200 bg-[#FFFCF5] py-1.5 pl-8 pr-3 text-xs text-slate-800 placeholder:text-slate-400 focus:border-[#1E3A8A] focus:outline-none"
                  />
                </div>
                <div className="flex items-center gap-3 text-xs">
                  <button
                    type="button"
                    onClick={() => onBulkCheck(allTopics, false)}
                    className="font-semibold text-[#1E3A8A] hover:underline"
                  >
                    Study All ({totalCount})
                  </button>
                  <span className="text-slate-300">|</span>
                  <button
                    type="button"
                    onClick={() => onBulkCheck(allTopics, true)}
                    className="font-medium text-slate-500 hover:text-slate-800"
                  >
                    Mark All Known
                  </button>
                </div>
              </div>

              <div className="max-h-[440px] space-y-2.5 overflow-y-auto pr-1">
                {syllabus.units.map((unit) => {
                  const unitKey = `${unit.unit_number}-${unit.unit_title}`;
                  const isCollapsed = collapsedUnits.has(unitKey);
                  const visibleTopics = unit.topics.filter((t) =>
                    t.toLowerCase().includes(filterText.trim().toLowerCase())
                  );
                  if (filterText && visibleTopics.length === 0) return null;

                  return (
                    <div
                      key={unitKey}
                      className="rounded-xl border border-slate-200/90 bg-[#FFFCF5] p-3"
                    >
                      <button
                        type="button"
                        onClick={() => toggleUnitCollapse(unitKey)}
                        className="flex w-full items-center justify-between gap-2 text-left"
                      >
                        <span className="text-xs font-bold text-[#1E3A8A]">
                          {unit.unit_number}: {unit.unit_title}
                        </span>
                        {isCollapsed ? (
                          <ChevronRight className="h-4 w-4 shrink-0 text-slate-400" />
                        ) : (
                          <ChevronDown className="h-4 w-4 shrink-0 text-slate-400" />
                        )}
                      </button>

                      {!isCollapsed && (
                        <div className="mt-2.5 space-y-1.5">
                          {visibleTopics.map((topic) => {
                            const checked = knownTopics.has(topic);
                            return (
                              <label
                                key={topic}
                                className={cn(
                                  "flex cursor-pointer items-start gap-2.5 rounded-lg px-2 py-1.5 text-xs transition-colors hover:bg-white",
                                  checked ? "text-slate-400" : "text-slate-800"
                                )}
                              >
                                <Checkbox
                                  checked={checked}
                                  onCheckedChange={() => onToggleTopic(topic)}
                                  className="mt-0.5"
                                />
                                <span
                                  className={cn(
                                    "flex-1 leading-snug",
                                    checked && "line-through"
                                  )}
                                >
                                  {topic}
                                </span>
                                {checked && (
                                  <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-emerald-500" />
                                )}
                              </label>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
