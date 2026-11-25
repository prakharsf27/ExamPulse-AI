"use client";

import React, { useEffect } from "react";
import {
  BookOpen,
  Clock,
  FolderOpen,
  History,
  Layers,
  Trash2,
  X,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { StudyHistoryEntry } from "@/types/exampulse";

interface StudyHistoryDrawerProps {
  open: boolean;
  entries: StudyHistoryEntry[];
  onClose: () => void;
  onOpenEntry: (entry: StudyHistoryEntry) => void;
  onDeleteEntry: (id: string) => void;
  onClearAll: () => void;
}

function formatSavedDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

export function StudyHistoryDrawer({
  open,
  entries,
  onClose,
  onOpenEntry,
  onDeleteEntry,
  onClearAll,
}: StudyHistoryDrawerProps) {
  useEffect(() => {
    if (!open) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="no-print fixed inset-0 z-50 flex justify-end">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-slate-900/40 backdrop-blur-[1px] transition-opacity"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Slide-Over Panel */}
      <aside
        role="dialog"
        aria-label="Study History"
        className="relative z-10 flex h-full w-full max-w-md flex-col border-l border-slate-200 bg-[#FFFCF5] shadow-2xl"
      >
        <div className="flex items-center justify-between border-b border-slate-200 bg-white px-5 py-4">
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[#1E3A8A] text-white">
              <History className="h-4 w-4" />
            </div>
            <div>
              <h2 className="text-base font-extrabold text-[#1E3A8A]">
                Study History ({entries.length})
              </h2>
              <p className="text-[11px] text-slate-500">
                Saved offline in your browser
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
            aria-label="Close history drawer"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="flex-1 space-y-3 overflow-y-auto p-4">
          {entries.length === 0 ? (
            <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-slate-300 bg-white px-6 py-14 text-center">
              <BookOpen className="h-8 w-8 text-[#1E3A8A]/40" />
              <p className="mt-3 text-sm font-bold text-slate-800">
                No saved summaries yet
              </p>
              <p className="mt-1 text-xs text-slate-500">
                Generate a Full Subject Summary in Step 5 and it will automatically be
                saved here for offline review.
              </p>
            </div>
          ) : (
            entries.map((entry) => (
              <div
                key={entry.id}
                className="rounded-xl border border-slate-200 bg-white p-4 shadow-2xs transition-colors hover:border-[#1E3A8A]/30"
              >
                <div className="flex items-start justify-between gap-2">
                  <h3 className="text-sm font-bold text-[#1E3A8A] leading-snug">
                    {entry.subjectTitle}
                  </h3>
                  <span className="shrink-0 font-mono text-[10px] text-slate-400">
                    {formatSavedDate(entry.timestamp)}
                  </span>
                </div>

                <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
                  <Badge tone="navy">
                    <Layers className="h-3 w-3" />
                    {entry.unitsCount} Units
                  </Badge>
                  <Badge tone="coral">
                    <Clock className="h-3 w-3" />
                    {entry.hoursBudget}h
                  </Badge>
                  <Badge tone="slate">{entry.learningStyle}</Badge>
                </div>

                <div className="mt-3.5 flex items-center gap-2 border-t border-slate-100 pt-3">
                  <Button
                    type="button"
                    variant="primary"
                    size="sm"
                    className="flex-1"
                    onClick={() => onOpenEntry(entry)}
                  >
                    <FolderOpen className="h-3.5 w-3.5" />
                    Open Summary
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => onDeleteEntry(entry.id)}
                    aria-label={`Delete ${entry.subjectTitle}`}
                    className="text-red-600 hover:border-red-200 hover:bg-red-50 hover:text-red-700"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                    Delete
                  </Button>
                </div>
              </div>
            ))
          )}
        </div>

        {entries.length > 0 && (
          <div className="flex items-center justify-between border-t border-slate-200 bg-white px-5 py-3">
            <span className="text-xs text-slate-500">
              Stored in <code className="font-mono">localStorage</code>
            </span>
            <button
              type="button"
              onClick={onClearAll}
              className="text-xs font-semibold text-red-600 hover:underline"
            >
              Clear All
            </button>
          </div>
        )}
      </aside>
    </div>
  );
}
