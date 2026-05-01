import type { LearningProfileResponse } from "@/types/api"
import { ApiError, apiRequest, isMockMode } from "./client"

export async function getLearningProfile(): Promise<LearningProfileResponse> {
  if (isMockMode()) {
    throw new ApiError(404, "Learning profile is only available in real API mode", "MOCK_MODE")
  }
  return apiRequest<LearningProfileResponse>("/api/learning/profile")
}
