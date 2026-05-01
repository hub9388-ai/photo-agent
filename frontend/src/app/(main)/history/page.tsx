"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import { useRouter } from "next/navigation"
import { AlertTriangle, History } from "lucide-react"
import { HistoryFilterBar, HistoryList } from "@/components/history"
import { getJobResults, listJobs, retryAgent } from "@/lib/api"
import { mockHistoryTasks } from "@/lib/mocks"
import type { HistoryTask } from "@/components/history"
import type { AgentResultResponse, AgentType, JobDetailResponse, JobStatus, JobType } from "@/types/api"

const ENABLE_DEMO_FALLBACK = process.env.NEXT_PUBLIC_ENABLE_DEMO_FALLBACK !== "false"

const statusLabels: Record<JobStatus, string> = {
  queued: "排队中",
  running: "进行中",
  streaming: "流式中",
  completed: "已完成",
  partial_completed: "部分完成",
  failed: "失败",
  cancelled: "已取消",
}

const titleByType: Record<JobType, string> = {
  photo_review: "照片智能分析",
  post_process_advice: "后期建议任务",
  coach_feedback: "学习反馈任务",
  asset_indexing: "素材库索引",
  trip_planning: "拍摄规划任务",
  batch_review: "批量照片分析",
}

const thumbGradients = [
  "from-[#FDE68A] via-[#64748B] to-[#0F172A]",
  "from-[#F8FAFC] via-[#FECACA] to-[#334155]",
  "from-[#FDE68A] via-[#38BDF8] to-[#1E293B]",
  "from-[#CBD5E1] via-[#64748B] to-[#0F172A]",
  "from-[#DBEAFE] via-[#A7F3D0] to-[#0F172A]",
]

type JobCenterItem = {
  job: JobDetailResponse
  results: AgentResultResponse[]
}

function formatJobTime(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  })
}

function trimText(value: string | undefined, fallback = "结果暂不可用"): string {
  return (value || fallback).replace(/\s+/g, " ").slice(0, 80)
}

function summaryByAgent(results: AgentResultResponse[]): Record<string, string> {
  return Object.fromEntries(
    results.map((result) => [
      result.agent,
      result.status === "failed"
        ? `失败：${trimText(result.agentError || result.summary, "结果不可用")}`
        : trimText(result.summary || result.visibleText),
    ])
  )
}

function failedAgents(results: AgentResultResponse[]): AgentType[] {
  return results
    .filter((result) => result.status === "failed")
    .map((result) => result.agent)
}

function buildTaskSummary(job: JobDetailResponse, results: AgentResultResponse[]): string {
  const agentSummary = summaryByAgent(results)
  if (job.type === "photo_review") {
    return [
      agentSummary.post ? `Post：${agentSummary.post}` : "Post：结果暂不可用",
      agentSummary.coach ? `Coach：${agentSummary.coach}` : "Coach：结果暂不可用",
    ].join("     ")
  }
  if (job.type === "trip_planning") return agentSummary.plan || "拍摄规划结果暂不可用"
  if (job.type === "asset_indexing") return agentSummary.asset || "素材索引结果暂不可用"
  if (job.status === "running" || job.status === "streaming") return "任务仍在运行，可查看进度并恢复 SSE"
  if (job.status === "cancelled") return "任务已取消，该任务没有完整结果"
  if (job.status === "failed") return "任务失败，可查看错误或重新分析"
  return Object.values(agentSummary)[0] || "任务结果暂不可用"
}

function contextString(job: JobDetailResponse, ...keys: string[]): string | undefined {
  for (const key of keys) {
    const value = job.context[key]
    if (typeof value === "string" && value.trim()) return value.trim()
  }
  return undefined
}

function shortMediaId(mediaId: string | undefined): string {
  if (!mediaId) return "未关联照片"
  return mediaId.length > 18 ? `${mediaId.slice(0, 18)}...` : mediaId
}

function buildTaskTitle(job: JobDetailResponse): string {
  if (job.type === "photo_review") {
    return `${titleByType[job.type]} · ${shortMediaId(job.mediaIds[0])}`
  }

  if (job.type === "trip_planning") {
    const city = contextString(job, "city")
    const location = contextString(job, "target_location", "targetLocation", "location")
    const place = [city, location].filter(Boolean).join("")
    return place ? `${titleByType[job.type]} · ${place}` : titleByType[job.type]
  }

  if (job.type === "asset_indexing") {
    const project =
      contextString(job, "project_name", "projectName", "project_id", "projectId") ||
      contextString(job, "project_root", "projectRoot")
    return project ? `${titleByType[job.type]} · ${project}` : titleByType[job.type]
  }

  return titleByType[job.type] || "Agent 任务"
}

