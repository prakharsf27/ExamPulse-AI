"use client";

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Pause,
  Play,
  SkipBack,
  SkipForward,
  Square,
  Volume2,
  VolumeX,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface NotesAudioPlayerProps {
  text: string;
  title?: string;
}

/** Convert Markdown + inline math into clean, natural-sounding spoken sentences. */
function markdownToSpeechChunks(markdown: string): string[] {
  const cleaned = markdown
    // Remove fenced code blocks' backticks while preserving content
    .replace(/```[\w-]*\n([\s\S]*?)```/g, "$1")
    // Convert markdown links [label](url) -> label
    .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
    // Strip table separator rows like |---|---|
    .replace(/^\s*\|?(?:\s*:?-+:?\s*\|)+\s*$/gm, "")
    // Replace pipes in markdown tables with natural pauses
    .replace(/\|/g, ", ")
    // Convert headings into clear spoken pauses
    .replace(/^#{1,6}\s+(.+)$/gm, "$1.")
    // Remove bullet / checkbox markers
    .replace(/^\s*[-*•]\s*(?:\[[ xX]\]\s*)?/gm, "")
    .replace(/^\s*\d+\.\s+/gm, "")
    // Strip emphasis/code markers
    .replace(/[*_`~]/g, "")
    // Make basic math symbols readable
    .replace(/\$\$([\s\S]*?)\$\$/g, "$1")
    .replace(/\$([^$]+)\$/g, "$1")
    .replace(/\\text\{([^}]+)\}/g, "$1")
    .replace(/\\frac\{([^}]+)\}\{([^}]+)\}/g, "$1 divided by $2")
    .replace(/\\leq|<=|≤/g, " less than or equal to ")
    .replace(/\\geq|>=|≥/g, " greater than or equal to ")
    .replace(/->|→/g, " leads to ")
    .replace(/\s+/g, " ")
    .trim();

  if (!cleaned) return [];

  // Split into sentence chunks (~240 chars max) so browser SpeechSynthesis never truncates
  const sentences = cleaned.split(/(?<=[.!?])\s+/);
  const chunks: string[] = [];
  let current = "";

  for (const s of sentences) {
    const trimmed = s.trim();
    if (!trimmed) continue;
    if ((current + " " + trimmed).trim().length <= 240) {
      current = (current ? current + " " : "") + trimmed;
    } else {
      if (current) chunks.push(current);
      if (trimmed.length <= 240) {
        current = trimmed;
      } else {
        // Split very long sentences by comma/clause
        const parts = trimmed.split(/(?<=[,;:])\s+/);
        let buf = "";
        for (const p of parts) {
          if ((buf + " " + p).trim().length <= 240) {
            buf = (buf ? buf + " " : "") + p;
          } else {
            if (buf) chunks.push(buf);
            buf = p.slice(0, 240);
          }
        }
        current = buf;
      }
    }
  }
  if (current) chunks.push(current);
  return chunks;
}

const SPEED_OPTIONS = [0.9, 1.0, 1.25, 1.5];

export function NotesAudioPlayer({ text, title }: NotesAudioPlayerProps) {
  const [supported, setSupported] = useState(true);
  const [voices, setVoices] = useState<SpeechSynthesisVoice[]>([]);
  const [selectedVoiceUri, setSelectedVoiceUri] = useState<string>("");
  const [rate, setRate] = useState<number>(1.0);
  const [status, setStatus] = useState<"idle" | "playing" | "paused">("idle");
  const [chunkIndex, setChunkIndex] = useState<number>(0);

  const chunks = useMemo(() => markdownToSpeechChunks(text), [text]);
  const activeRunIdRef = useRef<number>(0);
  const statusRef = useRef<"idle" | "playing" | "paused">("idle");
  const rateRef = useRef<number>(rate);
  const voiceRef = useRef<string>(selectedVoiceUri);

  rateRef.current = rate;
  voiceRef.current = selectedVoiceUri;
  statusRef.current = status;

  useEffect(() => {
    if (typeof window === "undefined" || !("speechSynthesis" in window)) {
      setSupported(false);
      return;
    }

    const loadVoices = () => {
      const all = window.speechSynthesis.getVoices();
      const english = all.filter((v) => v.lang.toLowerCase().startsWith("en"));
      const list = english.length > 0 ? english : all;
      setVoices(list);
      if (list.length > 0 && !voiceRef.current) {
        const preferred =
          list.find((v) =>
            /samantha|google us english|daniel|karen|alex/i.test(v.name)
          ) || list[0];
        setSelectedVoiceUri(preferred.voiceURI);
      }
    };

    loadVoices();
    window.speechSynthesis.onvoiceschanged = loadVoices;

    return () => {
      activeRunIdRef.current += 1;
      window.speechSynthesis.cancel();
      window.speechSynthesis.onvoiceschanged = null;
    };
  }, []);

  // Stop speech if the underlying note text changes
  useEffect(() => {
    if (typeof window !== "undefined" && "speechSynthesis" in window) {
      activeRunIdRef.current += 1;
      window.speechSynthesis.cancel();
    }
    setStatus("idle");
    setChunkIndex(0);
  }, [text]);

  const speakFrom = useCallback(
    (startIdx: number) => {
      if (
        typeof window === "undefined" ||
        !("speechSynthesis" in window) ||
        chunks.length === 0
      ) {
        return;
      }

      const runId = ++activeRunIdRef.current;
      window.speechSynthesis.cancel();

      const safeStart = Math.max(0, Math.min(startIdx, chunks.length - 1));
      setStatus("playing");
      setChunkIndex(safeStart);

      const speakNext = (idx: number) => {
        if (activeRunIdRef.current !== runId) return;
        if (idx >= chunks.length) {
          setStatus("idle");
          setChunkIndex(0);
          return;
        }

        setChunkIndex(idx);
        const utter = new SpeechSynthesisUtterance(chunks[idx]);
        utter.rate = rateRef.current;
        const chosenVoice = voices.find((v) => v.voiceURI === voiceRef.current);
        if (chosenVoice) utter.voice = chosenVoice;

        utter.onend = () => {
          if (activeRunIdRef.current !== runId) return;
          speakNext(idx + 1);
        };

        utter.onerror = (ev) => {
          if (activeRunIdRef.current !== runId) return;
          if (ev.error === "canceled" || ev.error === "interrupted") return;
          speakNext(idx + 1);
        };

        window.speechSynthesis.speak(utter);
      };

      speakNext(safeStart);
    },
    [chunks, voices]
  );

  const handlePlayPause = () => {
    if (!supported || chunks.length === 0) return;

    if (status === "idle") {
      speakFrom(chunkIndex);
    } else if (status === "playing") {
      window.speechSynthesis.pause();
      setStatus("paused");
    } else if (status === "paused") {
      window.speechSynthesis.resume();
      setStatus("playing");
    }
  };

  const handleStop = () => {
    if (!supported) return;
    activeRunIdRef.current += 1;
    window.speechSynthesis.cancel();
    setStatus("idle");
    setChunkIndex(0);
  };

  const handleChangeSpeed = (nextRate: number) => {
    setRate(nextRate);
    rateRef.current = nextRate;
    if (statusRef.current === "playing") {
      speakFrom(chunkIndex);
    }
  };

  if (!supported) {
    return (
      <div className="no-print mb-4 flex items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-4 py-2.5 text-xs text-slate-500">
        <VolumeX className="h-4 w-4" />
        Audio read-aloud is not supported in this browser.
      </div>
    );
  }

  const progressPct =
    chunks.length > 0
      ? Math.round(((chunkIndex + (status === "playing" ? 1 : 0)) / chunks.length) * 100)
      : 0;

  return (
    <div className="no-print mb-4 rounded-xl border border-[#1E3A8A]/20 bg-gradient-to-r from-[#EEF2FF]/70 via-white to-[#FDF3F0]/70 p-3.5 shadow-2xs">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-[#1E3A8A] text-white">
            <Volume2 className="h-4 w-4" />
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold text-[#1E3A8A]">
                Listen to Notes (Audio Mode)
              </span>
              {status !== "idle" && (
                <Badge tone={status === "playing" ? "coral" : "amber"}>
                  {status === "playing" ? "Speaking" : "Paused"} · {chunkIndex + 1}/
                  {chunks.length}
                </Badge>
              )}
            </div>
            <p className="truncate text-[11px] text-slate-500">
              {title
                ? `Hands-free audio walkthrough for ${title}`
                : "Hear these syllabus-grounded notes read aloud"}
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-1.5">
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={chunks.length === 0 || chunkIndex === 0}
            onClick={() => speakFrom(Math.max(0, chunkIndex - 1))}
            aria-label="Previous section"
            className="h-8 w-8 p-0"
          >
            <SkipBack className="h-3.5 w-3.5" />
          </Button>

          <Button
            type="button"
            variant={status === "playing" ? "accent" : "primary"}
            size="sm"
            disabled={chunks.length === 0}
            onClick={handlePlayPause}
            className="h-8 px-3 text-xs font-bold"
          >
            {status === "playing" ? (
              <>
                <Pause className="h-3.5 w-3.5" />
                Pause
              </>
            ) : status === "paused" ? (
              <>
                <Play className="h-3.5 w-3.5" />
                Resume
              </>
            ) : (
              <>
                <Play className="h-3.5 w-3.5" />
                Listen
              </>
            )}
          </Button>

          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={chunks.length === 0 || chunkIndex >= chunks.length - 1}
            onClick={() => speakFrom(Math.min(chunks.length - 1, chunkIndex + 1))}
            aria-label="Next section"
            className="h-8 w-8 p-0"
          >
            <SkipForward className="h-3.5 w-3.5" />
          </Button>

          {status !== "idle" && (
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={handleStop}
              aria-label="Stop audio"
              className="h-8 px-2.5 text-xs"
            >
              <Square className="h-3 w-3" />
              Stop
            </Button>
          )}

          <div className="ml-1 flex items-center rounded-lg border border-slate-200 bg-white p-0.5">
            {SPEED_OPTIONS.map((spd) => (
              <button
                key={spd}
                type="button"
                onClick={() => handleChangeSpeed(spd)}
                className={cn(
                  "rounded-md px-1.5 py-0.5 font-mono text-[10px] font-bold transition-colors",
                  rate === spd
                    ? "bg-[#1E3A8A] text-white"
                    : "text-slate-600 hover:bg-slate-100"
                )}
              >
                {spd}x
              </button>
            ))}
          </div>

          {voices.length > 0 && (
            <select
              value={selectedVoiceUri}
              onChange={(e) => {
                setSelectedVoiceUri(e.target.value);
                voiceRef.current = e.target.value;
                if (statusRef.current === "playing") speakFrom(chunkIndex);
              }}
              aria-label="Select voice"
              className="hidden h-8 max-w-[140px] rounded-lg border border-slate-200 bg-white px-2 text-[11px] text-slate-700 focus:border-[#1E3A8A] focus:outline-none md:block"
            >
              {voices.slice(0, 12).map((v) => (
                <option key={v.voiceURI} value={v.voiceURI}>
                  {v.name}
                </option>
              ))}
            </select>
          )}
        </div>
      </div>

      {status !== "idle" && (
        <div className="mt-2.5 space-y-1">
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-200">
            <div
              className="h-full rounded-full bg-[#E17055] transition-all duration-300"
              style={{ width: `${progressPct}%` }}
            />
          </div>
          <p className="line-clamp-1 text-[11px] italic text-slate-600">
            &ldquo;{chunks[chunkIndex]}&rdquo;
          </p>
        </div>
      )}
    </div>
  );
}
