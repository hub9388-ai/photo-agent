"use client"

import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { Info, ShieldAlert } from "lucide-react"
import {
  DemoFallbackBanner,
  GrowthChart,
  LearningEmptyState,
  LearningHeader,
  LocalRecoveryBanner,
  PhotoFeedbackList,
  PracticeErrorState,
  PracticeReviewProgress,
  PracticeTaskList,
  PracticeUploadDialog,
  SkillRadar,
} from "@/components/learning"
import { createJob, getJobResults, getLearningProfile, listJobs, subscribeJobEvents, uploadMedia } from "@/lib/api"
import {
  attemptFromCoachFeedbackJob,
  buildPracticeTasks,
  buildSkillScores,
  buildWeeklyScores,
  compactSentence,
  hasUsableCoachPayload,
  mapCoachToPhotoEvaluation,
} from "@/lib/learning/adapters"
import {
  demoAttemptResult,
  demoLearningBanner,
  demoPhotoEvaluations,
  demoPracticeTasks,
  demoSkillScores,
  demoWeeklyScores,
} from "@/lib/learning/demo"
import { clearPracticeRecovery, loadPracticeRecovery, savePracticeRecovery } from "@/lib/learning/storage"
import type { AgentEventMessage, AgentResultResponse, LearningProfileResponse } from "@/types/api"
import type {
  CoachHistoryItem,
  LearningFallbackReason,
  LearningIssue,
  PracticeAttempt,
  PracticeRecoveryRecord,
  PracticeTask,
} from "@/types/learning"
import { DEMO_MODE } from "@/lib/demo/config"

const ENABLE_DEMO_FALLBACK = !DEMO_MODE && process.env.NEXT_PUBLIC_ENABLE_DEMO_FALLBACK !== "false"
const COACH_TIMEOUT_MS = 1000 * 90

function buildLearningIssue(
  code: LearningIssue["code"],
  overrides?: Partial<LearningIssue>
): LearningIssue {
  const base: Record<LearningIssue["code"], LearningIssue> = {
    upload_failed: {
      code: "upload_failed",
      title: "练习照片上传失败",
      message: "请检查图片格式和大小后重试。支持 JPG / PNG / HEIC / RAW。",
      retryLabel: "重新上传",
    },
    create_job_failed: {
      code: "create_job_failed",
      title: "练习复盘任务创建失败",
      message: "照片已上传，但未能启动学习教练复盘。你可以基于已上传照片重新创建任务。",
      retryLabel: "重新创建任务",
    },
    coach_timeout: {
      code: "coach_timeout",
      title: "学习教练响应超时",
      message: "你的练习照片已保存，可以稍后重试 CoachAgent。",
      retryLabel: "重试复盘",
    },
    coach_failed: {
      code: "coach_failed",
      title: "学习教练暂时没有完成复盘",
      message: "你的练习照片已保存，可以稍后重试 CoachAgent，或查看示例复盘。",
      retryLabel: "重试复盘",
    },
    result_missing: {
      code: "result_missing",
      title: "练习结果暂不可用",
      message: "任务已完成，但没有读取到 CoachAgent 结果。可以稍后刷新或重试复盘。",
      retryLabel: "重试复盘",
    },
    archive_failed: {
      code: "archive_failed",
      title: "复盘已完成，但归档到练习任务失败",
      message: "你仍可以查看本次复盘结果，并稍后重新归档。",
      retryLabel: "重新归档",
    },
    task_missing: {
      code: "task_missing",
      title: "练习任务不存在或已被清理",
      message: "你可以返回学习页，或从历史反馈中重新生成练习任务。",
    },
    history_failed: {
      code: "history_failed",
      title: "练习记录加载失败",
      message: "你可以重试加载，或查看示例练习任务。",
      retryLabel: "重试加载",
    },
    payload_incomplete: {
      code: "payload_incomplete",
      title: "本次复盘结果为文本反馈",
      message: "CoachAgent 未包含完整结构化评分，页面已使用 visible_text 兜底展示。",
    },
  }
  return { ...base[code], ...overrides }
}