function taskActions(job: JobDetailResponse, failed: AgentType[]): HistoryTask["actions"] {
  if (job.status === "running" || job.status === "streaming" || job.status === "queued") {
    return ["progress"]
  }
  if (job.status === "partial_completed") return failed.length ? ["view", "retry", "rerun"] : ["view", "rerun"]
  if (job.status === "failed") return failed.length ? ["view", "retry", "rerun"] : ["view", "rerun"]
  if (job.type === "trip_planning") return ["view", "reuse"]
  if (job.type === "asset_indexing") return ["view", "open"]
  return ["view", "rerun"]
}

function mapJobToHistoryTask(item: JobCenterItem, index: number): HistoryTask {
  const { job, results } = item
  const failed = failedAgents(results)
  const typeLabel = job.type === "photo_review" ? job.agents.join(" + ") || "photo_review" : job.type
  return {
    id: job.jobId,
    title: buildTaskTitle(job),
    type: job.type,
    typeLabel,
    status: job.status,
    statusLabel: statusLabels[job.status],
    summary: buildTaskSummary(job, results),
    subSummary:
      job.status === "partial_completed"
        ? "成功结果已保留，失败 Agent 可单独重试"
        : job.status === "running" || job.status === "streaming"
          ? "已恢复关键事件记录，实时 delta 文本不会完整恢复"
          : job.agents.length
            ? `Agents: ${job.agents.join(" + ")}`
            : undefined,
    detailSummary:
      results.length === 0 && job.status !== "running" && job.status !== "streaming"
        ? "任务存在，但结果暂不可用；可能仍在运行、Agent 执行失败或 MVP 重启导致运行中任务丢失。"
        : undefined,
    time: formatJobTime(job.updatedAt || job.createdAt),
    thumbGradient: thumbGradients[index % thumbGradients.length],
    thumbStyle: job.type === "asset_indexing" ? "mosaic" : undefined,
    failedAgents: failed,
    actions: taskActions(job, failed),
  }
}

function demoItems(): JobCenterItem[] {
  return mockHistoryTasks.map((task, index) => {
    const type = task.type === "trip_planning" || task.type === "asset_indexing" ? task.type : "photo_review"
    const status = task.status as JobStatus
    const agents: AgentType[] =
      type === "trip_planning" ? ["plan"] : type === "asset_indexing" ? ["asset"] : ["post", "coach"]
    const results: AgentResultResponse[] =
      status === "cancelled" || status === "running"
        ? []
        : agents.map((agent) => ({
            agent,
            status: task.status === "partial_completed" && agent === "post" ? "failed" : "succeeded",
            summary: task.summary,
            visibleText: task.summary,
            structuredPayload: {},
            warnings: [],
            agentError: task.status === "partial_completed" && agent === "post" ? "模型超时" : null,
            createdAt: "2026-04-28T10:00:00.000Z",
          }))
    return {
      job: {
        jobId: `demo_${task.id}`,
        type,
        trigger: "user",
        status,
        agents,
        mediaIds: type === "photo_review" ? [`demo_media_${index + 1}`] : [],
        progress: status === "completed" ? 1 : null,
        context: {},
        createdAt: "2026-04-28T10:00:00.000Z",
        updatedAt: "2026-04-28T10:00:00.000Z",
      },
      results,
    }
  })
}

