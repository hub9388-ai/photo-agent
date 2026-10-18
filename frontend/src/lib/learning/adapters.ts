import type {
  AgentResultResponse,
  JobDetailResponse,
  PhotoEvaluation,
  SkillScore,
  WeeklyScore,
} from "@/types/api"
import type { CoachHistoryItem, PracticeAttempt, PracticeTask } from "@/types/learning"
import { demoPracticeTasks } from "./demo"

export function toStringList(value: unknown): string[] {
  if (!value) return []
  if (Array.isArray(value)) {
    return value.flatMap(toStringList).filter(Boolean)
  }
  if (typeof value === "string") return value ? [value] : []
  if (typeof value === "object") {
    return Object.values(value as Record<string, unknown>).flatMap(toStringList)
  }
  return [String(value)]
}

export function payloadValue(result: AgentResultResponse, ...keys: string[]): unknown {
  for (const key of keys) {
    if (key in result.structuredPayload) return result.structuredPayload[key]
  }
  return undefined
}

export function compactSentence(value: string | undefined | null, fallback: string, max = 130): string {
  return (value || fallback).replace(/\s+/g, " ").slice(0, max)
}

export function hasUsableCoachPayload(result: AgentResultResponse): boolean {
  return Boolean(
    toStringList(payloadValue(result, "strengths")).length ||
      toStringList(payloadValue(result, "improvements", "issues", "improvement_points")).length ||
      toStringList(payloadValue(result, "next_exercise", "nextExercise", "next_steps")).length ||
      result.summary ||
      result.visibleText
  )
}

export function mapCoachToPhotoEvaluation(item: CoachHistoryItem, index: number): PhotoEvaluation {
  const { job, result } = item
  const strengths = toStringList(payloadValue(result, "strengths"))
  const improvements = toStringList(payloadValue(result, "improvements", "issues", "improvement_points"))
  const nextExercise = toStringList(payloadValue(result, "next_exercise", "nextExercise", "next_steps"))
  const commentSource = [
    strengths.length ? `优点：${strengths.slice(0, 2).join("、")}` : "",
    improvements.length ? `问题：${improvements.slice(0, 2).join("、")}` : "",
  ]
    .filter(Boolean)
    .join("；")

  return {
    id: `eval_${job.jobId}`,
    file: typeof result.structuredPayload.source_filename === "string" ? result.structuredPayload.source_filename : job.mediaIds[0] ? `${job.mediaIds[0]}.jpg` : `Coach 反馈 ${index + 1}`,
    thumbnailUrl: typeof result.structuredPayload.preview_url === "string" ? result.structuredPayload.preview_url : "",
    sourceJobId: job.jobId,
    source: "CoachAgent 历史结果",
    status: improvements.length > 0 ? "pending_review" : "mastered",
    statusLabel: improvements.length > 0 ? "待复习" : "已整理",
    comment: compactSentence(commentSource || result.summary || result.visibleText, "已生成学习反馈。"),
    suggestion: compactSentence(
      nextExercise[0] || result.summary,
      "选择一个问题重复拍摄 3 张，对比构图、光线和主体表达。"
    ),
  }
}

function normalizeTaskTitle(text: string, index: number) {
  const cleaned = text.replace(/^练习[:：\s]*/, "").replace(/\s+/g, " ")
  return `练习 ${index + 1}：${cleaned.slice(0, 26) || "复盘并重拍关键问题"}`
}

export function buildPracticeTasks(items: CoachHistoryItem[]): PracticeTask[] {
  const tasks = items.flatMap((item, itemIndex) => {
    const result = item.result
    const explicitTasks = toStringList(payloadValue(result, "practice_tasks", "practiceTasks"))
    const improvements = toStringList(payloadValue(result, "improvements", "issues", "improvement_points"))
    const exercises = explicitTasks.length
      ? explicitTasks
      : toStringList(payloadValue(result, "next_exercise", "nextExercise", "next_steps"))
    const exerciseText = exercises[0] || result.summary || result.visibleText

    if (!exerciseText) return []

    const taskId = `practice_${item.job.jobId}_${itemIndex}`
    const description = compactSentence(exerciseText, "围绕本次 Coach 反馈重拍一组照片。", 180)

    return [
      {
        id: taskId,
        practice_task_id: taskId,
        title: normalizeTaskTitle(description, itemIndex),
        description,
        target: compactSentence(improvements[0] || "近期 Coach 反馈", "近期 Coach 反馈"),
        problem: compactSentence(
          improvements[1] || improvements[0] || "构图、光线或主体表达",
          "构图、光线或主体表达"
        ),
        sourceJobId: item.job.jobId,
        sourceMediaId: item.job.mediaIds[0],
        sourceAgent: "coach",
        goal: description,
        status: itemIndex === 0 ? "in_progress" : "not_started",
        statusLabel: itemIndex === 0 ? "进行中" : "未开始",
        attempts: [],
        createdAt: item.job.createdAt,
        updatedAt: item.job.updatedAt,
      },
    ] satisfies PracticeTask[]
  })

  return tasks.length ? tasks.slice(0, 5) : demoPracticeTasks
}

