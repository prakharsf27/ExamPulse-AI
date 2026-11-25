import * as React from "react";
import { cn } from "@/lib/utils";

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  tone?: "navy" | "coral" | "amber" | "emerald" | "slate";
}

const TONE_MAP: Record<NonNullable<BadgeProps["tone"]>, string> = {
  navy: "bg-[#EEF2FF] text-[#1E3A8A] border-[#C7D2FE]",
  coral: "bg-[#FDF3F0] text-[#C85A40] border-[#FADFD7]",
  amber: "bg-amber-50 text-amber-800 border-amber-200",
  emerald: "bg-emerald-50 text-emerald-800 border-emerald-200",
  slate: "bg-slate-100 text-slate-700 border-slate-200",
};

export function Badge({ className, tone = "slate", ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-semibold",
        TONE_MAP[tone],
        className
      )}
      {...props}
    />
  );
}
