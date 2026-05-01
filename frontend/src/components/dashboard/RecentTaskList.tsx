"use client"

import { useEffect, useMemo, useState } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { listJobs } from "@/lib/api"
import type { JobDetailResponse, JobStatus } from "@/types/api"

const statusColorMap: Record<JobStatus, string> = {
  queued: "bg-yellow-100 text-yellow-700",
  running: "bg-blue-100 text-blue-700",
  streaming: "bg-blue-100 text-blue-700",
  completed: "bg-green-100 text-green-700",
  partial_completed: "bg-orange-100 text-orange-700",
  failed: "bg-red-100 text-red-700",
  cancelled: "bg-slate-100 text-slate-600",
}

const statusLabelMap: Record<JobStatus, string> = {
  queued: "排队中",
  running: "进行中",
  streaming: "进行中",
  completed: "已完成",
  partial_completed: "部分完成",
  failed: "失败",
  cancelled: "已取消",
}

const typeTitleMap: Record<string, string> = {
  photo_review: "照片智能分析",
  post_process_advice: "后期建议",
  coach_feedback: "学习反馈",
  asset_indexing: "素材库索引",
  trip_planning: "拍摄规划任务",
  batch_review: "批量照片分析",
}

const thumbGradients = [
  "from-blue-100 to-slate-300",
  "from-emerald-100 to-slate-300",
  "from-orange-100 to-slate-300",
]

function contextString(job: JobDetailResponse, ...keys: string[]): string | undefined {
  for (const key of keys) {
    const value = job.context[key]
    if (typeof value === "string" && value.trim()) return value.trim()
  }
  return undefined
}

function shortMediaId(mediaId: string | undefined): string {
  if (!mediaId) return "未关联照片"
  return mediaId.length > 16 ? `${mediaId.slice(0, 16)}...` : mediaId
}

function titleForJob(job: JobDetailResponse) {
  if (job.type === "photo_review" || job.type === "post_process_advice" || job.type === "coach_feedback") {
    return `${typeTitleMap[job.type]} · ${shortMediaId(job.mediaIds[0])}`
  }

  if (job.type === "trip_planning") {
    const city = contextString(job, "city")
    const location = contextString(job, "target_location", "targetLocation", "location")
    const place = [city, location].filter(Boolean).join("")
    return place ? `${typeTitleMap[job.type]} · ${place}` : typeTitleMap[job.type]
  }

  if (job.type === "asset_indexing") {
    const project =
      contextString(job, "project_name", "projectName", "project_id", "projectId") ||
      contextString(job, "project_root", "projectRoot")
    return project ? `${typeTitleMap[job.type]} · ${project}` : typeTitleMap[job.type]
  }

  return typeTitleMap[job.type] || "Agent 任务"
}

function typeLabelForJob(job: JobDetailResponse) {
  if (job.type === "photo_review") return job.agents.join(" + ") || "photo_review"
  return job.type
}

function routeForJob(job: JobDetailResponse) {
  if (job.type === "trip_planning") return `/planning?job_id=${job.jobId}`
  if (job.type === "asset_indexing") return `/assets?job_id=${job.jobId}`
  if (job.type === "coach_feedback") return `/learning?job_id=${job.jobId}`
  if (job.type === "post_process_advice") return `/analysis/${job.jobId}?tab=post`
  return `/analysis/${job.jobId}`
}

function formatRelativeTime(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return "时间未知"
  const seconds = Math.max(0, Math.floor((Date.now() - date.getTime()) / 1000))
  if (seconds < 60) return "刚刚"
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes} 分钟前`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours} 小时前`
  const days = Math.floor(hours / 24)
  if (days < 30) return `${days} 天前`
  return date.toLocaleDateString("zh-CN")
}

export function RecentTaskList() {
  const router = useRouter()
  const [jobs, setJobs] = useState<JobDetailResponse[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let isMounted = true

    void listJobs()
      .then((loadedJobs) => {
        if (!isMounted) return
        setJobs(loadedJobs)
        setError(null)
      })
      .catch((loadError) => {
        if (!isMounted) return
        setJobs([])
        setError(loadError instanceof Error ? loadError.message : "最近任务加载失败")
      })
      .finally(() => {
        if (isMounted) setIsLoading(false)
      })

    return () => {
      isMounted = false
    }
  }, [])

  const recentJobs = useMemo(
    () =>
      [...jobs]
        .sort((a, b) => new Date(b.updatedAt || b.createdAt).getTime() - new Date(a.updatedAt || a.createdAt).getTime())
        .slice(0, 3),
    [jobs]
  )

  return (
    <Card className="lg:col-span-2">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base">最近任务</CardTitle>
          <Link href="/history" className="text-sm text-blue-600 hover:underline">
            查看全部
          </Link>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {isLoading ? (
          <div className="rounded-lg bg-slate-50 p-4 text-sm text-slate-500">正在同步最近任务...</div>
        ) : null}

        {!isLoading && error ? (
          <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-700">
            最近任务加载失败：{error}
          </div>
        ) : null}

        {!isLoading && !error && !recentJobs.length ? (
          <div className="rounded-lg border border-dashed border-slate-300 bg-slate-50 p-4 text-sm text-slate-500">
            还没有真实任务。上传照片或创建拍摄规划后，这里会显示最近使用记录。
          </div>
        ) : null}

        {recentJobs.map((job, index) => (
          <div key={job.jobId} className="flex items-center gap-4 p-3 rounded-lg bg-slate-50">
            <div className={`h-12 w-12 flex-shrink-0 rounded-lg bg-gradient-to-br ${thumbGradients[index % thumbGradients.length]}`} />
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <p className="truncate font-medium text-slate-900">{titleForJob(job)}</p>
                <Badge variant="outline" className="shrink-0 text-xs bg-slate-100">
                  {typeLabelForJob(job)}
                </Badge>
              </div>
              <p className="text-sm text-slate-500">{formatRelativeTime(job.updatedAt || job.createdAt)}</p>
            </div>
            <Badge className={`${statusColorMap[job.status]} shrink-0`}>{statusLabelMap[job.status]}</Badge>
            <Button variant="ghost" size="sm" onClick={() => router.push(routeForJob(job))}>
              {job.status === "running" || job.status === "streaming" || job.status === "queued" ? "查看进度" : "查看结果"}
            </Button>
          </div>
        ))}
      </CardContent>
    </Card>
  )
}
