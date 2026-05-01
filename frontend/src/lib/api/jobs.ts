/**
 * Job / Analysis 相关 API
 * 包含任务创建、查询、控制等操作
 */

import type {
  AgentType,
  AnalysisJob,
  AgentProgress,
  CreateJobRequest,
  CreateJobResponse,
  JobDetailResponse,
  JobListResponse,
  JobResultsResponse,
  JobStatus,
  PostAgentResult,
  CoachAgentResult,
  PaginatedResponse,
} from "@/types/api"
import { apiClient, apiRequest, isMockMode, mockResponse, delay } from "./client"
import {
  mockJobs,
  mockHistoryTasks,
  mockAgentProgress,
  mockPostResult,
  mockCoachResult,
  mockJobResultsResponse,
} from "@/mocks"

export interface ListJobsParams {
  media_id?: string
  status?: string
  type?: string
  page?: number
  page_size?: number
}

function normalizeJobStatus(status: string): JobStatus {
  if (status === "pending") return "queued"
  if (
    status === "queued" ||
    status === "running" ||
    status === "streaming" ||
    status === "completed" ||
    status === "partial_completed" ||
    status === "failed" ||
    status === "cancelled"
  ) {
    return status
  }
  return "queued"
}

// 创建后端 Agent Job，匹配 POST /api/jobs
export async function createJob(payload: CreateJobRequest): Promise<CreateJobResponse> {
  if (isMockMode()) {
    await delay(500)
    const jobId = `job_${Date.now()}`
    return {
      jobId,
      status: "queued",
      eventsUrl: `/api/jobs/${jobId}/events`,
      resultsUrl: `/api/jobs/${jobId}/results`,
      agent: payload.agents.length === 1 ? payload.agents[0] : null,
    }
  }

  return apiRequest<CreateJobResponse>("/api/jobs", {
    method: "POST",
    body: JSON.stringify(payload),
  })
}

// 获取后端 Job 详情，匹配 GET /api/jobs/{jobId}
export async function getJobDetail(jobId: string): Promise<JobDetailResponse> {
  if (isMockMode()) {
    await delay(300)
    return {
      jobId,
      type: "photo_review",
      trigger: "user",
      status: "completed",
      agents: ["post", "coach"],
      mediaIds: ["media_001"],
      progress: 1,
      context: {},
      createdAt: "2026-04-28T10:24:00.000Z",
      updatedAt: "2026-04-28T10:24:36.000Z",
    }
  }

  return apiRequest<JobDetailResponse>(`/api/jobs/${jobId}`)
}

// 获取后端 Job 结果，匹配 GET /api/jobs/{jobId}/results
export async function getJobResults(jobId: string): Promise<JobResultsResponse> {
  if (isMockMode()) {
    await delay(300)
    return { ...mockJobResultsResponse, jobId }
  }

  return apiRequest<JobResultsResponse>(`/api/jobs/${jobId}/results`)
}

// 获取 Job 历史列表，匹配 GET /api/jobs
export async function listJobs(params?: ListJobsParams): Promise<JobDetailResponse[]> {
  if (isMockMode()) {
    await delay(400)
    return mockHistoryTasks.map((task) => ({
      jobId: `job_${task.id}`,
      type:
        task.type === "trip_planning"
          ? "trip_planning"
          : task.type === "asset_indexing"
            ? "asset_indexing"
            : "photo_review",
      trigger: "user",
      status: normalizeJobStatus(task.status),
      agents:
        task.type === "trip_planning"
          ? ["plan"]
          : task.type === "asset_indexing"
            ? ["asset"]
            : ["post", "coach"],
      mediaIds: task.type === "photo_review" ? ["media_001"] : [],
      progress: task.status === "completed" ? 1 : null,
      context: {},
      createdAt: "2026-04-28T10:24:00.000Z",
      updatedAt: "2026-04-28T10:24:36.000Z",
    }))
  }

  const response = await apiRequest<JobListResponse>("/api/jobs", {
    params: params as Record<string, string | number | boolean | undefined> | undefined,
  })
  return response.jobs
}

