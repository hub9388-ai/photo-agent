/**
 * API 统一导出
 */

// 基础客户端
export {
  apiClient,
  apiRequest,
  buildApiUrl,
  getApiBaseUrl,
  isMockMode,
  ApiError,
  delay,
  mockResponse,
  mockError,
} from "./client"

// SSE
export {
  SSEConnection,
  connectToJobSSE,
  subscribeJobEvents,
  subscribeToSSE,
  mockSSEStream,
} from "./sse"

// 媒体/素材 API
export {
  uploadMedia,
  uploadManyMedia,
  getAssets,
  getAssetStats,
  getAssetProjects,
  getAsset,
  uploadAssets,
  deleteAsset,
  batchDeleteAssets,
  updateAssetGrade,
  sendToAgent,
  type UploadManyMediaItemResult,
} from "./media"

// 素材库轻量真实化 API
export {
  scoreAssetsWithAssetAgent,
  sendAssetsToAgent,
  sendAssetsToCoach,
  sendAssetsToPost,
} from "./assets"

// Job API
export {
  createJob,
  createAnalysisJob,
  getJobDetail,
  getJobs,
  getJob,
  getAnalysisJob,
  getJobResults,
  listJobs,
  getJobProgress,
  getPostResult,
  getCoachResult,
  cancelJob,
  retryJob,
  retryAgent,
  deleteJob,
} from "./jobs"

// Handoff API
export {
  createHandoff,
} from "./handoff"

// Planning API
export {
  runPlanningAgent,
  type PlanRunRequest,
} from "./planning"

// Learning API
export {
  getLearningProfile,
} from "./learning"
