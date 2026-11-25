"use client";

import React from "react";
import {
  Check,
  FileUp,
  ListOrdered,
  Loader2,
  SlidersHorizontal,
  Sparkles,
} from "lucide-react";
import { cn } from "@/lib/utils";

export type WorkflowStageId = 1 | 2 | 3 | 4;

interface WorkflowProgressBarProps {
  activeStep: WorkflowStageId;
  completedSteps: Set<WorkflowStageId>;
  busyStep: WorkflowStageId | null;
  onSelectStep: (step: WorkflowStageId) => void;
  stepMeta?: Partial<Record<WorkflowStageId, string>>;
}

const STEPS: {
  id: WorkflowStageId;
  label: string;
  subtitle: string;
  icon: React.ComponentType<{ className?: string }>;
}[] = [
  {
    id: 1,
    label: "1. Upload & Ingest",
    subtitle: "Syllabus + PYQs",
    icon: FileUp,
  },
  {
    id: 2,
    label: "2. Constraints & Mastery",
    subtitle: "Hours & Checklist",
    icon: SlidersHorizontal,
  },
  {
    id: 3,
    label: "3. Priority Study Map",
    subtitle: "PYQ Weightage Rank",
    icon: ListOrdered,
  },
  {
    id: 4,
    label: "4. Study Workspace",
    subtitle: "Notes, Quiz & Sheet",
    icon: Sparkles,
  },
];

export function WorkflowProgressBar({
  activeStep,
  completedSteps,
  busyStep,
  onSelectStep,
  stepMeta,
}: WorkflowProgressBarProps) {
  return (
    <div className="no-print sticky top-[65px] z-20 mb-6 rounded-2xl border border-[#1E3A8A]/15 bg-white/95 p-3 shadow-sm backdrop-blur-md">
      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
        {STEPS.map((step, idx) => {
          const Icon = step.icon;
          const isCompleted = completedSteps.has(step.id);
          const isBusy = busyStep === step.id;
          const isActive = activeStep === step.id;
          const clickable = isCompleted || isActive;

          return (
            <button
              key={step.id}
              type="button"
              disabled={!clickable}
              onClick={() => clickable && onSelectStep(step.id)}
              className={cn(
                "relative flex items-center gap-3 rounded-xl border px-3 py-2 text-left transition-all",
                isBusy
                  ? "border-[#E17055] bg-[#FDF3F0] ring-1 ring-[#E17055]"
                  : isActive
                  ? "border-[#1E3A8A] bg-[#EEF2FF] ring-2 ring-[#1E3A8A]/25"
                  : isCompleted
                  ? "border-emerald-200 bg-emerald-50/50 hover:border-emerald-400"
                  : "cursor-not-allowed border-slate-200 bg-[#FFFCF5] opacity-55"
              )}
            >
              <div
                className={cn(
                  "flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-xs font-bold",
                  isBusy
                    ? "bg-[#E17055] text-white"
                    : isActive
                    ? "bg-[#1E3A8A] text-white"
                    : isCompleted
                    ? "bg-emerald-600 text-white"
                    : "bg-slate-200 text-slate-600"
                )}
              >
                {isBusy ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : isCompleted && !isActive ? (
                  <Check className="h-4 w-4 stroke-[2.5]" />
                ) : (
                  <Icon className="h-4 w-4" />
                )}
              </div>

              <div className="min-w-0 flex-1">
                <div
                  className={cn(
                    "truncate text-xs font-bold",
                    isActive ? "text-[#1E3A8A]" : "text-slate-900"
                  )}
                >
                  {step.label}
                </div>
                <div className="truncate text-[11px] text-slate-500">
                  {stepMeta?.[step.id] || step.subtitle}
                </div>
              </div>

              {idx < STEPS.length - 1 && (
                <span className="hidden text-slate-300 lg:inline">→</span>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}
