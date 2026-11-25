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
import { SubjectSummaryView } from "@/components/SubjectSummaryView";
import {
  WorkflowProgressBar,
  type WorkflowStageId,
} from "@/components/WorkflowProgressBar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  fetchBackendHealth,
  generateStudyPack,
  generateSubjectSummary,
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
  SubjectSummaryResponse,
} from "@/types/exampulse";

export default function ExamPulsePage() {
  const [health, setHealth] = useState<BackendHealth | null>(null);
  const [activeStep, setActiveStep] = useState<WorkflowStageId>(1);
  const [session, setSession] = useState<IngestResponse | null>(null);
  const [knownTopics, setKnownTopics] = useState<Set<string>>(new Set());
  const [hoursRemaining, setHoursRemaining] = useState<number>(8);
  const [learningStyle, setLearningStyle] = useState<LearningStyle>("Numerical-Heavy");

  const [priorityPlan, setPriorityPlan] = useState<PrioritizeResponse | null>(null);
  const [selectedTopic, setSelectedTopic] = useState<string | null>(null);
  const [studyPackCache, setStudyPackCache] = useState<Record<string, StudyPackResponse>>({});
  const [subjectSummary, setSubjectSummary] = useState<SubjectSummaryResponse | null>(null);
  const [traceDrawerOpen, setTraceDrawerOpen] = useState<boolean>(false);

  const [isIngesting, setIsIngesting] = useState(false);
  const [loadingLabel, setLoadingLabel] = useState("");
  const [isPrioritizing, setIsPrioritizing] = useState(false);
  const [loadingTopicPack, setLoadingTopicPack] = useState<string | null>(null);
  const [isGeneratingSummary, setIsGeneratingSummary] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchBackendHealth()
      .then(setHealth)
      .catch(() => setHealth(null));
  }, []);

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
      setSubjectSummary(null);
      setActiveStep(2);
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
      setSubjectSummary(null);
      setActiveStep(2);
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

  const handlePrioritize = async () => {
    if (!session) return;
    const unchecked = session.syllabus.units
      .flatMap((u) => u.topics)
      .filter((t) => !knownTopics.has(t));

    if (unchecked.length === 0) {
      setError(
        "All topics are marked as known! Uncheck at least one topic to generate a study plan."
      );
      return;
    }

    setError(null);
    setIsPrioritizing(true);
    try {
      const plan = await prioritizeStudyPlan({
        session_id: session.session_id,
        unchecked_topics: unchecked,
        hours_remaining: hoursRemaining,
        learning_style: learningStyle,
      });
      setPriorityPlan(plan);
      setActiveStep(3);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to prioritize topics.");
    } finally {
      setIsPrioritizing(false);
    }
  };

  const handleOpenStudyPack = async (topic: string, forceRefresh = false) => {
    if (!session) return;
    const cacheKey = `${session.session_id}::${topic}::${learningStyle}::${hoursRemaining}`;

    setSelectedTopic(topic);
    setTraceDrawerOpen(false);
    setActiveStep(4);

    if (!forceRefresh && studyPackCache[cacheKey]) {
      return;
    }

    setError(null);
    setLoadingTopicPack(topic);
    try {
      const pack = await generateStudyPack({
        session_id: session.session_id,
        topic,
        hours_remaining: hoursRemaining,
        learning_style: learningStyle,
      });
      setStudyPackCache((prev) => ({ ...prev, [cacheKey]: pack }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to generate study pack.");
    } finally {
      setLoadingTopicPack(null);
    }
  };

  const handleOpenSubjectSummary = async (forceRefresh = false) => {
    if (!session) return;
    setActiveStep(5);
    if (!forceRefresh && subjectSummary && subjectSummary.session_id === session.session_id) {
      return;
    }

    setError(null);
    setIsGeneratingSummary(true);
    try {
      const res = await generateSubjectSummary({
        session_id: session.session_id,
        learning_style: learningStyle,
        hours_remaining: hoursRemaining,
      });
      setSubjectSummary(res);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to generate subject summary."
      );
    } finally {
      setIsGeneratingSummary(false);
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
    setSubjectSummary(null);
    setTraceDrawerOpen(false);
    setError(null);
    setActiveStep(1);
  };

  const activeCacheKey =
    session && selectedTopic
      ? `${session.session_id}::${selectedTopic}::${learningStyle}::${hoursRemaining}`
      : null;
  const activeStudyPack = activeCacheKey ? studyPackCache[activeCacheKey] ?? null : null;

  const completedSteps = new Set<WorkflowStageId>();
  if (session) completedSteps.add(1);
  if (priorityPlan) completedSteps.add(2);
  if (priorityPlan && (activeStudyPack || selectedTopic || subjectSummary)) {
    completedSteps.add(3);
  }
  if (activeStudyPack) completedSteps.add(4);
  if (subjectSummary) completedSteps.add(5);

  let busyStep: WorkflowStageId | null = null;
  if (isIngesting) busyStep = 1;
  else if (isPrioritizing) busyStep = 2;
  else if (loadingTopicPack) busyStep = 4;
  else if (isGeneratingSummary) busyStep = 5;

  const stepMeta: Partial<Record<WorkflowStageId, string>> = {
    1: session
      ? `${session.stats.syllabus_chunks} syl + ${session.stats.pyq_chunks} PYQ chunks`
      : "Syllabus + PYQs",
    2: session
      ? `${hoursRemaining}h · ${learningStyle}`
      : "Hours & Checklist",
    3: priorityPlan
      ? `${priorityPlan.prioritized_topics.length} topics ranked`
      : "PYQ Weightage Rank",
    4: activeStudyPack
      ? `${activeStudyPack.notes_model || activeStudyPack.generation_mode}`
      : "Notes, Quiz & Sheet",
    5: subjectSummary
      ? `${subjectSummary.unit_keypoints.length} units summarized`
      : "Master Brief & SMTP",
  };

  return (
    <div className="min-h-screen bg-[#FFFCF5]">
      {/* Top Academic Header */}
      <header className="no-print sticky top-0 z-30 border-b border-slate-200/80 bg-white/95 backdrop-blur-md">
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
                  {health.gemini_configured ? "gemini-3.5-flash-lite" : "Local Fallback"}
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

      <main className="mx-auto max-w-7xl px-4 py-5 sm:px-6">
        <WorkflowProgressBar
          activeStep={activeStep}
          completedSteps={completedSteps}
          busyStep={busyStep}
          onSelectStep={(step) => setActiveStep(step)}
          stepMeta={stepMeta}
        />

        {error && activeStep !== 1 && (
          <div className="no-print mx-auto mb-5 max-w-6xl rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm font-medium text-red-800">
            {error}
          </div>
        )}

        {/* Step 1: Upload & Ingest */}
        {activeStep === 1 && (
          <UploadPanel
            onIngest={handleIngest}
            onLoadDemo={handleLoadDemo}
            isLoading={isIngesting}
            loadingLabel={loadingLabel}
            error={error}
          />
        )}

        {/* Step 2: Configure Constraints & Mastery */}
        {activeStep === 2 && session && (
          <ConstraintSidebar
            syllabus={session.syllabus}
            knownTopics={knownTopics}
            onToggleTopic={handleToggleTopic}
            onBulkCheck={handleBulkCheck}
            hoursRemaining={hoursRemaining}
            onChangeHours={setHoursRemaining}
            learningStyle={learningStyle}
            onChangeLearningStyle={setLearningStyle}
            onPrioritize={handlePrioritize}
            isPrioritizing={isPrioritizing}
          />
        )}

        {/* Step 3: AI Priority Study Map */}
        {activeStep === 3 && priorityPlan && (
          <PriorityStudyMap
            plan={priorityPlan}
            selectedTopic={selectedTopic}
            onSelectTopic={(topic) => handleOpenStudyPack(topic)}
            onEditConstraints={() => setActiveStep(2)}
            onOpenSubjectSummary={() => handleOpenSubjectSummary()}
            isGeneratingTopic={loadingTopicPack}
            isGeneratingSummary={isGeneratingSummary}
          />
        )}

        {/* Step 4: Adaptive Study Workspace */}
        {activeStep === 4 && (
          <StudyWorkspace
            studyPack={activeStudyPack}
            isLoading={loadingTopicPack !== null}
            loadingTopic={loadingTopicPack}
            onRegenerate={(topic) => handleOpenStudyPack(topic, true)}
            onBackToPriority={() => setActiveStep(3)}
            onOpenSubjectSummary={() => handleOpenSubjectSummary()}
            isGeneratingSummary={isGeneratingSummary}
            traceDrawerOpen={traceDrawerOpen}
            onToggleTraceDrawer={setTraceDrawerOpen}
          />
        )}

        {/* Step 5: Final Subject Summary & Email */}
        {activeStep === 5 && (
          <SubjectSummaryView
            summary={subjectSummary}
            isLoading={isGeneratingSummary}
            onRegenerate={() => handleOpenSubjectSummary(true)}
            onBack={() => setActiveStep(selectedTopic ? 4 : 3)}
          />
        )}
      </main>
    </div>
  );
}
