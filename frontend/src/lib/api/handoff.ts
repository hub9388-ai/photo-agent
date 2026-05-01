/**
 * Handoff API
 * 只封装业务层 Agent-to-Agent 流转，不在组件内直接 fetch。
 */

import type { HandoffRequest, HandoffResponse } from "@/types/api"
import { apiRequest, delay, isMockMode } from "./client"

export async function createHandoff(payload: HandoffRequest): Promise<HandoffResponse> {
  if (isMockMode()) {
    await delay(400)
    return {
      handoffId: `handoff_${Date.now()}`,
      jobId: `job_${Date.now()}`,
      status: "accepted",
      message: `${payload.sourceAgent} → ${payload.targetAgent} handoff 已创建`,
    }
  }

  return apiRequest<HandoffResponse>("/api/handoff", {
    method: "POST",
    body: JSON.stringify(payload),
  })
}

