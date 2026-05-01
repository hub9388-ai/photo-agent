/**
 * Events Mock 数据
 * 与后端 SSE AgentEventMessage 响应模型对齐。
 */

import type { AgentEventMessage } from "@/types/api"

export const mockJobId = "job_abc123"

export const mockAgentEvents: AgentEventMessage[] = [
  {
    eventId: "evt_job_abc123_created",
    seq: 1,
    jobId: mockJobId,
    agent: null,
    type: "job.created",
    message: "任务已创建",
    payload: {
      agents: ["post", "coach"],
      mediaIds: ["media_001"],
    },
    createdAt: "2026-04-28T10:24:00.000Z",
  },
  {
    eventId: "evt_job_abc123_started",
    seq: 2,
    jobId: mockJobId,
    agent: null,
    type: "job.started",
    message: "任务开始",
    payload: {},
    createdAt: "2026-04-28T10:24:01.000Z",
  },
  {
    eventId: "evt_post_started",
    seq: 3,
    jobId: mockJobId,
    agent: "post",
    type: "agent.started",
    message: "post Agent 已开始",
    payload: { agent: "post" },
    createdAt: "2026-04-28T10:24:02.000Z",
  },
  {
    eventId: "evt_coach_started",
    seq: 4,
    jobId: mockJobId,
    agent: "coach",
    type: "agent.started",
    message: "coach Agent 已开始",
    payload: { agent: "coach" },
    createdAt: "2026-04-28T10:24:02.200Z",
  },
  {
    eventId: "evt_post_progress_exposure",
    seq: 5,
    jobId: mockJobId,
    agent: "post",
    type: "agent.progress",
    message: "正在分析曝光与高光细节",
    payload: { step: "analyzing_exposure", progress: 0.35 },
    createdAt: "2026-04-28T10:24:06.000Z",
  },
  {
    eventId: "evt_coach_progress_composition",
    seq: 6,
    jobId: mockJobId,
    agent: "coach",
    type: "agent.progress",
    message: "正在分析构图与主体表达",
    payload: { step: "analyzing_composition", progress: 0.45 },
    createdAt: "2026-04-28T10:24:08.000Z",
  },
  {
    eventId: "evt_post_delta_1",
    seq: 7,
    jobId: mockJobId,
    agent: "post",
    type: "agent.delta",
    message: "色彩偏冷，建议增加暖色平衡。",
    payload: { text: "色彩偏冷，建议增加暖色平衡。" },
    createdAt: "2026-04-28T10:24:12.000Z",
  },
  {
    eventId: "evt_coach_result",
    seq: 8,
    jobId: mockJobId,
    agent: "coach",
    type: "agent.result",
    message: "coach Agent 已完成",
    payload: { resultId: "result_coach_001", status: "succeeded" },
    createdAt: "2026-04-28T10:24:30.000Z",
  },
  {
    eventId: "evt_post_result",
    seq: 9,
    jobId: mockJobId,
    agent: "post",
    type: "agent.result",
    message: "post Agent 已完成",
    payload: { resultId: "result_post_001", status: "succeeded" },
    createdAt: "2026-04-28T10:24:35.000Z",
  },
  {
    eventId: "evt_job_abc123_completed",
    seq: 10,
    jobId: mockJobId,
    agent: null,
    type: "job.completed",
    message: "任务完成",
    payload: { succeeded: 2, failed: 0, total: 2 },
    createdAt: "2026-04-28T10:24:36.000Z",
  },
]

