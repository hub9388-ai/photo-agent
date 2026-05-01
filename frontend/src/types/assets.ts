import type { CreateJobResponse } from "./api"

export type AssetGrade = "A" | "B" | "C" | "reject" | "duplicate" | "unscored"

export type AssetMediaCategory = "image" | "video" | "raw" | "unknown"

export type AssetMetadata = {
  iso?: string
  aperture?: string
  shutter?: string
  focal_length?: string
  camera?: string
  captured_at?: string
  width?: number
  height?: number
  location?: string
  file_size?: string
  brightness?: number
  sharpness?: number
  contrast?: number
  colorfulness?: number
  visual_status?: string
}

export type AssetItem = {
  asset_id: string
  media_id: string
  file_name: string
  preview_url?: string | null
  mime_type?: string
  media_category?: AssetMediaCategory
  metadata?: AssetMetadata
  grade: AssetGrade
  score?: number
  tags: string[]
  ai_reasons: string[]
  issues?: string[]
  duplicate_group_id?: string | null
  upload_status?: "uploading" | "uploaded" | "failed"
  error_message?: string | null
  created_at?: string
  is_demo?: boolean
}

export type AssetFilter = {
  keyword: string
  grade: "all" | AssetGrade
  sort_by: "created_at" | "score" | "file_name"
}

export type HandoffTarget = "post" | "coach"

export type UploadError = {
  file_name: string
  message: string
}

export type AssetHandoffRequest = {
  target_agent: HandoffTarget
  media_ids: string[]
  instruction: string
  context: {
    trigger: "handoff"
    source_agent: "asset"
    source_page: "assets"
    asset_ids: string[]
    asset_grades?: Record<string, AssetGrade>
    asset_scores?: Record<string, number>
    asset_reasons?: Record<string, string[]>
  }
}

export type AssetHandoffResult = {
  job_id: string
  target_agent: HandoffTarget
  method: "handoff" | "job_fallback"
  message: string
  raw?: CreateJobResponse | unknown
}

export type ScoredAssetResponse = {
  assetId: string
  mediaId: string
  fileName: string
  previewUrl?: string | null
  mimeType?: string | null
  mediaCategory?: AssetMediaCategory | string
  metadata?: {
    iso?: string | null
    aperture?: string | null
    shutter?: string | null
    focalLength?: string | null
    camera?: string | null
    capturedAt?: string | null
    width?: number | null
    height?: number | null
    location?: string | null
    fileSize?: string | null
    brightness?: number | null
    sharpness?: number | null
    contrast?: number | null
    colorfulness?: number | null
    visualStatus?: string | null
  }
  grade: AssetGrade
  score?: number | null
  tags: string[]
  aiReasons: string[]
  issues: string[]
  duplicateGroupId?: string | null
  duplicateOf?: string | null
  uploadStatus?: "uploading" | "uploaded" | "failed"
  errorMessage?: string | null
  createdAt?: string | null
}

export type AssetScoreResponse = {
  assets: ScoredAssetResponse[]
  duplicateGroups: Array<Record<string, unknown>>
  scoringMethod: string
  warnings: string[]
}
