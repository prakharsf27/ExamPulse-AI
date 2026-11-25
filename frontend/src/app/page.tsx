"use client";

import React, { useEffect, useState } from "react";
import {
  Activity,
  Database,
  GraduationCap,
  RotateCcw,
  Sparkles,
} from "lucide-react";
import { UploadPanel } from "@/components/UploadPanel";
import { ConstraintSidebar } from "@/components/ConstraintSidebar";
import { PriorityStudyMap } from "@/components/PriorityStudyMap";
import { StudyWorkspace } from "@/components/StudyWorkspace";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  fetchBackendHealth,
  generateStudyPack,
  ingestStudyFiles,
  loadDemoSession,
  prioritizeStudyPlan,
} from "@/lib/api";
import type {
  BackendHealth,
  IngestResponse,
  LearningStyle,
  PrioritizeResponse,
  StudyPackResponse,
} from "@/types/exampulse";

export default function ExamPulsePage() {
  const [health, setHealth] = useState<BackendHealth | null>(null);
  const [session, setSession] = useState<IngestResponse | null>(null);
  const [knownTopics, setKnownTopics] = useState<Set<string>>(new Set());
  const [hoursRemaining, setHoursRemaining] = useState<number>(8);
  const [learningStyle, setLearningStyle] = useState<LearningStyle>("Numerical-Heavy");

  const [priorityPlan, setPriorityPlan] = useState<PrioritizeResponse | null>(null);
  const [selectedTopic, setSelectedTopic] = useState<string | null>(null);
  const [studyPackCache, setStudyPackCache] = useState<Record<string, StudyPackResponse>>({});

  const [isIngesting, setIsIngesting] = useState(false);
  const [loadingLabel, setLoadingLabel] = useState("");
  const [isPrioritizing, setIsPrioritizing] = useState(false);
  const [loadingTopicPack, setLoadingTopicPack] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchBackendHealth()
      .then(setHealth)
      .catch(() => setHealth(null));
  }, []);

  const runPrioritizeAndSelectFirst = async (
    sess: IngestResponse,
    known: Set<string>,
    hours: number,
    style: LearningStyle
  ) => {
    const unchecked = sess.syllabus.units
      .flatMap((u) => u.topics)
      .filter((t) => !known.has(t));

    if (unchecked.length === 0) {
      setError("All topics are marked as known! Uncheck at least one topic to generate a study plan.");
      return;
    }

    setError(null);
    setIsPrioritizing(true);
    try {
      const plan = await prioritizeStudyPlan({
        session_id: sess.session_id,
        unchecked_topics: unchecked,
        hours_remaining: hours,
        learning_style: style,
      });
      setPriorityPlan(plan);
      if (plan.prioritized_topics.length > 0) {
        const topTopic = plan.prioritized_topics[0].topic;
        await handleSelectTopic(topTopic, sess.session_id, hours, style);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to prioritize topics.");
    } finally {
      setIsPrioritizing(false);
    }
  };

  const handleIngest = async (syllabusPdf: File, pyqPdfs: File[]) => {
    setError(null);
    setIsIngesting(true);
    setLoadingLabel("Extracting PDFs & indexing into Qdrant...");
    try {
      const res = await ingestStudyFiles(syllabusPdf, pyqPdfs);
      setSession(res);
      setKnownTopics(new Set());
      setPriorityPlan(null);
      setSelectedTopic(null);
      setStudyPackCache({});
      await runPrioritizeAndSelectFirst(res, new Set(), hoursRemaining, learningStyle);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to ingest uploaded PDFs.");
    } finally {
      setIsIngesting(false);
      setLoadingLabel("");
    }
  };

  const handleLoadDemo = async () => {
    setError(null);
    setIsIngesting(true);
    setLoadingLabel("Loading Operating Systems demo...");
    try {
      const res = await loadDemoSession();
      const preChecked = new Set<string>();
      const firstTopic = res.syllabus.units[0]?.topics[0];
      if (firstTopic) preChecked.add(firstTopic);

      setSession(res);
      setKnownTopics(preChecked);
      setPriorityPlan(null);
      setSelectedTopic(null);
      setStudyPackCache({});
      await runPrioritizeAndSelectFirst(res, preChecked, hoursRemaining, learningStyle);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Could not reach backend API. Ensure FastAPI is running on port 8000."
      );
    } finally {
      setIsIngesting(false);
      setLoadingLabel("");
    }
  };

  const handleSelectTopic = async (
    topic: string,
    overrideSessionId?: string,
    overrideHours?: number,
    overrideStyle?: LearningStyle,
    forceRefresh = false
  ) => {
    const sid = overrideSessionId || session?.session_id;
    if (!sid) return;
    const hrs = overrideHours ?? hoursRemaining;
    const sty = overrideStyle ?? learningStyle;
    const cacheKey = `${sid}::${topic}::${sty}::${hrs}`;

    setSelectedTopic(topic);
    if (!forceRefresh && studyPackCache[cacheKey]) {
      return;
    }

    setError(null);
    setLoadingTopicPack(topic);
    try {
      const pack = await generateStudyPack({
        session_id: sid,
        topic,
        hours_remaining: hrs,
        learning_style: sty,
      });
      setStudyPackCache((prev) => ({ ...prev, [cacheKey]: pack }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to generate study pack.");
    } finally {
      setLoadingTopicPack(null);
    }
  };

  const handleToggleTopic = (topic: string) => {
    setKnownTopics((prev) => {
      const next = new Set(prev);
      if (next.has(topic)) next.delete(topic);
      else next.add(topic);
      return next;
    });
  };

  const handleBulkCheck = (topics: string[], known: boolean) => {
    setKnownTopics(known ? new Set(topics) : new Set());
  };

  const handleReset = () => {
    setSession(null);
    setKnownTopics(new Set());
    setPriorityPlan(null);
    setSelectedTopic(null);
    setStudyPackCache({});
    setError(null);
  };

  const activeCacheKey =
    session && selectedTopic
      ? `${session.session_id}::${selectedTopic}::${learningStyle}::${hoursRemaining}`
      : null;
  const activeStudyPack = activeCacheKey ? studyPackCache[activeCacheKey] ?? null : null;

  return (
    <div className="min-h-screen bg-[#FFFCF5]">
      {/* Top Academic Header */}
      <header className="no-print sticky top-0 z-30 border-b border-slate-200/80 bg-white/90 backdrop-blur-md">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-3 sm:px-6">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#1E3A8A] text-white shadow-sm">
              <GraduationCap className="h-5 w-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-lg font-extrabold tracking-tight text-[#1E3A8A]">
                  ExamPulse
                </span>
                <span className="rounded-md bg-[#FDF3F0] px-1.5 py-0.5 font-mono text-xs font-bold text-[#E17055]">
                  AI
                </span>
              </div>
              <p className="text-[11px] font-medium text-slate-500">
                Syllabus-Grounded Agentic RAG Companion
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {session && (
              <Badge tone="navy" className="max-w-xs truncate">
                {session.syllabus.course_title}
              </Badge>
            )}
            {health ? (
              <div className="hidden items-center gap-1.5 md:flex">
                <Badge tone="emerald">
                  <Activity className="h-3 w-3" />
                  API Online
                </Badge>
                <Badge tone="slate">
                  <Database className="h-3 w-3" />
                  Qdrant: {health.qdrant_mode}
                </Badge>
                <Badge tone={health.gemini_configured ? "navy" : "amber"}>
                  <Sparkles className="h-3 w-3" />
                  {health.gemini_configured ? "Gemini Live" : "Local Fallback Mode"}
                </Badge>
              </div>
            ) : (
              <Badge tone="coral">Backend Offline (Start :8000)</Badge>
            )}

            {session && (
              <Button variant="outline" size="sm" onClick={handleReset}>
                <RotateCcw className="h-3.5 w-3.5" />
                New Session
              </Button>
            )}
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6">
        {!session ? (
          <UploadPanel
            onIngest={handleIngest}
            onLoadDemo={handleLoadDemo}
            isLoading={isIngesting}
            loadingLabel={loadingLabel}
            error={error}
          />
        ) : (
          <div className="grid gap-6 lg:grid-cols-12">
            {/* Left Sidebar */}
            <div className="lg:col-span-4 xl:col-span-3">
              <ConstraintSidebar
                syllabus={session.syllabus}
                knownTopics={knownTopics}
                onToggleTopic={handleToggleTopic}
                onBulkCheck={handleBulkCheck}
                hoursRemaining={hoursRemaining}
                onChangeHours={setHoursRemaining}
                learningStyle={learningStyle}
                onChangeLearningStyle={setLearningStyle}
                onPrioritize={() =>
                  runPrioritizeAndSelectFirst(
                    session,
                    knownTopics,
                    hoursRemaining,
                    learningStyle
                  )
                }
                isPrioritizing={isPrioritizing}
              />
            </div>

            {/* Right Main Study Workspace */}
            <div className="space-y-6 lg:col-span-8 xl:col-span-9">
              {error && (
                <div className="no-print rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm font-medium text-red-800">
                  {error}
                </div>
              )}

              {priorityPlan && (
                <PriorityStudyMap
                  plan={priorityPlan}
                  selectedTopic={selectedTopic}
                  onSelectTopic={(topic) => handleSelectTopic(topic)}
                  isGeneratingTopic={loadingTopicPack}
                />
              )}

              <StudyWorkspace
                studyPack={activeStudyPack}
                isLoading={loadingTopicPack !== null}
                loadingTopic={loadingTopicPack}
                onRegenerate={(topic) =>
                  handleSelectTopic(topic, undefined, undefined, undefined, true)
                }
              />
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
