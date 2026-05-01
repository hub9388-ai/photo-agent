/**
 * Mock 数据统一导出
 */

// Jobs / Analysis
export {
  mockExifData,
  mockAgentProgress,
  mockSSEEvents,
  mockPostResult,
  mockCoachResult,
  mockAnalysisJob,
  mockJobs,
  mockHistoryTasks,
} from "./jobs"

// Events
export {
  mockJobId,
  mockAgentEvents,
} from "./events"

// Results
export {
  mockPostAgentResultResponse,
  mockCoachAgentResultResponse,
  mockJobResultsResponse,
  mockPartialJobResultsResponse,
} from "./results"

// Assets
export {
  mockAssetStats,
  mockAssetProjects,
  createMockAsset,
  mockAssets,
  mockAssetGroups,
  mockSelectedAsset,
  mockAssetFolders,
  mockAssetGridGroups,
  mockAssetDetail,
  demoAssetItems,
} from "./assets"

// Planning
export {
  mockPlanningRequest,
  mockPlanVariants,
  mockPlanningResult,
  mockPlanningPagePlans,
} from "./planning"

// Learning
export {
  mockLearningStats,
  mockPhotoEvaluations,
  mockPracticeTasks,
  mockSkillScores,
  mockWeeklyScores,
} from "./learning"
