import type { UploadMediaResponse } from "@/types/api"
import type { AssetGrade, AssetItem, AssetMediaCategory, AssetMetadata } from "@/types/assets"
import { getApiBaseUrl } from "@/lib/api/client"

function stringValue(value: unknown): string | undefined {
  if (value === undefined || value === null || value === "") return undefined
  return String(value)
}

function numberValue(value: unknown): number | undefined {
  if (typeof value === "number" && Number.isFinite(value)) return value
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value)
    return Number.isFinite(parsed) ? parsed : undefined
  }
  return undefined
}

function formatDecimal(value: number) {
  return Number.isInteger(value) ? String(value) : value.toFixed(1).replace(/\.0$/, "")
}

function formatAperture(value: unknown): string | undefined {
  const raw = stringValue(value)
  if (!raw) return undefined
  if (/^f\//i.test(raw)) return raw
  const parsed = numberValue(raw)
  return parsed ? `f/${formatDecimal(parsed)}` : raw
}

function formatFocalLength(value: unknown): string | undefined {
  const raw = stringValue(value)
  if (!raw) return undefined
  if (/mm$/i.test(raw)) return raw
  const parsed = numberValue(raw)
  return parsed ? `${formatDecimal(parsed)}mm` : raw
}

function formatShutter(value: unknown): string | undefined {
  const raw = stringValue(value)
  if (!raw) return undefined
  if (raw.includes("/") || /s$/i.test(raw)) return raw
  const parsed = numberValue(raw)
  if (!parsed) return raw
  if (parsed >= 1) return `${formatDecimal(parsed)}s`
  return `1/${Math.round(1 / parsed)}s`
}

function cameraName(merged: Record<string, unknown>) {
  const direct = stringValue(merged.camera ?? merged.Camera ?? merged.model ?? merged.Model ?? merged.MakeModel)
  const make = stringValue(merged.make ?? merged.Make)
  const model = stringValue(merged.model ?? merged.Model)
  if (make && model && !direct?.includes(make)) return `${make} ${model}`
  return direct || model || make
}

export function resolveMediaUrl(url?: string | null): string | null {
  if (!url) return null
  if (/^(blob:|data:|https?:\/\/)/i.test(url)) return url
  const base = getApiBaseUrl().replace(/\/$/, "")
  return `${base}${url.startsWith("/") ? "" : "/"}${url}`
}

function mediaCategory(fileName: string, mimeType?: string): AssetMediaCategory {
  const lower = fileName.toLowerCase()
  if (mimeType?.startsWith("video/")) return "video"
  if (mimeType?.startsWith("image/")) return "image"
  if (/\.(dng|raw|arw|cr2|cr3|nef|raf)$/i.test(lower)) return "raw"
  return "unknown"
}

function extractMetadata(media: UploadMediaResponse): AssetMetadata {
  const raw = media.metadata || {}
  const exif = (raw.exif || raw.EXIF || {}) as Record<string, unknown>
  const merged = { ...raw, ...exif } as Record<string, unknown>

  return {
    iso: stringValue(merged.iso ?? merged.ISO ?? merged.ISOSpeedRatings ?? merged.PhotographicSensitivity),
    aperture: formatAperture(merged.aperture ?? merged.f_number ?? merged.fNumber ?? merged.FNumber),
    shutter: formatShutter(merged.shutter ?? merged.exposure_time ?? merged.exposureTime ?? merged.ExposureTime),
    focal_length: formatFocalLength(merged.focal_length ?? merged.focalLength ?? merged.FocalLength),
    camera: cameraName(merged),
    captured_at: stringValue(merged.captured_at ?? merged.capturedAt ?? merged.dateTaken ?? merged.DateTimeOriginal),
    width: numberValue(merged.width),
    height: numberValue(merged.height),
    location: stringValue(merged.location ?? merged.city ?? merged.address),
    file_size: stringValue(merged.file_size ?? merged.fileSize ?? merged.size ?? merged.sizeBytes),
  }
}

function hasRichMetadata(metadata: AssetMetadata) {
  return Boolean(
    metadata.iso ||
      metadata.aperture ||
      metadata.shutter ||
      metadata.focal_length ||
      metadata.camera
  )
}

function inferGrade(metadata: AssetMetadata, previewUrl?: string | null): AssetGrade {
  if (!previewUrl) return "C"
  if (hasRichMetadata(metadata)) return "A"
  if (metadata.width && metadata.height) return "B"
  return "C"
}

function scoreForGrade(grade: AssetGrade, metadata: AssetMetadata) {
  if (grade === "A") return metadata.camera ? 92 : 86
  if (grade === "B") return 78
  if (grade === "C") return 66
  if (grade === "duplicate") return 72
  if (grade === "reject") return 0
  return 58
}

function tagsForAsset(grade: AssetGrade, metadata: AssetMetadata) {
  const tags = new Set<string>()
  if (grade === "A") {
    tags.add("曝光准确")
    tags.add("对焦清晰")
    tags.add("构图稳定")
  }
  if (grade === "B") {
    tags.add("可后期")
    tags.add("主体明确")
  }
  if (grade === "C") {
    tags.add("待复核")
  }
  if (grade === "reject") {
    tags.add("上传失败")
  }
  if (grade === "duplicate") {
    tags.add("相似素材")
  }
  if (!hasRichMetadata(metadata)) tags.add("EXIF 缺失")
  return Array.from(tags)
}

function reasonsForAsset(grade: AssetGrade) {
  if (grade === "reject") return ["上传失败，暂不参与筛选。"]
  if (grade === "A") return ["预览图可用", "基础 EXIF 较完整", "适合送去后期或学习复盘"]
  if (grade === "C") return ["预览图可用", "EXIF 信息不完整，建议人工复核"]
  return ["基于轻量规则生成的素材分档，完整 AssetAgent 索引后续接入。"]
}

export function mediaToAssetItem(media: UploadMediaResponse, index = 0): AssetItem {
  const metadata = extractMetadata(media)
  const previewUrl = resolveMediaUrl(media.previewUrl)
  const grade = inferGrade(metadata, previewUrl)

  return {
    asset_id: `asset_${media.mediaId || Date.now()}_${index}`,
    media_id: media.mediaId,
    file_name: media.fileName,
    preview_url: previewUrl,
    mime_type: media.mimeType,
    media_category: mediaCategory(media.fileName, media.mimeType),
    metadata,
    grade,
    score: scoreForGrade(grade, metadata),
    tags: tagsForAsset(grade, metadata),
    ai_reasons: reasonsForAsset(grade),
    issues: hasRichMetadata(metadata) ? [] : ["未读取到完整 EXIF 信息"],
    duplicate_group_id: null,
    upload_status: "uploaded",
    created_at: new Date().toISOString(),
  }
}

export function failedFileToAssetItem(file: File, message: string, index = 0): AssetItem {
  return {
    asset_id: `asset_failed_${Date.now()}_${index}`,
    media_id: "",
    file_name: file.name,
    preview_url: null,
    mime_type: file.type || "application/octet-stream",
    media_category: mediaCategory(file.name, file.type),
    metadata: { file_size: String(file.size) },
    grade: "reject",
    score: 0,
    tags: ["上传失败"],
    ai_reasons: ["上传失败，素材仍保留在列表中便于重试。"],
    issues: [message],
    upload_status: "failed",
    error_message: message,
    created_at: new Date().toISOString(),
  }
}

export function formatExif(metadata?: AssetMetadata) {
  if (!metadata) return "EXIF 缺失"
  const parts = [metadata.iso && `ISO ${metadata.iso}`, metadata.aperture, metadata.shutter, metadata.focal_length].filter(Boolean)
  return parts.length ? parts.join(" · ") : "EXIF 缺失"
}

export function gradeLabel(grade: AssetGrade) {
  return {
    A: "A档",
    B: "B档",
    C: "C档",
    reject: "淘汰",
    duplicate: "重复",
    unscored: "未评分",
  }[grade]
}
