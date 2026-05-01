/**
 * Mock 数据文件 (兼容层)
 * @deprecated 请直接从 @/mocks 导入
 */

// 重新导出所有 mock 数据，保持向后兼容
export {
  // Jobs
  mockExifData,
  mockAgentProgress,
  mockSSEEvents,
  mockPostResult,
  mockCoachResult,
  mockAnalysisJob,
  mockJobs,
  mockHistoryTasks,
  // Events
  mockJobId,
  mockAgentEvents,
  // Results
  mockPostAgentResultResponse,
  mockCoachAgentResultResponse,
  mockJobResultsResponse,
  mockPartialJobResultsResponse,
  // Assets
  mockAssetStats,
  mockAssetProjects,
  createMockAsset,
  mockAssets as mockAssetsList,
  mockAssetGroups,
  mockSelectedAsset,
  mockAssetFolders,
  mockAssetGridGroups,
  mockAssetDetail,
  demoAssetItems,
  // Planning
  mockPlanningRequest,
  mockPlanVariants,
  mockPlanningResult,
  mockPlanningPagePlans,
  // Learning
  mockLearningStats,
  mockPhotoEvaluations,
  mockPracticeTasks,
  mockSkillScores,
  mockWeeklyScores,
} from "@/mocks"

// 旧版兼容：mockAssets 在旧代码中是 AssetStats 类型
export { mockAssetStats as mockAssets } from "@/mocks"

// ============================================================================
// 以下是旧版兼容导出，保持原有代码可用
// ============================================================================

import { mockJobs } from "@/mocks"

// 兼容旧版命名
export const mockSystemStatus = {
  api: "healthy",
  sse: "ready",
  storage: "healthy",
}

export const mockStats = {
  analyzedPhotos: 1248,
  feedbackCount: 892,
  planCount: 36,
  practiceCount: 24,
}

export const mockRecentTasks = mockJobs.map(job => ({
  id: job.id,
  title: job.title,
  type: job.agents.post && job.agents.coach ? "post" : "plan",
  typeLabel: job.agents.post && job.agents.coach ? "post + coach" : "plan",
  status: job.status,
  statusLabel: job.status === "completed" ? "已完成" : job.status === "running" ? "进行中" : "待处理",
  time: "2 小时前",
}))

// 旧版对象格式兼容（覆盖从 @/mocks 导入的数组版本）
export const mockSkillScoresLegacy = {
  exposureControl: 75,
  composition: 62,
  colorPerception: 88,
  postProcessing: 55,
}
