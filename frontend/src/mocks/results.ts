/**
 * Results Mock 数据
 * 与后端 JobResultsResponse / AgentResultResponse 响应模型对齐。
 */

import type { AgentResultResponse, JobResultsResponse } from "@/types/api"
import { mockJobId } from "./events"

export const mockPostAgentResultResponse: AgentResultResponse = {
  agent: "post",
  status: "succeeded",
  summary: "适合压暗背景并强化主体，建议保留天空高光层次并增强日出暖色。",
  visibleText:
    "这张照片的主体和环境关系明确。后期建议先压低整体曝光约 -0.3EV，降低高光以保留天空层次，再适度提升阴影让山体细节回来。色温可以略微调暖，橙色与黄色饱和度小幅增强，营造清晨日出的氛围。",
  structuredPayload: {
    taskMode: "single_photo",
    mainIssues: ["高光略亮", "整体色温偏冷", "前景层次可加强"],
    adjustments: {
      exposure: "-0.3 EV",
      contrast: "+15",
      highlights: "-40",
      shadows: "+25",
      vibrance: "+15",
    },
    xmpParams: {
      exposure2012: -0.3,
      contrast2012: 15,
      highlights2012: -40,
      shadows2012: 25,
      vibrance: 15,
    },
  },
  warnings: [],
  agentError: null,
  createdAt: "2026-04-28T10:24:35.000Z",
}

export const mockCoachAgentResultResponse: AgentResultResponse = {
  agent: "coach",
  status: "succeeded",
  summary: "主体明确、山体光影出色；下次可尝试更低机位并扩大前景占比。",
  visibleText:
    "这张照片的优点是主体明确，山体光影和水面倒影形成了清晰的视觉中心。可改进点在于机位稍高，前景占比偏小，画面纵深还可以更强。下次拍摄可以尝试更低机位，让前景引导线参与构图，同时记录日出前后色温变化。",
  structuredPayload: {
    taskMode: "critique",
    strengths: ["主体明确", "光影层次好", "水面倒影增强空间感"],
    improvements: ["前景占比偏小", "机位可更低", "纵深引导线不足"],
    nextExercise: "拍摄一组日出风光，尝试不同机位与前景组合，记录光线变化。",
    skillLevel: "进阶练习",
  },
  warnings: [],
  agentError: null,
  createdAt: "2026-04-28T10:24:30.000Z",
}

export const mockJobResultsResponse: JobResultsResponse = {
  jobId: mockJobId,
  status: "completed",
  results: [mockPostAgentResultResponse, mockCoachAgentResultResponse],
}

export const mockPartialJobResultsResponse: JobResultsResponse = {
  jobId: "job_partial_001",
  status: "partial_completed",
  results: [
    {
      ...mockCoachAgentResultResponse,
      createdAt: "2026-04-28T11:03:12.000Z",
    },
    {
      agent: "post",
      status: "failed",
      summary: "Post Agent 调用超时，已保留 Coach Agent 的学习反馈。",
      visibleText: "",
      structuredPayload: {},
      warnings: ["MODEL_TIMEOUT"],
      agentError: "模型请求超时，请稍后重试 Post Agent。",
      createdAt: "2026-04-28T11:03:20.000Z",
    },
  ],
}