export default function HistoryPage() {
  const router = useRouter()
  const [searchQuery, setSearchQuery] = useState("")
  const [typeFilter, setTypeFilter] = useState<JobType | "all">("all")
  const [statusFilter, setStatusFilter] = useState<JobStatus | "all">("all")
  const [currentPage, setCurrentPage] = useState(1)
  const [pageSize, setPageSize] = useState(10)
  const [items, setItems] = useState<JobCenterItem[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [usingDemo, setUsingDemo] = useState(false)

  const loadHistory = useCallback(async (forceDemo = false) => {
    if (forceDemo) {
      setItems(demoItems())
      setError(null)
      setUsingDemo(true)
      setIsLoading(false)
      return
    }

    try {
      setIsLoading(true)
      setError(null)
      setUsingDemo(false)
      const jobs = await listJobs()
      const settled = await Promise.allSettled(
        jobs.map(async (job) => {
          try {
            const response = await getJobResults(job.jobId)
            return { job, results: response.results }
          } catch {
            return { job, results: [] }
          }
        })
      )
      const loadedItems = settled.flatMap((result) =>
        result.status === "fulfilled" ? [result.value] : []
      )
      setItems(loadedItems)
    } catch (loadError) {
      const message = loadError instanceof Error ? loadError.message : "历史任务加载失败"
      setError(`历史任务加载失败：${message}`)
      if (ENABLE_DEMO_FALLBACK) {
        setItems(demoItems())
        setUsingDemo(true)
      } else {
        setItems([])
      }
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadHistory()
    }, 0)
    return () => window.clearTimeout(timer)
  }, [loadHistory])

  const filteredTasks = useMemo(() => {
    const normalizedQuery = searchQuery.trim().toLowerCase()
    return items
      .filter(({ job }) => typeFilter === "all" || job.type === typeFilter)
      .filter(({ job }) => statusFilter === "all" || job.status === statusFilter)
      .map(mapJobToHistoryTask)
      .filter((task) => {
        if (!normalizedQuery) return true
        return (
          task.title.toLowerCase().includes(normalizedQuery) ||
          task.typeLabel.toLowerCase().includes(normalizedQuery) ||
          task.summary.toLowerCase().includes(normalizedQuery) ||
          task.subSummary?.toLowerCase().includes(normalizedQuery)
        )
      })
  }, [items, searchQuery, statusFilter, typeFilter])

  const pagedTasks = useMemo(() => {
    const start = (currentPage - 1) * pageSize
    return filteredTasks.slice(start, start + pageSize)
  }, [currentPage, filteredTasks, pageSize])

  const pagination = {
    currentPage,
    totalPages: Math.max(1, Math.ceil(filteredTasks.length / pageSize)),
    pageSize,
    totalItems: filteredTasks.length,
  }

  const findJobByTaskId = (taskId: string) => items.find((item) => item.job.jobId === taskId)?.job

  const routeForJob = (job: JobDetailResponse): string => {
    if (job.type === "trip_planning") return `/planning?job_id=${job.jobId}`
    if (job.type === "asset_indexing") return `/assets?job_id=${job.jobId}`
    if (job.type === "coach_feedback") return `/learning?job_id=${job.jobId}`
    if (job.type === "post_process_advice") return `/analysis/${job.jobId}?tab=post`
    return `/analysis/${job.jobId}`
  }

  const handleTaskView = (taskId: string) => {
    const job = findJobByTaskId(taskId)
    if (!job) return
    router.push(routeForJob(job))
  }

  const handleTaskReanalyze = (taskId: string) => {
    const job = findJobByTaskId(taskId)
    if (!job) return
    if (job.type === "trip_planning") router.push(`/planning?reuse_job_id=${job.jobId}`)
    else if (job.type === "asset_indexing") router.push(`/assets?job_id=${job.jobId}`)
    else router.push(`/analysis/${job.jobId}`)
  }

  const handleTaskRetry = async (taskId: string) => {
    const item = items.find((candidate) => candidate.job.jobId === taskId)
    const agent = item ? failedAgents(item.results)[0] : undefined
    if (!item || !agent || usingDemo) {
      handleTaskView(taskId)
      return
    }
    try {
      await retryAgent(item.job.jobId, agent)
      router.push(`/analysis/${item.job.jobId}`)
    } catch (retryError) {
      setError(retryError instanceof Error ? `失败 Agent 重试失败：${retryError.message}` : "失败 Agent 重试失败")
    }
  }

  return (
    <div className="mx-auto w-full max-w-[1400px] px-7 py-6">
      <div className="mb-6 flex items-center gap-5">
        <History className="h-10 w-10 text-[#0F172A]" />
        <div className="space-y-2">
          <h1 className="text-[30px] font-extrabold leading-none text-[#0F172A]">历史记录</h1>
          <p className="text-sm text-[#64748B]">从历史任务恢复分析、学习、规划和素材管理结果</p>
        </div>
      </div>

      <HistoryFilterBar
        searchQuery={searchQuery}
        onSearchChange={(value) => {
          setSearchQuery(value)
          setCurrentPage(1)
        }}
        typeFilter={typeFilter}
        onTypeFilterChange={(value) => {
          setTypeFilter(value)
          setCurrentPage(1)
        }}
        statusFilter={statusFilter}
        onStatusFilterChange={(value) => {
          setStatusFilter(value)
          setCurrentPage(1)
        }}
        totalCount={pagination.totalItems}
        onRefresh={() => void loadHistory()}
      />

      {error && (
        <div className="mt-4 flex items-center justify-between rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm font-medium text-red-700">
          <span className="flex items-center gap-2"><AlertTriangle className="h-4 w-4" />{error}</span>
          <button className="font-extrabold text-red-700 underline" onClick={() => void loadHistory(true)}>
            使用 Demo 历史数据
          </button>
        </div>
      )}

      {usingDemo && (
        <div className="mt-4 rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm font-medium text-blue-700">
          当前使用 Demo 历史数据，真实后端暂不可用或暂无完整历史结果。
        </div>
      )}

      <div className="mt-5">
        <HistoryList
          tasks={pagedTasks}
          pagination={pagination}
          isLoading={isLoading}
          onPageChange={setCurrentPage}
          onPageSizeChange={setPageSize}
          onTaskView={handleTaskView}
          onTaskReanalyze={handleTaskReanalyze}
          onTaskRetry={handleTaskRetry}
        />
      </div>
    </div>
  )
}
