import type { CreateJobRequest, HandoffRequest } from "@/types/api"
import type { AssetHandoffResult, AssetItem, AssetScoreResponse, HandoffTarget, ScoredAssetResponse } from "@/types/assets"
import { resolveMediaUrl } from "@/lib/assets"
import { ApiError, isMockMode, delay } from "./client"
import { apiRequest } from "./client"
import { createHandoff } from "./handoff"
import { createJob } from "./jobs"

function selectedMediaIds(assets: AssetItem[]) {
  return assets
    .filter((asset) => asset.upload_status !== "failed")
    .map((asset) => asset.media_id)
    .filter(Boolean)
}

function handoffContext(assets: AssetItem[]) {
  return {
    source_agent: "asset",
    source_page: "assets",
    asset_ids: assets.map((asset) => asset.asset_id),
    asset_grades: Object.fromEntries(assets.map((asset) => [asset.asset_id, asset.grade])),
    asset_scores: Object.fromEntries(
      assets
        .filter((asset) => typeof asset.score === "number")
        .map((asset) => [asset.asset_id, asset.score as number])
    ),
    asset_reasons: Object.fromEntries(assets.map((asset) => [asset.asset_id, asset.ai_reasons])),
  }
}

function legacyHandoffPayload(target: HandoffTarget, assets: AssetItem[], instruction: string): HandoffRequest {
  return {
    sourceAgent: "asset",
    targetAgent: target,
    mediaIds: selectedMediaIds(assets),
    context: {
      trigger: "handoff",
      instruction,
      ...handoffContext(assets),
    },
  }
}

function fallbackJobPayload(target: HandoffTarget, assets: AssetItem[], instruction: string): CreateJobRequest {
  const context = {
    trigger: "handoff",
    instruction,
    ...handoffContext(assets),
  }
  return {
    type: target === "post" ? "post_process_advice" : "coach_feedback",
    agents: [target],
    media_ids: selectedMediaIds(assets),
    trigger: "handoff",
    user_goal: instruction,
    context,
  }
}

export async function sendAssetsToAgent(
  assets: AssetItem[],
  target: HandoffTarget
): Promise<AssetHandoffResult> {
  const mediaIds = selectedMediaIds(assets)
  if (!mediaIds.length) {
    throw new Error("请先选择至少一张已上传成功的素材。")
  }

  const instruction =
    target === "post"
      ? "请基于素材库筛选理由，给出后期建议"
      : "请基于素材库筛选理由，给出拍摄学习反馈"

  if (isMockMode()) {
    await delay(400)
    return {
      job_id: `job_${Date.now()}`,
      target_agent: target,
      method: "handoff",
      message: target === "post" ? "已创建新的后期分析任务" : "已发送给学习教练",
    }
  }

  try {
    const handoff = await createHandoff(legacyHandoffPayload(target, assets, instruction))
    if (handoff.status !== "accepted" || !handoff.jobId) {
      throw new Error(handoff.message || "Handoff rejected")
    }
    return {
      job_id: handoff.jobId,
      target_agent: target,
      method: "handoff",
      message: handoff.message || (target === "post" ? "已创建新的后期分析任务" : "已发送给学习教练"),
      raw: handoff,
    }
  } catch (error) {
    const canFallback = !(error instanceof ApiError) || error.status === 404 || error.status === 422 || error.status >= 500
    if (!canFallback) throw error
    const job = await createJob(fallbackJobPayload(target, assets, instruction))
    return {
      job_id: job.jobId,
      target_agent: target,
      method: "job_fallback",
      message:
        target === "post"
          ? "Handoff 接口不可用，已降级创建后期任务"
          : "Handoff 接口不可用，已降级创建学习反馈任务",
      raw: job,
    }
  }
}

export function sendAssetsToPost(assets: AssetItem[]) {
  return sendAssetsToAgent(assets, "post")
}

export function sendAssetsToCoach(assets: AssetItem[]) {
  return sendAssetsToAgent(assets, "coach")
}

function scoredAssetToAssetItem(asset: ScoredAssetResponse): AssetItem {
  return {
    asset_id: asset.assetId,
    media_id: asset.mediaId,
    file_name: asset.fileName,
    preview_url: resolveMediaUrl(asset.previewUrl),
    mime_type: asset.mimeType || undefined,
    media_category: (asset.mediaCategory as AssetItem["media_category"]) || "image",
    metadata: {
      iso: asset.metadata?.iso || undefined,
      aperture: asset.metadata?.aperture || undefined,
      shutter: asset.metadata?.shutter || undefined,
      focal_length: asset.metadata?.focalLength || undefined,
      camera: asset.metadata?.camera || undefined,
      captured_at: asset.metadata?.capturedAt || undefined,
      width: asset.metadata?.width || undefined,
      height: asset.metadata?.height || undefined,
      location: asset.metadata?.location || undefined,
      file_size: asset.metadata?.fileSize || undefined,
      brightness: asset.metadata?.brightness || undefined,
      sharpness: asset.metadata?.sharpness || undefined,
      contrast: asset.metadata?.contrast || undefined,
      colorfulness: asset.metadata?.colorfulness || undefined,
      visual_status: asset.metadata?.visualStatus || undefined,
    },
    grade: asset.grade,
    score: typeof asset.score === "number" ? asset.score : undefined,
    tags: asset.tags || [],
    ai_reasons: asset.aiReasons || [],
    issues: asset.issues || [],
    duplicate_group_id: asset.duplicateGroupId || null,
    upload_status: asset.uploadStatus || "uploaded",
    error_message: asset.errorMessage || null,
    created_at: asset.createdAt || undefined,
  }
}

export async function scoreAssetsWithAssetAgent(mediaIds: string[]): Promise<AssetItem[]> {
  if (!mediaIds.length) return []
  const response = await apiRequest<AssetScoreResponse>("/api/agents/asset/score", {
    method: "POST",
    body: JSON.stringify({
      mediaIds,
      cullingPreference: "balanced",
    }),
  })
  return response.assets.map(scoredAssetToAssetItem)
}