function toAttemptStatus(result?: AgentResultResponse): PracticeAttempt["status"] {
  if (!result) return "failed"
  if (result.status !== "succeeded") return "failed"
  const text = `${result.summary} ${result.visibleText}`
  if (/未完成|需复练|还需要|不足|失败/.test(text)) return "needs_retry"
  return "completed"
}

function dateKey(value?: string) {
  if (!value) return null
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return null
  return date.toISOString().slice(0, 10)
}

function countLearningStreak(values: Array<string | undefined>) {
  const keys = Array.from(new Set(values.map(dateKey).filter(Boolean) as string[])).sort().reverse()
  if (!keys.length) return 0

  let streak = 1
  let cursor = new Date(`${keys[0]}T00:00:00.000Z`).getTime()
  for (const key of keys.slice(1)) {
    const next = new Date(`${key}T00:00:00.000Z`).getTime()
    const diffDays = Math.round((cursor - next) / 86400000)
    if (diffDays !== 1) break
    streak += 1
    cursor = next
  }
  return streak
}

function levelFromCompletedCount(count: number) {
  if (count >= 20) return "Lv.5"
  if (count >= 10) return "Lv.4"
  if (count >= 4) return "Lv.3"
  if (count >= 1) return "Lv.2"
  return "Lv.1"
}

