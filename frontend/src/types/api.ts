/**
 * PhotoAI API 类型定义
 * 定义所有后端 API 契约对应的数据类型
 */

// ============================================================================
// 通用类型
// ============================================================================

export type AgentType = "post" | "coach" | "plan" | "asset"
export type JobStatus =
  | "queued"
  | "running"
  | "streaming"
  | "completed"
  | "partial_completed"
  | "failed"
  | "cancelled"

export type TaskStatus = JobStatus | "pending"
export type JobType =
  | "photo_review"
  | "post_process_advice"
  | "coach_feedback"
  | "asset_indexing"
  | "trip_planning"
  | "batch_review"
export type JobTrigger = "user" | "handoff" | "system" | "retry"
export type AgentResultStatus = "succeeded" | "failed"
export type Grade = "A" | "B" | "C" | "rejected" | "duplicate"

// ============================================================================
// Backend API Contract 类型
// 后端请求体 MVP 使用 snake_case；响应 JSON 暴露 camelCase。
// ============================================================================

export interface MediaMetadata {
  width?: number
  height?: number
  exif?: Record<string, unknown>
  [key: string]: unknown
}

export interface UploadMediaResponse {
  mediaId: string
  previewUrl: string
  fileName: string
  mimeType: string
  metadata: MediaMetadata
  storageUri?: string | null
}

export interface CreateJobRequest {
  type: JobType
  media_ids?: string[]
  agents: AgentType[]
  user_goal?: string
  trigger?: JobTrigger
  context?: Record<string, unknown>
}

export interface CreateJobResponse {
  jobId: string
  status: JobStatus
  eventsUrl: string
  resultsUrl: string
  agent?: AgentType | null
}

export interface JobDetailResponse {
  userGoal?: string
  jobId: string
  type: JobType
  trigger: JobTrigger
  status: JobStatus
  agents: AgentType[]
  mediaIds: string[]
  progress?: number | null
  context: Record<string, unknown>
  createdAt: string
  updatedAt: string
}

export type AgentEventType =
  | "job.created"
  | "job.started"
  | "agent.started"
  | "agent.progress"
  | "agent.delta"
  | "agent.result"
  | "agent.error"
  | "job.completed"
  | "job.partial_completed"
  | "job.failed"

export interface AgentEventMessage {
  eventId: string
  seq: number
  jobId: string
  agent?: AgentType | null
  type: AgentEventType
  message?: string | null
  payload: Record<string, unknown>
  createdAt: string
}

export interface AgentResultResponse {
  agent: AgentType
  status: AgentResultStatus
  summary: string
  visibleText: string
  structuredPayload: Record<string, unknown>
  warnings: string[]
  agentError?: string | null
  createdAt: string
}

export interface JobResultsResponse {
  jobId: string
  status: JobStatus
  results: AgentResultResponse[]
}

export interface JobListResponse {
  jobs: JobDetailResponse[]
  count: number
}

export interface HandoffRequest {
  sourceAgent: AgentType
  targetAgent: AgentType
  mediaIds: string[]
  jobId?: string
  context?: Record<string, unknown>
}

export interface HandoffResponse {
  handoffId: string
  jobId?: string | null
  status: "accepted" | "rejected"
  message?: string | null
}

export interface ErrorResponse {
  code: string
  message: string
  details?: Record<string, unknown> | null
}

export interface ApiResponse<T> {
  success: boolean
  data?: T
  error?: {
    code: string
    message: string
  }
}

export interface PaginatedResponse<T> {
  items: T[]
  pagination: {
    page: number
    pageSize: number
    total: number
    totalPages: number
  }
}

// ============================================================================
// Dashboard 相关类型
// ============================================================================

export interface SystemStatus {
  api: "healthy" | "degraded" | "down"
  sse: "ready" | "connecting" | "disconnected"
  storage: "healthy" | "full" | "error"
}

export interface DashboardStats {
  analyzedPhotos: number
  feedbackCount: number
  planCount: number
  practiceCount: number
}

export interface LearningProfileResponse {
  streakDays: number
  completedPracticeTasks: number
  currentLevel: string
  coachFeedbackCount: number
  source: "job_result_profile"
  generatedAt: string
}

export interface RecentTask {
  id: string
  title: string
  type: AgentType | string
  typeLabel: string
  status: TaskStatus
  statusLabel: string
  time: string
}

// ============================================================================
// Analysis (Jobs) 相关类型
// ============================================================================

export interface AnalysisJob {
  id: string
  title: string
  status: TaskStatus
  progress: number
  createdAt: string
  updatedAt: string
  images: AnalysisImage[]
  agents: {
    post?: PostAgentResult
    coach?: CoachAgentResult
  }
}

export interface AnalysisImage {
  id: string
  filename: string
  url: string
  thumbnailUrl: string
  exif: ExifData
}

