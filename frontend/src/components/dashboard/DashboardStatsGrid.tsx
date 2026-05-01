"use client"

import { useEffect, useState } from "react"
import { Camera, Check, Clock, MapPin } from "lucide-react"
import { getJobResults, listJobs } from "@/lib/api"
import type { AgentResultResponse, JobDetailResponse, JobStatus } from "@/types/api"
import { StatsCard } from "./StatsCard"

type DashboardMetrics = {
  analyzedPhotos: number
  feedbackCount: number
  planCount: number
  practiceCount: number
  source: "loading" | "real" | "fallback" | "error"
}

const EMPTY_METRICS: DashboardMetrics = {
  analyzedPhotos: 0,
  feedbackCount: 0,
  planCount: 0,
  practiceCount: 0,
  source: "loading",
}

const COMPLETED_STATUSES = new Set<JobStatus>(["completed", "partial_completed"])
const ACTIVE_RESULT_STATUSES = new Set<JobStatus>(["completed", "partial_completed", "running", "streaming"])

function isObject(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === "object" && !Array.isArray(value))
}

function toList(value: unknown): unknown[] {
  if (Array.isArray(value)) return value
  if (typeof value === "string" && value.trim()) {
    return value
      .split(/\n|；|;|。/)
      .map((item) => item.trim())
      .filter(Boolean)
  }
  return []
}

function payloadList(payload: Record<string, unknown>, ...keys: string[]) {
  for (const key of keys) {
    const list = toList(payload[key])
    if (list.length) return list
  }
  return []
}

function countTodoPracticeTasks(results: AgentResultResponse[]) {
  return results
    .filter((result) => result.agent === "coach" && result.status === "succeeded")
    .reduce((total, result) => {
      const payload = result.structuredPayload || {}
      const explicitTasks = payloadList(payload, "practice_tasks", "practiceTasks")
      if (explicitTasks.length) {
        return (
          total +
          explicitTasks.filter((task) => {
            if (!isObject(task)) return true
            const status = String(task.status || task.practice_status || "").toLowerCase()
            return status !== "completed" && status !== "done"
          }).length
        )
      }

      return total + payloadList(payload, "next_exercise", "nextExercise", "next_steps", "nextSteps").length
    }, 0)
}

function countAnalyzedPhotos(jobs: JobDetailResponse[]) {
  const mediaIds = new Set<string>()
  let fallbackJobCount = 0

  jobs.forEach((job) => {
    if (!COMPLETED_STATUSES.has(job.status)) return
    const isPhotoAnalysis =
      job.type === "photo_review" ||
      job.type === "post_process_advice" ||
      job.type === "coach_feedback" ||
      job.type === "batch_review"
    if (!isPhotoAnalysis) return

    if (job.mediaIds.length) {
      job.mediaIds.forEach((mediaId) => mediaIds.add(mediaId))
    } else {
      fallbackJobCount += 1
    }
  })

  return mediaIds.size + fallbackJobCount
}

async function loadDashboardMetrics(): Promise<DashboardMetrics> {
  const jobs = await listJobs()
  const resultJobs = jobs.filter(
    (job) =>
      ACTIVE_RESULT_STATUSES.has(job.status) &&
      (job.agents.includes("coach") || job.type === "photo_review" || job.type === "coach_feedback")
  )

  const settledResults = await Promise.allSettled(resultJobs.map((job) => getJobResults(job.jobId)))
  const results = settledResults.flatMap((item) => (item.status === "fulfilled" ? item.value.results : []))
  const feedbackCount = results.filter((result) => result.agent === "coach" && result.status === "succeeded").length

  return {
    analyzedPhotos: countAnalyzedPhotos(jobs),
    feedbackCount,
    planCount: jobs.filter((job) => job.type === "trip_planning" && job.status !== "failed" && job.status !== "cancelled").length,
    practiceCount: countTodoPracticeTasks(results),
    source: "real",
  }
}

function statCards(metrics: DashboardMetrics) {
  const sourceLabel =
    metrics.source === "loading"
      ? "正在同步"
      : metrics.source === "error"
        ? "后端不可用"
        : metrics.source === "fallback"
          ? "示例数据"
          : "来自 Job/Result"

  return [
    { icon: Camera, value: metrics.analyzedPhotos.toLocaleString(), label: "已分析照片", change: sourceLabel, iconColor: "text-blue-500" },
    { icon: Check, value: metrics.feedbackCount.toLocaleString(), label: "学习反馈", change: sourceLabel, iconColor: "text-green-500" },
    { icon: MapPin, value: metrics.planCount.toLocaleString(), label: "拍摄规划", change: sourceLabel, iconColor: "text-orange-500" },
    { icon: Clock, value: metrics.practiceCount.toLocaleString(), label: "待办练习", change: sourceLabel, iconColor: "text-purple-500" },
  ]
}

export function DashboardStatsGrid() {
  const [metrics, setMetrics] = useState<DashboardMetrics>(EMPTY_METRICS)

  useEffect(() => {
    let isMounted = true

    void loadDashboardMetrics()
      .then((nextMetrics) => {
        if (isMounted) setMetrics(nextMetrics)
      })
      .catch(() => {
        if (isMounted) setMetrics({ ...EMPTY_METRICS, source: "error" })
      })

    return () => {
      isMounted = false
    }
  }, [])

  return (
    <div className="grid grid-cols-2 gap-4">
      {statCards(metrics).map((stat) => (
        <StatsCard key={stat.label} {...stat} />
      ))}
    </div>
  )
}