export default function LearningPage() {
  const subscriptionsRef = useRef<Record<string, () => void>>({})
  const timeoutRef = useRef<Record<string, ReturnType<typeof setTimeout>>>({})
  const [coachHistory, setCoachHistory] = useState<CoachHistoryItem[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [notice, setNotice] = useState<string | null>(null)
  const [fallbackReason, setFallbackReason] = useState<LearningFallbackReason>("none")
  const [practiceAttempts, setPracticeAttempts] = useState<Record<string, PracticeAttempt[]>>({})
  const [learningProfile, setLearningProfile] = useState<LearningProfileResponse | null>(null)
  const [uploadingTaskId, setUploadingTaskId] = useState<string | null>(null)
  const [selectedTask, setSelectedTask] = useState<PracticeTask | null>(null)
  const [dialogError, setDialogError] = useState<string | null>(null)
  const [issue, setIssue] = useState<LearningIssue | null>(null)
  const [recovery, setRecovery] = useState<PracticeRecoveryRecord | null>(() => loadPracticeRecovery())
  const [forceDemo, setForceDemo] = useState(false)
  const [claimedTasks, setClaimedTasks] = useState<string[]>([])

  const clearAttemptRuntime = useCallback((attemptId: string) => {
    subscriptionsRef.current[attemptId]?.()
    delete subscriptionsRef.current[attemptId]
    if (timeoutRef.current[attemptId]) {
      clearTimeout(timeoutRef.current[attemptId])
      delete timeoutRef.current[attemptId]
    }
  }, [])

  const updateAttempt = useCallback((taskId: string, attemptId: string, patch: Partial<PracticeAttempt>) => {
    setPracticeAttempts((current) => ({
      ...current,
      [taskId]: (current[taskId] || []).map((attempt) =>
        attempt.attemptId === attemptId ? { ...attempt, ...patch } : attempt
      ),
    }))
  }, [])

  const archiveAttempt = useCallback((taskId: string, attempt: PracticeAttempt) => {
    try {
      setPracticeAttempts((current) => {
        const existing = current[taskId] || []
        const next = existing.some((item) => item.attemptId === attempt.attemptId)
          ? existing.map((item) => (item.attemptId === attempt.attemptId ? attempt : item))
          : [attempt, ...existing]
        return { ...current, [taskId]: next }
      })
      return true
    } catch {
      setIssue(buildLearningIssue("archive_failed", { taskId, jobId: attempt.jobId, mediaId: attempt.mediaId }))
      return false
    }
  }, [])

  const loadLearningData = useCallback(async () => {
    let nextFallback: LearningFallbackReason = "none"
    try {
      setIsLoading(true)
      setNotice(null)
      setIssue(null)
      const [jobs, profile] = await Promise.all([
        listJobs(),
        getLearningProfile().catch(() => null),
      ])
      setLearningProfile(profile)
      const photoReviewJobs = jobs
        .filter((job) => job.type === "photo_review" && job.agents.includes("coach"))
        .slice(0, 12)

      if (!photoReviewJobs.length) {
        setCoachHistory([])
        setFallbackReason("empty_history")
        setNotice("还没有学习记录。完成一次照片分析后，学习教练会自动沉淀优点、问题和练习任务。")
        return
      }

      const settledResults = await Promise.allSettled(
        photoReviewJobs.map(async (job) => {
          const response = await getJobResults(job.jobId)
          const coachResult = response.results.find(
            (result) => result.agent === "coach" && result.status === "succeeded"
          )
          return coachResult ? { job, result: coachResult } : null
        })
      )

      const loadedHistory = settledResults
        .flatMap((settled) => (settled.status === "fulfilled" && settled.value ? [settled.value] : []))
        .sort((a, b) => new Date(b.job.updatedAt).getTime() - new Date(a.job.updatedAt).getTime())

      if (!loadedHistory.length) {
        setCoachHistory([])
        setFallbackReason("empty_coach_results")
        setNotice("历史任务中暂时没有可用的 Coach 结果。当前使用示例学习数据。")
        return
      }

      const usableHistory = loadedHistory.filter((item) => hasUsableCoachPayload(item.result))
      setCoachHistory(usableHistory.length ? usableHistory : loadedHistory.slice(0, 1))

      const coachFeedbackJobs = jobs.filter(
        (job) =>
          job.type === "coach_feedback" &&
          job.agents.includes("coach") &&
          typeof job.context.practice_task_id === "string"
      )
      const settledAttempts = await Promise.allSettled(
        coachFeedbackJobs.map(async (job) => {
          const response = await getJobResults(job.jobId)
          const coachResult = response.results.find((result) => result.agent === "coach")
          return attemptFromCoachFeedbackJob(job, coachResult)
        })
      )
      const attemptsByTask = settledAttempts.reduce<Record<string, PracticeAttempt[]>>((acc, settled) => {
        if (settled.status !== "fulfilled" || !settled.value) return acc
        const { taskId, attempt } = settled.value
        acc[taskId] = [attempt, ...(acc[taskId] || [])]
        return acc
      }, {})
      if (Object.keys(attemptsByTask).length) {
        setPracticeAttempts(attemptsByTask)
      }

      if (!usableHistory.length) {
        nextFallback = "missing_payload"
        setNotice("最近的 Coach 结果缺少结构化字段，已使用文本结果展示，练习任务会按规则兜底生成。")
        setIssue(buildLearningIssue("payload_incomplete"))
      } else if (usableHistory.length < 3) {
        nextFallback = "insufficient_data"
        setNotice("历史学习结果不足 3 次，已先用最近 Coach 反馈展示；完成 3 次分析后会生成更稳定的能力画像。")
      }
      setFallbackReason(nextFallback)
    } catch (error) {
      setCoachHistory([])
      setLearningProfile(null)
      setFallbackReason("api_error")
      setNotice(error instanceof Error ? `学习数据加载失败：${error.message}` : "学习数据加载失败。")
      setIssue(buildLearningIssue("history_failed"))
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    const loadTimer = window.setTimeout(() => {
      if (DEMO_MODE) { try { setClaimedTasks(JSON.parse(localStorage.getItem("photoai.demo.claimedTasks.v2") ?? "[]")) } catch { /* Keep the task list usable. */ } }
      void loadLearningData()
    }, 0)
    const activeSubscriptions = subscriptionsRef.current
    return () => {
      window.clearTimeout(loadTimer)
      Object.keys(activeSubscriptions).forEach(clearAttemptRuntime)
    }
  }, [clearAttemptRuntime, loadLearningData])

  const hasRealTasks = coachHistory.length > 0
  const shouldUseDemo = forceDemo || (ENABLE_DEMO_FALLBACK && !hasRealTasks)
  const photoEvaluations = useMemo(
    () => (hasRealTasks ? coachHistory.map(mapCoachToPhotoEvaluation).slice(0, 4) : DEMO_MODE ? [] : demoPhotoEvaluations),
    [coachHistory, hasRealTasks]
  )

  const practiceTasks = useMemo(() => {
    if (DEMO_MODE && !coachHistory.length) return []
    const sourceTasks = shouldUseDemo ? demoPracticeTasks : buildPracticeTasks(coachHistory)
    return sourceTasks.map((task) => {
      const attempts = practiceAttempts[task.id] || practiceAttempts[task.practice_task_id] || task.attempts || []
      const latestAttempt = attempts[0]
      if (!latestAttempt) return { ...task, attempts, ...(DEMO_MODE ? { status: claimedTasks.includes(task.id) ? "in_progress" as const : "not_started" as const, statusLabel: claimedTasks.includes(task.id) ? "已领取" : "未领取" } : {}) }
      const status =
        latestAttempt.status === "completed"
          ? "completed"
          : latestAttempt.status === "reviewing" ||
              latestAttempt.status === "job_created" ||
              latestAttempt.status === "uploading" ||
              latestAttempt.status === "uploaded"
            ? "in_progress"
            : latestAttempt.status === "archive_failed"
              ? "failed"
              : "needs_retry"
      const statusLabel =
        status === "completed" ? "已完成" : status === "in_progress" ? "练习中" : status === "failed" ? "归档失败" : "需复练"
      return { ...task, attempts, status, statusLabel } satisfies PracticeTask
    })
  }, [coachHistory, practiceAttempts, shouldUseDemo, claimedTasks])

  const skillScores = useMemo(() => (hasRealTasks ? buildSkillScores(coachHistory) : demoSkillScores), [coachHistory, hasRealTasks])
  const weeklyScores = useMemo(() => (hasRealTasks ? buildWeeklyScores(coachHistory) : demoWeeklyScores), [coachHistory, hasRealTasks])
  const completedPracticeTasks = practiceTasks.filter(
    (task) => !task.isDemo && task.attempts.some((attempt) => attempt.status === "completed" && !attempt.isDemo)
  ).length
  const learningActivityDates = [
    ...coachHistory.map((item) => item.job.updatedAt || item.job.createdAt),
    ...practiceTasks.flatMap((task) =>
      task.attempts
        .filter((attempt) => !attempt.isDemo)
        .map((attempt) => attempt.createdAt)
    ),
  ]
  const stats = {
    streak: learningProfile?.streakDays ?? (hasRealTasks ? countLearningStreak(learningActivityDates) : 0),
    completed: learningProfile?.completedPracticeTasks ?? completedPracticeTasks,
    level: learningProfile?.currentLevel ?? levelFromCompletedCount(completedPracticeTasks),
  }
  const skillSourceNote = shouldUseDemo
    ? "当前为示例技能画像；真实能力画像会在 Coach 历史反馈积累后生成。"
    : coachHistory.length < 3
      ? "基于 Coach 历史反馈估算，非完整能力测评；完成 3 次分析后可信度更高。"
      : "基于 Coach 历史反馈估算，非完整能力测评。"

  const watchPracticeJob = useCallback(
    (task: PracticeTask, attemptId: string, jobId: string, mediaId?: string, fileName?: string) => {
      clearAttemptRuntime(attemptId)
      timeoutRef.current[attemptId] = setTimeout(() => {
        updateAttempt(task.id, attemptId, {
          status: "needs_retry",
          feedbackSummary: "学习教练响应超时，可以稍后重试。",
        })
        setIssue(buildLearningIssue("coach_timeout", { taskId: task.id, jobId, mediaId }))
      }, COACH_TIMEOUT_MS)

      subscriptionsRef.current[attemptId] = subscribeJobEvents(jobId, {
        onEvent: async (event: AgentEventMessage) => {
          if (
            event.type !== "job.completed" &&
            event.type !== "job.partial_completed" &&
            event.type !== "job.failed"
          ) {
            return
          }
          try {
            const response = await getJobResults(jobId)
            const coachResult = response.results.find((result) => result.agent === "coach")
            if (!coachResult) {
              updateAttempt(task.id, attemptId, {
                status: "failed",
                feedbackSummary: "任务已完成，但没有读取到 CoachAgent 结果。",
              })
              setIssue(buildLearningIssue("result_missing", { taskId: task.id, jobId, mediaId }))
              return
            }
            const status = toAttemptStatus(coachResult)
            const summary =
              coachResult.summary ||
              coachResult.visibleText ||
              (status === "completed" ? "练习反馈已完成。" : "练习评估失败，可重新提交练习照片。")
            const archived = archiveAttempt(task.id, {
              attemptId,
              practice_task_id: task.practice_task_id,
              jobId,
              mediaId,
              fileName,
              status,
              feedbackSummary: compactSentence(summary, "练习反馈已完成。"),
              visibleText: coachResult.visibleText,
              structuredPayload: coachResult.structuredPayload,
              agentError: coachResult.agentError,
              createdAt: new Date().toISOString(),
            })
            if (archived) {
              clearPracticeRecovery()
              setRecovery(null)
              setNotice(status === "completed" ? "练习反馈已归档到对应任务下。" : "练习反馈已保存，建议复练。")
            }
          } catch (error) {
            updateAttempt(task.id, attemptId, {
              status: "failed",
              feedbackSummary: error instanceof Error ? error.message : "练习结果读取失败。",
            })
            setIssue(buildLearningIssue("result_missing", { taskId: task.id, jobId, mediaId }))
          } finally {
            clearAttemptRuntime(attemptId)
          }
        },
        onError: () => {
          updateAttempt(task.id, attemptId, {
            status: "reviewing",
            feedbackSummary: "SSE 连接中断，后台任务仍在运行，可稍后从历史记录查看。",
          })
        },
      })
    },
    [archiveAttempt, clearAttemptRuntime, updateAttempt]
  )

  const createPracticeJobFromMedia = useCallback(
    async (task: PracticeTask, mediaId: string, fileName?: string, attemptId = `attempt_${Date.now()}`) => {
      const goal = task.goal || task.description || task.target || "请评估这张练习照片是否完成练习目标"
      const createdJob = await createJob({
        type: "coach_feedback",
        agents: ["coach"],
        media_ids: [mediaId],
        user_goal: `请评估这张练习照片是否完成练习目标：${goal}。请判断是否完成、哪里进步了、还存在什么问题、下一步怎么练。`,
        context: {
          practice_task_id: task.practice_task_id,
          practice_goal: goal,
          source_job_id: task.sourceJobId,
          source_media_id: task.sourceMediaId,
          source_agent: "coach",
        },
      })

      archiveAttempt(task.id, {
        attemptId,
        practice_task_id: task.practice_task_id,
        jobId: createdJob.jobId,
        mediaId,
        fileName,
        status: "reviewing",
        feedbackSummary: "CoachAgent 正在评估练习照片...",
        createdAt: new Date().toISOString(),
      })
      savePracticeRecovery({
        practiceTaskId: task.practice_task_id,
        practiceGoal: goal,
        sourceJobId: task.sourceJobId,
        sourceMediaId: task.sourceMediaId,
        uploadedMediaId: mediaId,
        uploadedFileName: fileName,
        createdJobId: createdJob.jobId,
        attemptStatus: "reviewing",
        updatedAt: new Date().toISOString(),
      })
      setRecovery(loadPracticeRecovery())
      setNotice(`练习照片已提交，任务 ${createdJob.jobId} 正在运行。`)
      watchPracticeJob(task, attemptId, createdJob.jobId, mediaId, fileName)
    },
    [archiveAttempt, watchPracticeJob]
  )

  const handleUploadPracticePhoto = async (task: PracticeTask, file: File) => {
    const attemptId = `attempt_${Date.now()}`
    try {
      setUploadingTaskId(task.id)
      setDialogError(null)
      setIssue(null)
      setNotice(`正在上传「${task.title}」的练习照片...`)
      archiveAttempt(task.id, {
        attemptId,
        practice_task_id: task.practice_task_id,
        fileName: file.name,
        status: "uploading",
        feedbackSummary: "正在上传练习照片...",
        createdAt: new Date().toISOString(),
      })
      savePracticeRecovery({
        practiceTaskId: task.practice_task_id,
        practiceGoal: task.goal,
        sourceJobId: task.sourceJobId,
        sourceMediaId: task.sourceMediaId,
        uploadedFileName: file.name,
        attemptStatus: "uploading",
        updatedAt: new Date().toISOString(),
      })

      const media = await uploadMedia(file)
      updateAttempt(task.id, attemptId, {
        mediaId: media.mediaId,
        fileName: media.fileName,
        status: "uploaded",
        feedbackSummary: "照片已上传，正在创建学习复盘任务...",
      })
      savePracticeRecovery({
        practiceTaskId: task.practice_task_id,
        practiceGoal: task.goal,
        sourceJobId: task.sourceJobId,
        sourceMediaId: task.sourceMediaId,
        uploadedMediaId: media.mediaId,
        uploadedFileName: media.fileName,
        attemptStatus: "uploaded",
        updatedAt: new Date().toISOString(),
      })

      try {
        await createPracticeJobFromMedia(task, media.mediaId, media.fileName, attemptId)
        setSelectedTask(null)
      } catch (error) {
        updateAttempt(task.id, attemptId, {
          status: "uploaded",
          feedbackSummary: "照片已上传，但复盘任务创建失败，可重新创建任务。",
        })
        const message = error instanceof Error ? error.message : "创建练习复盘任务失败。"
        setDialogError(message)
        setIssue(buildLearningIssue("create_job_failed", { taskId: task.id, mediaId: media.mediaId, message }))
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : "练习照片上传失败。"
      updateAttempt(task.id, attemptId, {
        status: "failed",
        feedbackSummary: message,
      })
      setDialogError(message)
      setIssue(buildLearningIssue("upload_failed", { taskId: task.id, message }))
    } finally {
      setUploadingTaskId(null)
    }
  }

  const handleRetryAttempt = (task: PracticeTask, attempt: PracticeAttempt) => {
    if (!attempt.mediaId) {
      setSelectedTask(task)
      setIssue(buildLearningIssue("upload_failed", { taskId: task.id, message: "这条尝试没有可复用的 media_id，请重新上传练习照片。" }))
      return
    }
    void createPracticeJobFromMedia(task, attempt.mediaId, attempt.fileName)
  }

  const handleRestoreRecovery = () => {
    if (!recovery) return
    const task = practiceTasks.find((item) => item.practice_task_id === recovery.practiceTaskId || item.id === recovery.practiceTaskId)
    if (!task) {
      setIssue(buildLearningIssue("task_missing"))
      clearPracticeRecovery()
      setRecovery(null)
      return
    }
    const attemptId = `attempt_recovered_${Date.now()}`
    if (recovery.createdJobId) {
      archiveAttempt(task.id, {
        attemptId,
        practice_task_id: task.practice_task_id,
        jobId: recovery.createdJobId,
        mediaId: recovery.uploadedMediaId,
        fileName: recovery.uploadedFileName,
        status: "reviewing",
        feedbackSummary: recovery.feedbackSummary || "已恢复未完成练习提交，正在继续等待 CoachAgent 结果。",
        createdAt: recovery.updatedAt,
      })
      watchPracticeJob(task, attemptId, recovery.createdJobId, recovery.uploadedMediaId, recovery.uploadedFileName)
      setNotice("已恢复未完成练习提交。")
      return
    }
    if (recovery.uploadedMediaId) {
      void createPracticeJobFromMedia(task, recovery.uploadedMediaId, recovery.uploadedFileName, attemptId)
      return
    }
    setSelectedTask(task)
  }

  const handleDiscardRecovery = () => {
    clearPracticeRecovery()
    setRecovery(null)
  }

  const showEmptyState = fallbackReason === "empty_history" && !shouldUseDemo
  const showSkillGuard = (fallbackReason === "insufficient_data" || coachHistory.length < 3) && hasRealTasks

  return (
    <div className="mx-auto max-w-[1400px] space-y-5 p-6">
      <LearningHeader stats={stats} />

      {recovery ? (
        <LocalRecoveryBanner record={recovery} onRestore={handleRestoreRecovery} onDiscard={handleDiscardRecovery} />
      ) : null}

      {(notice || isLoading) && (
        <div className="flex items-center gap-2 rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm font-medium text-blue-700">
          {fallbackReason === "api_error" ? <ShieldAlert className="h-4 w-4" /> : <Info className="h-4 w-4" />}
          <span>{isLoading ? "正在聚合 CoachAgent 历史结果..." : notice}</span>
        </div>
      )}

      {issue ? (
        <PracticeErrorState
          issue={issue}
          onRetry={issue.code === "history_failed" ? loadLearningData : undefined}
          onDismiss={() => setIssue(null)}
        />
      ) : null}

      {uploadingTaskId ? <PracticeReviewProgress message="练习照片正在提交，请保持页面打开。" /> : null}

      {showEmptyState ? <LearningEmptyState onShowDemo={DEMO_MODE ? undefined : () => setForceDemo(true)} /> : null}

      {shouldUseDemo ? (
        <DemoFallbackBanner message={demoLearningBanner} actionLabel="重新读取真实数据" onAction={loadLearningData} />
      ) : null}

      {showSkillGuard ? (
        <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm font-medium text-amber-700">
          历史结果还不够多，技能雷达为临时画像；完成 3 次分析后会生成更可靠的能力画像。
        </div>
      ) : null}

      <div className="grid grid-cols-1 items-stretch gap-5 lg:grid-cols-12">
        <div className="flex h-full flex-col gap-5 lg:col-span-8">
          <PhotoFeedbackList feedbacks={photoEvaluations} />
          <PracticeTaskList
            tasks={practiceTasks}
            uploadingTaskId={uploadingTaskId}
            onRequestUpload={(task) => {
              if (DEMO_MODE) {
                const next = Array.from(new Set([...claimedTasks, task.id]))
                setClaimedTasks(next)
                localStorage.setItem("photoai.demo.claimedTasks.v2", JSON.stringify(next))
                setNotice(`已领取「${task.title}」。这里只记录练习计划，不代表完成拍摄或 AI 复评。`)
                return
              }
              setSelectedTask(task)
              setDialogError(null)
            }}
            onRetryAttempt={handleRetryAttempt}
            onShowDemoAttempt={() =>
              setNotice(`${demoAttemptResult.title}：${demoAttemptResult.summary} 下一步：${demoAttemptResult.nextStep}`)
            }
          />
        </div>

        <div className="flex h-full flex-col gap-5 lg:col-span-4">
          <GrowthChart scores={weeklyScores} realRecordCount={coachHistory.length} isDemo={shouldUseDemo} />
          <SkillRadar skills={skillScores} sourceNote={skillSourceNote} />
        </div>
      </div>

      <PracticeUploadDialog
        task={selectedTask}
        isOpen={Boolean(selectedTask)}
        isSubmitting={Boolean(uploadingTaskId)}
        errorMessage={dialogError}
        onClose={() => {
          if (!uploadingTaskId) setSelectedTask(null)
        }}
        onSubmit={handleUploadPracticePhoto}
      />
    </div>
  )
}