export interface ExifData {
  iso?: number
  aperture?: string
  shutterSpeed?: string
  focalLength?: string
  cameraModel?: string
  lensModel?: string
  dateTaken?: string
}

export interface AgentProgress {
  name: string
  progress: number
  status: "pending" | "running" | "completed" | "failed"
  currentStep: string
  steps: AgentStep[]
}

export interface AgentStep {
  name: string
  status: "pending" | "running" | "completed"
}

export interface SSEEvent {
  time: string
  agent: AgentType
  message: string
}

export interface PostAgentResult {
  status: "completed" | "failed"
  summary: string
  suggestions: PostSuggestion[]
  params: PostParams
}

export interface PostSuggestion {
  category: string
  items: string[]
}

export interface PostParams {
  exposure: string
  contrast: string
  highlights: string
  shadows: string
  whites?: string
  blacks?: string
  clarity?: string
  vibrance?: string
  saturation?: string
}

export interface CoachAgentResult {
  status: "completed" | "failed"
  sections: CoachSection[]
  practiceTask?: PracticeTaskInfo
}

export interface CoachSection {
  title: string
  icon: "check" | "alert" | "map" | "star"
  items: string[]
}

export interface PracticeTaskInfo {
  title: string
  description: string
  isChallenge?: boolean
}

// ============================================================================
// Assets 相关类型
// ============================================================================

export interface AssetProject {
  id: string
  name: string
  count: number
  children?: AssetFolder[]
}

export interface AssetFolder {
  id: string
  name: string
  count: number
}

export interface AssetStats {
  total: number
  gradeA: number
  gradeB: number
  gradeC: number
  rejected: number
  duplicate: number
}

export interface Asset {
  id: string
  filename: string
  grade: Grade
  url: string
  thumbnailUrl: string
  exif: ExifData
  metadata: AssetMetadata
  aiAnalysis: AssetAIAnalysis
}

export interface AssetMetadata {
  dateTaken: string
  location?: string
  resolution: string
  fileSize: string
  tags: string[]
}

export interface AssetAIAnalysis {
  qualityScore: number
  tags: AssetTag[]
  note: string
  handoffAgents: AgentType[]
}

export interface AssetTag {
  name: string
  type: "positive" | "warning" | "negative" | "neutral"
}

export interface AssetGroup {
  id: string
  name: string
  assets: Asset[]
  isSimilarGroup?: boolean
}

// ============================================================================
// Planning 相关类型
// ============================================================================

export interface PlanningRequest {
  city: string
  date: string
  timeSlots: string[]
  subject: string
  equipment: string
  budget: string
  referenceImages: string[]
  requirements: string
}

export interface PlanningResult {
  id: string
  title: string
  plans: PlanVariant[]
}

export interface PlanVariant {
  id: string
  name: string
  spots: PlanSpot[]
  info: PlanInfo[]
}

export interface PlanSpot {
  time: string
  title: string
  description: string
  position: string
  lighting: string
  method: string
}

export interface PlanInfo {
  icon: "check" | "camera" | "sun" | "wand"
  title: string
  content: string
}

// ============================================================================
// Learning 相关类型
// ============================================================================

export interface LearningStats {
  streak: number
  completed: number
  level: string
}

export interface PhotoEvaluation {
  id: string
  file: string
  thumbnailUrl: string
  sourceJobId?: string
  source: string
  status: "pending_review" | "mastered"
  statusLabel: string
  comment: string
  suggestion: string
}

export interface PracticeTask {
  id: string
  practice_task_id?: string
  title: string
  description: string
  target?: string
  problem?: string
  sourceJobId?: string
  sourceMediaId?: string
  sourceAgent?: "coach"
  goal?: string
  status: "completed" | "in_progress" | "not_started" | "needs_retry" | "submitted" | "failed"
  statusLabel: string
  attempts?: PracticeAttempt[]
}

export interface PracticeAttempt {
  attemptId: string
  practice_task_id?: string
  jobId?: string
  mediaId?: string
  fileName?: string
  status:
    | "running"
    | "uploading"
    | "uploaded"
    | "job_created"
    | "reviewing"
    | "completed"
    | "needs_retry"
    | "failed"
    | "archive_failed"
  feedbackSummary?: string
  visibleText?: string
  structuredPayload?: Record<string, unknown>
  agentError?: string | null
  createdAt?: string
}

export interface SkillScore {
  name: string
  score: number
  color: string
  icon?: string
}

export interface WeeklyScore {
  week: string
  score: number
}

// ============================================================================
// History 相关类型
// ============================================================================

export interface HistoryTask {
  id: string
  title: string
  type: AgentType | string
  typeLabel: string
  status: TaskStatus
  statusLabel: string
  summary: string
  time: string
}

export interface HistoryFilter {
  search?: string
  type?: AgentType | null
  status?: TaskStatus | null
  startDate?: string
  endDate?: string
}
