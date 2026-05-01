import type { AgentResultResponse, JobDetailResponse } from "./api"

export type PracticeTaskStatus =
  | "not_started"
  | "in_progress"
  | "submitted"
  | "completed"
  | "needs_retry"
  | "failed"

export type PracticeAttemptStatus =
  | "uploading"
  | "uploaded"
  | "job_created"
  | "reviewing"
  | "completed"
  | "needs_retry"
  | "failed"
  | "archive_failed"

export type LearningFallbackReason =
  | "none"
  | "empty_history"
  | "empty_coach_results"
  | "api_error"
  | "missing_payload"
  | "insufficient_data"
  | "demo"

export type LearningIssueCode =
  | "upload_failed"
  | "create_job_failed"
  | "coach_timeout"
  | "coach_failed"
  | "result_missing"
  | "archive_failed"
  | "task_missing"
  | "history_failed"
  | "payload_incomplete"

export type PracticeTask = {
  id: string
  practice_task_id: string
  title: string
  description: string
  target?: string
  problem?: string
  sourceJobId?: string
  sourceMediaId?: string
  sourceAgent?: "coach"
  goal: string
  status: PracticeTaskStatus
  statusLabel: string
  attempts: PracticeAttempt[]
  createdAt?: string
  updatedAt?: string
  isDemo?: boolean
}

export type PracticeAttempt = {
  attemptId: string
  practice_task_id: string
  jobId?: string
  mediaId?: string
  fileName?: string
  status: PracticeAttemptStatus
  feedbackSummary?: string
  visibleText?: string
  structuredPayload?: Record<string, unknown>
  agentError?: string | null
  createdAt?: string
  isDemo?: boolean
}

export type CoachHistoryItem = {
  job: JobDetailResponse
  result: AgentResultResponse
}

export type LearningPageState = {
  isLoading: boolean
  notice: string | null
  fallbackReason: LearningFallbackReason
}

export type LearningIssue = {
  code: LearningIssueCode
  title: string
  message: string
  taskId?: string
  mediaId?: string
  jobId?: string
  retryLabel?: string
}

export type PracticeRecoveryRecord = {
  practiceTaskId: string
  practiceGoal: string
  sourceJobId?: string
  sourceMediaId?: string
  uploadedMediaId?: string
  uploadedFileName?: string
  createdJobId?: string
  attemptStatus: PracticeAttemptStatus
  visibleText?: string
  feedbackSummary?: string
  updatedAt: string
}
