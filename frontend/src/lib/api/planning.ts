/**
 * Planning API
 * /api/agents/plan/run 是 trip_planning job 的便捷入口。
 */

import type { CreateJobResponse } from "@/types/api"
import { apiRequest, delay, isMockMode } from "./client"

export interface PlanRunRequest {
  user_goal: string
  city?: string
  target_location?: string
  shoot_date?: string
  time_window?: string
  subject?: string
  style_keywords?: string[]
  gear?: string[]
  reference_media_ids?: string[]
  context?: Record<string, unknown>
}

export async function runPlanningAgent(payload: PlanRunRequest): Promise<CreateJobResponse> {
  if (isMockMode()) {
    await delay(500)
    const jobId = `job_plan_${Date.now()}`
    return {
      jobId,
      status: "queued",
      eventsUrl: `/api/jobs/${jobId}/events`,
      resultsUrl: `/api/jobs/${jobId}/results`,
      agent: "plan",
    }
  }

  return apiRequest<CreateJobResponse>("/api/agents/plan/run", {
    method: "POST",
    body: JSON.stringify(payload),
  })
}