// 重试单个 Agent，匹配 POST /api/jobs/{jobId}/agents/{agent}/retry
export async function retryAgent(
  jobId: string,
  agent: AgentType
): Promise<CreateJobResponse> {
  if (isMockMode()) {
    await delay(500)
    return {
      jobId,
      status: "queued",
      eventsUrl: `/api/jobs/${jobId}/events`,
      resultsUrl: `/api/jobs/${jobId}/results`,
      agent,
    }
  }

  return apiRequest<CreateJobResponse>(`/api/jobs/${jobId}/agents/${agent}/retry`, {
    method: "POST",
  })
}

// 创建分析任务
export async function createAnalysisJob(params: {
  images: string[]  // asset IDs
  preferences?: string
  agents: ("post" | "coach")[]
}): Promise<{ jobId: string }> {
  if (isMockMode()) {
    await delay(500)
    return { jobId: `job_${Date.now()}` }
  }

  const response = await apiClient.post<{ jobId: string }>("/api/jobs", params)
  return response.data!
}

// 获取任务列表
export async function getJobs(params?: {
  status?: string
  type?: string
  page?: number
  pageSize?: number
}): Promise<PaginatedResponse<AnalysisJob>> {
  if (isMockMode()) {
    await delay(500)
    const page = params?.page || 1
    const pageSize = params?.pageSize || 10
    const start = (page - 1) * pageSize
    const end = start + pageSize
    const items = mockJobs.slice(start, end)

    return {
      items,
      pagination: {
        page,
        pageSize,
        total: mockJobs.length,
        totalPages: Math.ceil(mockJobs.length / pageSize),
      },
    }
  }

  const response = await apiClient.get<PaginatedResponse<AnalysisJob>>("/api/jobs", {
    params,
  })
  return response.data!
}

// 获取后端 Job 详情的标准函数名
export async function getJob(jobId: string): Promise<JobDetailResponse> {
  return getJobDetail(jobId)
}

// 获取旧 UI 分析任务详情（兼容 mock UI 模型）
export async function getAnalysisJob(id: string): Promise<AnalysisJob> {
  if (isMockMode()) {
    const job = mockJobs.find(j => j.id === id)
    if (!job) {
      throw new Error("Job not found")
    }
    return mockResponse(job, 300).then(r => r.data!)
  }

  const response = await apiClient.get<AnalysisJob>(`/api/jobs/${id}`)
  return response.data!
}

// 获取任务进度
export async function getJobProgress(id: string): Promise<{
  post?: AgentProgress
  coach?: AgentProgress
}> {
  if (isMockMode()) {
    await delay(300)
    // 模拟进度变化
    const progress = Math.random() > 0.5 ? 78 : 100
    return {
      post: {
        ...mockAgentProgress.post,
        progress,
        status: progress < 100 ? "running" : "completed",
      },
      coach: mockAgentProgress.coach,
    }
  }

  const response = await apiClient.get<{ post?: AgentProgress; coach?: AgentProgress }>(
    `/api/jobs/${id}/progress`
  )
  return response.data!
}

// 获取 Post Agent 结果
export async function getPostResult(jobId: string): Promise<PostAgentResult> {
  if (isMockMode()) {
    await delay(300)
    return mockResponse(mockPostResult, 300).then(r => r.data!)
  }

  const response = await apiClient.get<PostAgentResult>(`/api/jobs/${jobId}/post`)
  return response.data!
}

// 获取 Coach Agent 结果
export async function getCoachResult(jobId: string): Promise<CoachAgentResult> {
  if (isMockMode()) {
    await delay(300)
    return mockResponse(mockCoachResult, 300).then(r => r.data!)
  }

  const response = await apiClient.get<CoachAgentResult>(`/api/jobs/${jobId}/coach`)
  return response.data!
}

// 取消任务
export async function cancelJob(id: string): Promise<void> {
  if (isMockMode()) {
    await delay(300)
    return
  }

  await apiClient.post(`/api/jobs/${id}/cancel`)
}

// 重试失败的任务
export async function retryJob(id: string): Promise<{ jobId: string }> {
  if (isMockMode()) {
    await delay(500)
    return { jobId: id }
  }

  const response = await apiClient.post<{ jobId: string }>(`/api/jobs/${id}/retry`)
  return response.data!
}

// 删除任务
export async function deleteJob(id: string): Promise<void> {
  if (isMockMode()) {
    await delay(300)
    return
  }

  await apiClient.delete(`/api/jobs/${id}`)
}