export function attemptStatusFromResult(result?: AgentResultResponse): PracticeAttempt["status"] {
  if (!result) return "failed"
  if (result.status !== "succeeded") return "failed"
  const combined = `${result.summary} ${result.visibleText}`
  if (/未完成|需复练|还需要|不足|失败/.test(combined)) return "needs_retry"
  return "completed"
}

export function attemptFromCoachFeedbackJob(
  job: JobDetailResponse,
  result?: AgentResultResponse
): { taskId: string; attempt: PracticeAttempt } | null {
  const taskId = String(job.context.practice_task_id || "")
  if (!taskId) return null
  return {
    taskId,
    attempt: {
      attemptId: `attempt_${job.jobId}`,
      practice_task_id: taskId,
      jobId: job.jobId,
      mediaId: job.mediaIds[0] || "",
      fileName: job.mediaIds[0] ? `${job.mediaIds[0]}.jpg` : "练习照片",
      status: attemptStatusFromResult(result),
      feedbackSummary: compactSentence(
        result?.summary || result?.visibleText || "练习反馈已生成。",
        "练习反馈已生成。"
      ),
      visibleText: result?.visibleText,
      structuredPayload: result?.structuredPayload,
      agentError: result?.agentError,
      createdAt: job.createdAt,
    },
  }
}

function scoreFromKeywords(text: string, keywords: string[], base: number): number {
  const hits = keywords.reduce((count, keyword) => count + (text.includes(keyword) ? 1 : 0), 0)
  return Math.min(96, base + hits * 8)
}

function numericPayloadValue(result: AgentResultResponse, ...keys: string[]): number | null {
  const value = payloadValue(result, ...keys)
  if (typeof value === "number" && Number.isFinite(value)) return value
  if (typeof value === "string") {
    const parsed = Number.parseFloat(value)
    return Number.isFinite(parsed) ? parsed : null
  }
  return null
}

function scoreFromCoachResult(result: AgentResultResponse): number {
  const directScore = numericPayloadValue(
    result,
    "practice_score",
    "practiceScore",
    "quality_score",
    "qualityScore",
    "score",
    "rating"
  )
  if (directScore !== null) return Math.max(0, Math.min(100, Math.round(directScore)))

  const scoreInText = `${result.summary} ${result.visibleText}`.match(/(\d{2,3})(?:\s*\/\s*100|分)/)
  if (scoreInText) {
    const parsed = Number.parseInt(scoreInText[1], 10)
    if (Number.isFinite(parsed)) return Math.max(0, Math.min(100, parsed))
  }

  const strengths = toStringList(payloadValue(result, "strengths"))
  const improvements = toStringList(payloadValue(result, "improvements", "issues", "improvement_points"))
  const nextSteps = toStringList(payloadValue(result, "next_exercise", "nextExercise", "next_steps"))
  const text = `${result.summary} ${result.visibleText}`
  const positiveSignals = ["优点", "完成", "清晰", "稳定", "主体明确", "层次", "进步"].filter((keyword) =>
    text.includes(keyword)
  ).length
  const negativeSignals = ["问题", "不足", "过曝", "欠曝", "杂乱", "偏色", "不清晰"].filter((keyword) =>
    text.includes(keyword)
  ).length
  const score = 58 + strengths.length * 6 + nextSteps.length * 2 + positiveSignals * 3 - improvements.length * 4 - negativeSignals * 3
  return Math.max(35, Math.min(92, Math.round(score)))
}

export function buildSkillScores(items: CoachHistoryItem[]): SkillScore[] {
  if (items.length < 3) {
    return [
      { name: "曝光控制", score: 32, color: "blue", icon: "sun" },
      { name: "构图能力", score: 32, color: "orange", icon: "scan-line" },
      { name: "色彩感知", score: 32, color: "green", icon: "palette" },
      { name: "后期思路", score: 32, color: "purple", icon: "wand-sparkles" },
    ]
  }
  const text = items.map((item) => `${item.result.summary} ${item.result.visibleText}`).join(" ")
  const historyBoost = Math.min(16, items.length * 3)

  return [
    {
      name: "曝光控制",
      score: scoreFromKeywords(text, ["曝光", "高光", "阴影", "光线", "过曝"], 58 + historyBoost),
      color: "blue",
      icon: "sun",
    },
    {
      name: "构图能力",
      score: scoreFromKeywords(text, ["构图", "主体", "前景", "引导线", "层次"], 54 + historyBoost),
      color: "orange",
      icon: "scan-line",
    },
    {
      name: "色彩感知",
      score: scoreFromKeywords(text, ["色彩", "色温", "白平衡", "饱和", "氛围"], 56 + historyBoost),
      color: "green",
      icon: "palette",
    },
    {
      name: "后期思路",
      score: scoreFromKeywords(text, ["后期", "参数", "Lightroom", "调整", "风格"], 52 + historyBoost),
      color: "purple",
      icon: "wand-sparkles",
    },
  ]
}

export function buildWeeklyScores(items: CoachHistoryItem[]): WeeklyScore[] {
  const recent = [...items]
    .sort((a, b) => new Date(a.job.createdAt).getTime() - new Date(b.job.createdAt).getTime())
    .slice(-7)

  return Array.from({ length: 7 }, (_, index) => ({
    week: `W${index + 1}`,
    score: recent[index] ? scoreFromCoachResult(recent[index].result) : 0,
  }))
}
