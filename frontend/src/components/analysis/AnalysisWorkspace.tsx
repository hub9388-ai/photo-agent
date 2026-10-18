"use client"

import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { AlertCircle, ChevronLeft } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  createJob,
  getJob,
  getJobResults,
  getMedia,
  retryAgent,
  subscribeJobEvents,
  uploadMedia,
  buildApiUrl,
} from "@/lib/api"
import { mediaToAssetItem } from "@/lib/assets/asset-mappers"
import {
  mockAgentEvents,
  mockJobResultsResponse,
  mockPartialJobResultsResponse,
} from "@/mocks"
import type { AssetItem } from "@/types/assets"
import type {
  AgentEventMessage,
  AgentResultResponse,
  AgentType,
  JobResultsResponse,
  JobStatus,
  UploadMediaResponse,
} from "@/types/api"

import { AgentProgressCard, type AgentProgress } from "./AgentProgressCard"
import { AnalysisResultPanel, type PostParameter } from "./AnalysisResultPanel"
import { LiveEventStream, type SSEEvent } from "./LiveEventStream"
import { UploadPlaceholder, UploadPreviewPanel } from "./UploadPreviewPanel"

type ReviewAgent = Extract<AgentType, "post" | "coach">

interface AnalysisWorkspaceProps {
  initialJobId?: string
}

interface PostSuggestion {
  category: string
  items: string[]
}

interface PostPanelResult {
  summary: string
  suggestions: PostSuggestion[]
  params?: Record<string, string>
  parameters?: PostParameter[]
  originalText?: string
  sourceNote?: string
}

interface CoachPanelResult {
  sections: { title: string; items: string[] }[]
  originalText?: string
  practiceTask?: {
    title: string
    description: string
    isChallenge?: boolean
    requirements?: string[]
    acceptance?: string[]
  }
}

const agentNames: Record<ReviewAgent, string> = {
  post: "Post Agent（后期分析）",
  coach: "Coach Agent（学习教练）",
}

const AGENT_TIMEOUT_MS = 90_000
const SAVED_ANALYSIS_CACHE_KEY = "photoai.savedAnalysis.v1"
const PLANNING_DRAFT_CACHE_KEY = "photoai.planningDraft.v1"
const PLANNING_PRESET_DRAFT_KEY = "photoai.planningPresetDraft.v1"
const ASSET_LIBRARY_CACHE_KEY = "photoai.assetLibrary.v1"

const demoPhotoSvg = encodeURIComponent(`
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 900">
  <defs>
    <linearGradient id="sky" x1="0" x2="1" y1="0" y2="1">
      <stop offset="0%" stop-color="#f7b267"/>
      <stop offset="46%" stop-color="#9cc9ff"/>
      <stop offset="100%" stop-color="#0f2747"/>
    </linearGradient>
    <linearGradient id="water" x1="0" x2="0" y1="0" y2="1">
      <stop offset="0%" stop-color="#7aa7d9"/>
      <stop offset="100%" stop-color="#10213a"/>
    </linearGradient>
  </defs>
  <rect width="1200" height="900" fill="url(#sky)"/>
  <circle cx="865" cy="230" r="95" fill="#ffd08a" opacity=".9"/>
  <path d="M0 565 L210 330 L375 570 Z" fill="#52657c"/>
  <path d="M225 570 L520 185 L790 570 Z" fill="#f8fafc"/>
  <path d="M360 570 L610 270 L965 570 Z" fill="#94a3b8"/>
  <rect y="570" width="1200" height="330" fill="url(#water)"/>
  <path d="M0 665 C220 620 360 730 565 670 C760 615 905 665 1200 628 L1200 900 L0 900 Z" fill="#0f172a" opacity=".34"/>
  <path d="M420 610 L760 610 L690 660 L500 660 Z" fill="#0f172a" opacity=".55"/>
</svg>
`)

const demoMedia: UploadMediaResponse = {
  mediaId: "media_demo_landscape",
  previewUrl: `data:image/svg+xml;charset=utf-8,${demoPhotoSvg}`,
  fileName: "demo_landscape.jpg",
  mimeType: "image/jpeg",
  storageUri: "demo://landscape",
  metadata: {
    width: 1200,
    height: 900,
    exif: {
      ISO: 200,
      FNumber: "f/8",
      ExposureTime: "1/125s",
      FocalLength: "35mm",
      Model: "Demo Camera",
    },
  },
}

const defaultSteps: Record<ReviewAgent, string[]> = {
  post: ["曝光", "色彩", "后期方向", "参数建议"],
  coach: ["构图", "优点问题", "拍摄建议", "练习任务"],
}

const initialAgentState: Record<ReviewAgent, AgentProgress> = {
  post: makeAgentProgress("post", 0, "pending", "等待创建分析任务"),
  coach: makeAgentProgress("coach", 0, "pending", "等待创建分析任务"),
}

const emptyPostResult: PostPanelResult = {
  summary: "等待 Post Agent 生成后期建议。",
  suggestions: [
    {
      category: "实时结果",
      items: ["任务完成或部分完成后，这里会展示真实后期建议。"],
    },
  ],
}

const emptyCoachResult: CoachPanelResult = {
  sections: [
    {
      title: "实时结果",
      items: ["任务完成或部分完成后，这里会展示真实学习反馈。"],
    },
  ],
}

function makeAgentProgress(
  agent: ReviewAgent,
  progress: number,
  status: AgentProgress["status"],
  currentStep: string
): AgentProgress {
  const boundedProgress = Math.max(0, Math.min(100, Math.round(progress)))
  const runningIndex = Math.min(
    defaultSteps[agent].length - 1,
    Math.floor((boundedProgress / 100) * defaultSteps[agent].length)
  )

  return {
    name: agentNames[agent],
    progress: boundedProgress,
    status,
    currentStep,
    steps: defaultSteps[agent].map((name, index) => {
      if (status === "completed") return { name, status: "completed" }
      if (status === "failed") {
        return {
          name,
          status: index < runningIndex ? "completed" : "pending",
        }
      }
      if (status === "pending") return { name, status: "pending" }
      if (index < runningIndex) return { name, status: "completed" }
      if (index === runningIndex) return { name, status: "running" }
      return { name, status: "pending" }
    }),
  }
}

function normalizeProgress(value: unknown, fallback: number): number {
  if (typeof value !== "number" || Number.isNaN(value)) return fallback
  return value <= 1 ? value * 100 : value
}

function formatTime(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return "--:--:--"
  return date.toLocaleTimeString("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  })
}

function normalizePreviewUrl(url?: string): string | undefined {
  if (!url) return undefined
  if (url.startsWith("blob:") || url.startsWith("http://") || url.startsWith("https://")) {
    return url
  }
  return buildApiUrl(url)
}

function exifValue(exif: Record<string, unknown> | undefined, keys: string[]): string | undefined {
  if (!exif) return undefined
  for (const key of keys) {
    const value = exif[key]
    if (typeof value === "string" || typeof value === "number") return String(value)
  }
  return undefined
}

function toExif(media: UploadMediaResponse | null) {
  const exif = media?.metadata?.exif as Record<string, unknown> | undefined
  return {
    iso: exifValue(exif, ["ISO", "iso", "ISOSpeedRatings"]),
    aperture: exifValue(exif, ["FNumber", "aperture", "ApertureValue"]),
    shutterSpeed: exifValue(exif, ["ExposureTime", "shutterSpeed", "ShutterSpeedValue"]),
    focalLength: exifValue(exif, ["FocalLength", "focalLength"]),
    cameraModel: exifValue(exif, ["Model", "cameraModel"]),
  }
}

function toStringList(value: unknown): string[] {
  if (!value) return []
  if (Array.isArray(value)) {
    return value
      .map((item) => {
        if (typeof item === "string") return item
        if (item && typeof item === "object") return JSON.stringify(item)
        return String(item)
      })
      .filter(Boolean)
  }
  if (typeof value === "string") return value ? [value] : []
  if (typeof value === "object") return Object.values(value).flatMap(toStringList)
  return [String(value)]
}

const parameterLabels: Record<string, { label: string; meaning: string; unit?: string }> = {
  exposure: { label: "曝光补偿", meaning: "控制整张照片的整体明暗", unit: "EV" },
  exposure2012: { label: "曝光补偿", meaning: "控制整张照片的整体明暗", unit: "EV" },
  contrast: { label: "对比度", meaning: "拉开明暗反差，增强画面力度" },
  contrast2012: { label: "对比度", meaning: "拉开明暗反差，增强画面力度" },
  highlights: { label: "高光", meaning: "控制亮部明暗" },
  highlights2012: { label: "高光", meaning: "控制亮部明暗" },
  shadows: { label: "阴影", meaning: "控制暗部明暗" },
  shadows2012: { label: "阴影", meaning: "控制暗部明暗" },
  whites: { label: "白色色阶", meaning: "控制最亮区域的白场强度" },
  whites2012: { label: "白色色阶", meaning: "控制最亮区域的白场强度" },
  blacks: { label: "黑色色阶", meaning: "控制最暗区域的黑场和厚重感" },
  blacks2012: { label: "黑色色阶", meaning: "控制最暗区域的黑场和厚重感" },
  clarity: { label: "清晰度", meaning: "增强中间调局部对比，让纹理更明确" },
  clarity2012: { label: "清晰度", meaning: "增强中间调局部对比，让纹理更明确" },
  dehaze: { label: "去朦胧", meaning: "增强空气透视和远景通透度" },
  dehaze2012: { label: "去朦胧", meaning: "增强空气透视和远景通透度" },
  vibrance: { label: "自然饱和度", meaning: "调整低饱和颜色的鲜艳程度" },
  saturation: { label: "饱和度", meaning: "整体增加或减少色彩浓度" },
  temperature: { label: "色温", meaning: "调整画面冷暖倾向", unit: "K" },
  temp: { label: "色温", meaning: "调整画面冷暖倾向", unit: "K" },
  tint: { label: "色调", meaning: "调整绿色与洋红之间的偏色" },
  noiseReduction: { label: "降噪", meaning: "减少高 ISO 或暗部提亮后的噪点" },
  sharpening: { label: "锐化", meaning: "增强边缘细节，但过高会显得生硬" },
}

function normalizeParamKey(key: string): string {
  return key.replace(/[_\s-]/g, "").replace(/^xmp/i, "")
}

function getParameterMeta(key: string) {
  const normalized = normalizeParamKey(key)
  const foundKey = Object.keys(parameterLabels).find(
    (candidate) => normalizeParamKey(candidate).toLowerCase() === normalized.toLowerCase()
  )
  return foundKey ? parameterLabels[foundKey] : { label: key, meaning: "影响局部或全局观感，需要结合个人审美微调" }
}

function parseNumericValue(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value
  if (typeof value !== "string") return null
  const match = value.match(/[-+]?\d+(?:\.\d+)?/)
  return match ? Number(match[0]) : null
}

function formatSignedValue(value: number, unit = ""): string {
  const absValue = Math.abs(value)
  const fixed = absValue.toString()
  return `${value > 0 ? "+" : value < 0 ? "-" : ""}${fixed}${unit ? ` ${unit}` : ""}`
}

function formatParameterSuggestion(key: string, value: unknown): string {
  const meta = getParameterMeta(key)
  const numericValue = parseNumericValue(value)
  if (numericValue === null) {
    return `${meta.label}：${String(value)}。含义：${meta.meaning}。建议作为方向参考，根据个人审美和原片宽容度微调。`
  }

  const direction =
    numericValue > 0 ? "增加" : numericValue < 0 ? "降低" : "保持"
  return `${meta.label}：${typeof value === "string" ? value : formatSignedValue(numericValue, meta.unit)}（${direction}）`
}

function parameterEffect(key: string, value: unknown): string {
  const numeric = parseNumericValue(value)
  if (numeric === null || numeric === 0) return getParameterMeta(key).meaning
  const normalized = normalizeParamKey(key).toLowerCase().replace(/2012$/, "")
  const effects: Record<string, [string, string]> = {
    exposure: ["降低整体曝光", "提高整体曝光"],
    highlights: ["压低亮部", "提亮亮部"],
    shadows: ["压暗暗部", "提亮暗部"],
    blacks: ["压低黑场", "抬高黑场"],
    whites: ["压低白场", "抬高白场"],
    contrast: ["减弱明暗反差", "增强明暗反差"],
    saturation: ["降低色彩浓度", "增加色彩浓度"],
    vibrance: ["降低自然饱和度", "增加自然饱和度"],
    clarity: ["减弱局部纹理对比", "增强局部纹理对比"],
    dehaze: ["降低去朦胧强度", "增加去朦胧强度"],
  }
  return effects[normalized]?.[numeric < 0 ? 0 : 1] ?? getParameterMeta(key).meaning
}

function mapParameterRows(value: unknown): PostParameter[] {
  if (!value || typeof value !== "object" || Array.isArray(value)) return []
  return Object.entries(value as Record<string, unknown>)
    .filter(([, item]) => item !== null && item !== undefined && item !== "")
    .map(([key, item]) => ({
      key,
      label: getParameterMeta(key).label,
      value: typeof item === "number" ? formatSignedValue(item, getParameterMeta(key).unit) : String(item),
      effect: parameterEffect(key, item),
    }))
}

function cleanSuggestion(value: string): string {
  return value.replace(/^[\s•●▸·◎-]+/, "").trim()
}

function formatParameterObject(value: unknown): string[] {
  if (!value || typeof value !== "object" || Array.isArray(value)) return []
  return Object.entries(value as Record<string, unknown>)
    .filter(([, item]) => item !== null && item !== undefined && item !== "")
    .map(([key, item]) => formatParameterSuggestion(key, item))
}

function resultPayload(result: AgentResultResponse, key: string): unknown {
  return result.structuredPayload?.[key]
}

function uniqueItems(items: string[]): string[] {
  return Array.from(new Set(items.filter(Boolean)))
}

function extractStyleDirectionItems(
  payload: Record<string, unknown>,
  result: AgentResultResponse,
  userPreference: string
): string[] {
  const directions = toStringList(
    payload.style_directions ?? payload.styleDirections ?? payload.editing_style ??
    payload.editingStyle ?? payload.post_style ?? payload.postStyle
  )
  if (directions.length) return directions.slice(0, 4)
  // Never invent photo-specific advice from generic style keywords.
  return [result.summary || userPreference].filter(Boolean)
}

function extractParameterItems(adjustmentSource: unknown, xmpSource: unknown): string[] {
  const xmpParams = formatParameterObject(xmpSource)
  return xmpParams.length ? xmpParams : formatParameterObject(adjustmentSource)
}

function mapPostResult(result?: AgentResultResponse, userPreference = ""): PostPanelResult {
  if (!result) return emptyPostResult
  if (result.status === "failed") {
    return {
      summary: result.summary || "Post Agent 暂未完成，已保留其他成功结果。",
      suggestions: [
        {
          category: "错误信息",
          items: [result.agentError || "后期分析失败，可稍后重试 Post Agent。"],
        },
      ],
    }
  }

  const summary = result.summary || "Post Agent 已生成后期建议。"
  const payload = result.structuredPayload || {}
  const suggestions: PostSuggestion[] = []

  const mainIssues = toStringList(payload.main_issues ?? payload.mainIssues)
  const adjustmentSource = payload.adjustments
  const xmpSource = payload.xmp_params ?? payload.xmpParams
  const styleDirections = extractStyleDirectionItems(payload, result, userPreference)
  const parameterItems = extractParameterItems(adjustmentSource, xmpSource)

  if (mainIssues.length) suggestions.push({ category: "主要问题", items: mainIssues.map(cleanSuggestion) })
  if (styleDirections.length && styleDirections[0] !== summary) suggestions.push({
    category: "处理方向",
    items: styleDirections.map(cleanSuggestion),
  })
  const actions = toStringList(adjustmentSource).map(cleanSuggestion)
  if (actions.length) suggestions.push({ category: "调整建议", items: actions })
  if (parameterItems.length) {
    suggestions.push({
      category: "模型参考参数",
      items: parameterItems,
    })
  }
  if (!suggestions.length) {
    suggestions.push({
      category: "后期建议",
      items: [result.visibleText || result.summary || "后期建议已生成。"],
    })
  }

  return {
    summary,
    suggestions,
    parameters: mapParameterRows(xmpSource),
    originalText: result.visibleText || "",
    sourceNote: String(payload.source_note || ""),
  }
}

function compactFeedbackItem(item: string): string {
  // Keep the complete feedback. Readability must not discard model content.
  return item
    .replace(/^[•·\s]+/, "")
    .replace(/^[-\d.、\s]+/, "")
    .trim()
}

function compactFeedbackList(items: string[]): string[] {
  return uniqueItems(items.map((item) => compactFeedbackItem(item)))
}

function mapCoachResult(result?: AgentResultResponse): CoachPanelResult {
  if (!result) return emptyCoachResult
  if (result.status === "failed") {
    return {
      sections: [
        {
          title: "错误信息",
          items: [result.agentError || "学习反馈失败，可稍后重试 Coach Agent。"],
        },
      ],
    }
  }

  const strengths = compactFeedbackList(toStringList(resultPayload(result, "strengths")))
  const improvements = compactFeedbackList(toStringList(resultPayload(result, "improvements")))
  const exerciseSource = resultPayload(result, "next_exercise") ?? resultPayload(result, "nextExercise")
  const exercise = exerciseSource && typeof exerciseSource === "object" && !Array.isArray(exerciseSource)
    ? exerciseSource as Record<string, unknown> : null
  const nextExercise = exercise ? [] : compactFeedbackList(toStringList(exerciseSource))

  const sections = [
    strengths.length ? { title: "优点", items: strengths } : undefined,
    improvements.length ? { title: "可改进点", items: improvements } : undefined,
    nextExercise.length ? { title: "下次怎么拍", items: nextExercise } : undefined,
  ].filter(Boolean) as CoachPanelResult["sections"]

  if (!sections.length) {
    sections.push({
      title: "学习反馈",
      items: compactFeedbackList(toStringList(result.visibleText || result.summary || "学习反馈已生成。")),
    })
  }

  return {
    sections,
    originalText: result.visibleText || "",
    practiceTask: exercise
      ? {
          title: typeof exercise.title === "string" ? exercise.title : "练习任务",
          description: typeof exercise.scene === "string" ? exercise.scene : "",
          requirements: toStringList(exercise.requirements),
          acceptance: toStringList(exercise.acceptance),
        }
      : nextExercise.length
      ? {
          title: "练习任务",
          description: nextExercise.join("；"),
          isChallenge: true,
        }
      : undefined,
  }
}

function statusLabel(status: JobStatus | "idle" | "uploading" | "creating"): string {
  const labels = {
    idle: "待上传",
    uploading: "上传中",
    creating: "创建中",
    queued: "排队中",
    running: "运行中",
    streaming: "运行中",
    completed: "已完成",
    partial_completed: "部分完成",
    failed: "失败",
    cancelled: "已取消",
  }
  return labels[status]
}

function statusBadgeClass(status: JobStatus | "idle" | "uploading" | "creating"): string {
  if (status === "completed") return "bg-green-50 text-green-700 border-green-200"
  if (status === "partial_completed") return "bg-amber-50 text-amber-700 border-amber-200"
  if (status === "failed" || status === "cancelled") return "bg-red-50 text-red-700 border-red-200"
  return "bg-blue-50 text-blue-700 border-blue-200"
}

function isTerminalStatus(status: JobStatus | "idle" | "uploading" | "creating"): boolean {
  return (
    status === "completed" ||
    status === "partial_completed" ||
    status === "failed" ||
    status === "cancelled"
  )
}

function mockEventsToStream(jobId: string): SSEEvent[] {
  return mockAgentEvents.map((event) => ({
    time: formatTime(event.createdAt),
    agent: event.agent ?? "job",
    message: event.jobId === jobId ? event.message || event.type : event.message || event.type,
  }))
}

function sanitizeFileName(value: string) {
  return value.replace(/[\\/:*?"<>|]/g, "_").replace(/\s+/g, "_").slice(0, 80)
}

function markdownList(items: string[]) {
  return items.length ? items.map((item) => `- ${item}`).join("\n") : "- 暂无"
}

function buildAnalysisReport(input: {
  jobId: string | null
  media: UploadMediaResponse | null
  preference: string
  postResult: PostPanelResult
  coachResult: CoachPanelResult
  events: SSEEvent[]
}) {
  const { jobId, media, preference, postResult, coachResult, events } = input
  const postSections = postResult.suggestions
    .map((section) => `### ${section.category}\n\n${markdownList(section.items)}`)
    .join("\n\n")
  const coachSections = coachResult.sections
    .map((section) => `### ${section.title}\n\n${markdownList(section.items)}`)
    .join("\n\n")
  const eventLines = events.slice(-20).map((event) => `- ${event.time} [${event.agent}] ${event.message}`)

  return [
    "# PhotoAI 分析报告",
    "",
    `- 任务 ID：${jobId || "未创建任务"}`,
    `- 文件名：${media?.fileName || "未记录"}`,
    `- Media ID：${media?.mediaId || "未记录"}`,
    `- 分析偏好：${preference || "未填写"}`,
    `- 导出时间：${new Date().toLocaleString("zh-CN", { hour12: false })}`,
    "",
    "## 后期建议",
    "",
    `**摘要**：${postResult.summary}`,
    "",
    postSections || "暂无后期建议。",
    postResult.sourceNote ? `\n### 分析依据\n\n${postResult.sourceNote}` : "",
    postResult.originalText ? `\n### Post Agent 完整原文\n\n${postResult.originalText}` : "",
    "",
    "## 学习反馈",
    "",
    coachSections || "暂无学习反馈。",
    coachResult.practiceTask
      ? `\n### 练习任务\n\n- ${coachResult.practiceTask.title}：${coachResult.practiceTask.description}`
      : "",
    coachResult.practiceTask?.requirements?.length
      ? `\n### 练习要求\n\n${markdownList(coachResult.practiceTask.requirements)}` : "",
    coachResult.practiceTask?.acceptance?.length
      ? `\n### 验收标准\n\n${markdownList(coachResult.practiceTask.acceptance)}` : "",
    coachResult.originalText ? `\n### Coach Agent 完整原文\n\n${coachResult.originalText}` : "",
    "",
    "## 最近事件",
    "",
    eventLines.length ? eventLines.join("\n") : "- 暂无实时事件记录",
    "",
  ].join("\n")
}

function downloadTextFile(fileName: string, content: string) {
  const blob = new Blob([content], { type: "text/markdown;charset=utf-8" })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement("a")
  anchor.href = url
  anchor.download = fileName
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
}

function isAssetItem(value: unknown): value is AssetItem {
  if (!value || typeof value !== "object") return false
  const record = value as Record<string, unknown>
  return typeof record.asset_id === "string" && typeof record.media_id === "string"
}

function readCachedAssets(): AssetItem[] {
  const raw = window.localStorage.getItem(ASSET_LIBRARY_CACHE_KEY)
  if (!raw) return []
  try {
    const parsed = JSON.parse(raw) as unknown
    return Array.isArray(parsed) ? parsed.filter(isAssetItem) : []
  } catch {
    return []
  }
}

function saveAnalysisMediaToAssets(media: UploadMediaResponse, postResult?: AgentResultResponse, coachResult?: AgentResultResponse) {
  const currentAssets = readCachedAssets()
  const mappedAsset = mediaToAssetItem(media, currentAssets.length)
  const enrichedAsset: AssetItem = {
    ...mappedAsset,
    asset_id: currentAssets.find((asset) => asset.media_id === media.mediaId)?.asset_id ?? mappedAsset.asset_id,
    tags: Array.from(new Set([...mappedAsset.tags, "来自分析页", "可后期", "可学习"])),
    ai_reasons: Array.from(
      new Set([
        "从分析页保存到素材库，后续可继续进行筛选、后期或学习复盘。",
        postResult?.summary,
        coachResult?.summary,
        ...mappedAsset.ai_reasons,
      ].filter((item): item is string => Boolean(item)))
    ).slice(0, 5),
  }
  const nextAssets = [
    enrichedAsset,
    ...currentAssets.filter((asset) => asset.media_id !== media.mediaId),
  ]
  window.localStorage.setItem(ASSET_LIBRARY_CACHE_KEY, JSON.stringify(nextAssets))
  return enrichedAsset
}

export function AnalysisWorkspace({ initialJobId }: AnalysisWorkspaceProps) {
  const router = useRouter()
  const unsubscribeRef = useRef<(() => void) | null>(null)
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const [media, setMedia] = useState<UploadMediaResponse | null>(null)
  const [jobId, setJobId] = useState<string | null>(initialJobId ?? null)
  const [jobStatus, setJobStatus] = useState<JobStatus | "idle" | "uploading" | "creating">(
    initialJobId ? "running" : "idle"
  )
  const [preference, setPreference] = useState("")
  const [events, setEvents] = useState<SSEEvent[]>([])
  const [agentProgress, setAgentProgress] = useState<Record<ReviewAgent, AgentProgress>>(
    initialAgentState
  )
  const [results, setResults] = useState<AgentResultResponse[]>([])
  const [error, setError] = useState<string | null>(null)
  const [demoNotice, setDemoNotice] = useState<string | null>(null)
  const activeJobRef = useRef<string | null>(initialJobId ?? null)

  const previewUrl = normalizePreviewUrl(media?.previewUrl)
  const isBusy = jobStatus === "uploading" || jobStatus === "creating"
  const hasMediaOrJob = Boolean(media || jobId)

  const resultByAgent = useMemo(() => {
    return Object.fromEntries(results.map((result) => [result.agent, result])) as Partial<
      Record<AgentType, AgentResultResponse>
    >
  }, [results])

  const postPanelResult = useMemo(
    () => mapPostResult(resultByAgent.post, preference),
    [preference, resultByAgent.post]
  )
  const coachPanelResult = useMemo(
    () => mapCoachResult(resultByAgent.coach),
    [resultByAgent.coach]
  )

  const failedAgents = useMemo(() => {
    return results
      .filter((result) => result.status === "failed" && (result.agent === "post" || result.agent === "coach"))
      .map((result) => result.agent as ReviewAgent)
  }, [results])

  const successfulResultCount = results.filter((result) => result.status === "succeeded").length

  const clearAgentTimeout = useCallback(() => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current)
      timeoutRef.current = null
    }
  }, [])

  const startAgentTimeout = useCallback(() => {
    clearAgentTimeout()
    timeoutRef.current = setTimeout(() => {
      setError("Agent 运行时间较长，可能是模型超时或网络波动。你可以继续等待、重新连接 SSE，或使用示例结果保证 Demo 稳定。")
    }, AGENT_TIMEOUT_MS)
  }, [clearAgentTimeout])

  useEffect(() => {
    if (initialJobId) return
    const timer = window.setTimeout(() => {
      const rawPreset = window.sessionStorage.getItem(PLANNING_PRESET_DRAFT_KEY)
      if (!rawPreset) return
      try {
        const draft = JSON.parse(rawPreset) as Record<string, unknown>
        const intent = typeof draft.intent === "string" ? draft.intent : ""
        if (intent !== "send_to_analysis") {
          window.sessionStorage.removeItem(PLANNING_PRESET_DRAFT_KEY)
          return
        }
        const preset = typeof draft.preset === "string" ? draft.preset : ""
        window.sessionStorage.removeItem(PLANNING_PRESET_DRAFT_KEY)
        if (!preset.trim()) return
        setPreference(`来自拍摄规划的后期预设草稿：\n${preset}`)
        setDemoNotice("已带入规划页生成的后期预设草稿。上传照片后，PostAgent 会按该方向给出后期建议。")
      } catch {
        window.sessionStorage.removeItem(PLANNING_PRESET_DRAFT_KEY)
        // 预设草稿只是前端辅助，不影响分析页主链路。
      }
    }, 0)
    return () => window.clearTimeout(timer)
  }, [initialJobId])

  const loadResults = useCallback(async (targetJobId: string) => {
    const response = await getJobResults(targetJobId)
    if (activeJobRef.current !== targetJobId) return
    clearAgentTimeout()
    setJobStatus(response.status)
    setResults(response.results)
    setAgentProgress((current) => {
      const next = { ...current }
      response.results.forEach((result) => {
        if (result.agent === "post" || result.agent === "coach") {
          next[result.agent] = makeAgentProgress(
            result.agent,
            result.status === "succeeded" ? 100 : current[result.agent].progress,
            result.status === "succeeded" ? "completed" : "failed",
            result.status === "succeeded" ? `${agentNames[result.agent]} 已完成` : result.agentError || "Agent 失败"
          )
        }
      })
      return next
    })
  }, [clearAgentTimeout])

  const appendEvent = useCallback((event: AgentEventMessage) => {
    setEvents((current) => [
      ...current.slice(-79),
      {
        time: formatTime(event.createdAt),
        agent: event.agent ?? "job",
        message: event.message || event.type,
      },
    ])
  }, [])

  const applyEvent = useCallback(
    (event: AgentEventMessage) => {
      appendEvent(event)

      const agent = event.agent === "post" || event.agent === "coach" ? event.agent : null
      if (agent && event.type === "agent.started") {
        setAgentProgress((current) => ({
          ...current,
          [agent]: makeAgentProgress(agent, 8, "running", event.message || "Agent 已开始"),
        }))
      }

      if (agent && event.type === "agent.progress") {
        setAgentProgress((current) => {
          const previous = current[agent]
          const progress = normalizeProgress(event.payload.progress, previous.progress)
          return {
            ...current,
            [agent]: makeAgentProgress(agent, progress, "running", event.message || previous.currentStep),
          }
        })
      }

      if (agent && event.type === "agent.result") {
        setAgentProgress((current) => ({
          ...current,
          [agent]: makeAgentProgress(agent, 100, "completed", event.message || "Agent 已完成"),
        }))
        void loadResults(event.jobId).catch((resultError) => {
          setError(resultError instanceof Error ? resultError.message : "获取结果失败")
        })
      }

      if (agent && event.type === "agent.error") {
        setAgentProgress((current) => ({
          ...current,
          [agent]: makeAgentProgress(agent, current[agent].progress, "failed", event.message || "Agent 失败"),
        }))
      }

      if (
        event.type === "job.started" ||
        event.type === "job.completed" ||
        event.type === "job.partial_completed" ||
        event.type === "job.failed"
      ) {
        const nextStatus =
          event.type === "job.completed"
            ? "completed"
            : event.type === "job.partial_completed"
              ? "partial_completed"
              : event.type === "job.failed"
                ? "failed"
                : "running"
        setJobStatus(nextStatus)
        if (nextStatus === "completed" || nextStatus === "partial_completed" || nextStatus === "failed") {
          clearAgentTimeout()
          void loadResults(event.jobId).catch((resultError) => {
            setError(resultError instanceof Error ? resultError.message : "获取结果失败")
          })
        }
      }
    },
    [appendEvent, clearAgentTimeout, loadResults]
  )

  const subscribeToJob = useCallback(
    (targetJobId: string) => {
      unsubscribeRef.current?.()
      unsubscribeRef.current = subscribeJobEvents(targetJobId, {
        onOpen: () => {
          setError(null)
        },
        onEvent: applyEvent,
        onError: (sseError) => {
          setError(`${sseError.message || "SSE 连接异常"}。后台任务不会因此中断，你可以重新连接或稍后刷新结果。`)
        },
      })
      startAgentTimeout()
    },
    [applyEvent, startAgentTimeout]
  )

  useEffect(() => {
    if (!initialJobId) return
    const targetJobId = initialJobId
    activeJobRef.current = targetJobId
    let disposed = false

    async function restoreJob() {
      try {
        const restoredJob = await getJob(targetJobId)
        if (disposed) return
        setJobId(targetJobId)
        setMedia(null)
        setResults([])
        setPreference(restoredJob.userGoal || "")
        setJobStatus(restoredJob.status)
        const restoreMedia = async () => {
          const mediaId = restoredJob.mediaIds[0]
          if (!mediaId) return
          try {
            const restoredMedia = await getMedia(mediaId)
            if (!disposed) setMedia(restoredMedia)
          } catch {
            if (!disposed) setError("历史结果已保留，但原照片暂时无法恢复，请检查素材是否仍存在。")
          }
        }
        if (restoredJob.status === "completed" || restoredJob.status === "partial_completed" || restoredJob.status === "failed") {
          await Promise.all([loadResults(targetJobId), restoreMedia()])
        } else {
          subscribeToJob(targetJobId)
          await restoreMedia()
        }
      } catch (restoreError) {
        if (!disposed) {
          setError(restoreError instanceof Error ? restoreError.message : "恢复任务失败")
          setJobStatus("failed")
        }
      }
    }

    void restoreJob()

    return () => {
      disposed = true
    }
  }, [initialJobId, loadResults, subscribeToJob])

  useEffect(() => {
    return () => {
      unsubscribeRef.current?.()
      clearAgentTimeout()
    }
  }, [clearAgentTimeout])

  const handleFileSelect = async (file: File) => {
    try {
      setError(null)
      setDemoNotice(null)
      setJobId(null)
      activeJobRef.current = null
      setResults([])
      setEvents([])
      setAgentProgress(initialAgentState)
      setJobStatus("uploading")
      const uploadedMedia = await uploadMedia(file)
      setMedia(uploadedMedia)
      setJobStatus("idle")
    } catch (uploadError) {
      setError(uploadError instanceof Error ? uploadError.message : "上传失败")
      setDemoNotice("上传失败时可使用示例照片继续演示完整分析链路。")
      setJobStatus("idle")
    }
  }

  const handleStartAnalysis = async () => {
    if (!media) {
      setError("请先上传照片")
      return
    }

    try {
      setError(null)
      setDemoNotice(null)
      setResults([])
      setEvents([])
      setAgentProgress({
        post: makeAgentProgress("post", 0, "pending", "等待 Post Agent 调度"),
        coach: makeAgentProgress("coach", 0, "pending", "等待 Coach Agent 调度"),
      })
      setJobStatus("creating")

      const createdJob = await createJob({
        type: "photo_review",
        agents: ["post", "coach"],
        media_ids: [media.mediaId],
        user_goal: preference || "帮我看看这张照片怎么后期，以及怎么拍得更好",
      })

      setJobId(createdJob.jobId)
      activeJobRef.current = createdJob.jobId
      setJobStatus(createdJob.status)
      window.history.replaceState(null, "", `/analysis/${createdJob.jobId}`)
      subscribeToJob(createdJob.jobId)
    } catch (createError) {
      setError(createError instanceof Error ? createError.message : "创建分析任务失败")
      setDemoNotice("创建任务失败时，仍可切换到示例结果完成 Demo 录制。")
      setJobStatus("idle")
    }
  }

  const applyDemoResults = (response: JobResultsResponse, notice: string) => {
    clearAgentTimeout()
    unsubscribeRef.current?.()
    setMedia((current) => current ?? demoMedia)
    setJobId(response.jobId)
    setJobStatus(response.status)
    setResults(response.results)
    setEvents(mockEventsToStream(response.jobId))
    setError(null)
    setDemoNotice(notice)
    setAgentProgress({
      post: makeAgentProgress(
        "post",
        response.results.find((result) => result.agent === "post")?.status === "failed" ? 72 : 100,
        response.results.find((result) => result.agent === "post")?.status === "failed" ? "failed" : "completed",
        response.results.find((result) => result.agent === "post")?.status === "failed"
          ? "Post Agent 失败，成功结果已保留"
          : "Post Agent 已完成"
      ),
      coach: makeAgentProgress(
        "coach",
        response.results.find((result) => result.agent === "coach")?.status === "failed" ? 72 : 100,
        response.results.find((result) => result.agent === "coach")?.status === "failed" ? "failed" : "completed",
        response.results.find((result) => result.agent === "coach")?.status === "failed"
          ? "Coach Agent 失败，成功结果已保留"
          : "Coach Agent 已完成"
      ),
    })
    window.history.replaceState(null, "", `/analysis/${response.jobId}`)
  }

  const handleUseDemoPhoto = () => {
    clearAgentTimeout()
    unsubscribeRef.current?.()
    setMedia(demoMedia)
    setJobId(null)
    setJobStatus("idle")
    setResults([])
    setEvents([])
    setError(null)
    setPreference("偏好风光片的色彩增强，保留天空高光层次")
    setAgentProgress(initialAgentState)
    setDemoNotice("已载入示例照片。你可以继续创建真实任务，也可以直接使用示例结果。")
    router.replace("/analysis")
  }

  const handleUseDemoResults = () => {
    applyDemoResults(mockJobResultsResponse, "已切换到示例结果。用于断网、模型波动或录屏时稳定演示。")
  }

  const handleUsePartialDemoResults = () => {
    applyDemoResults(mockPartialJobResultsResponse, "已切换到 partial_completed 示例：Coach 成功，Post 失败，可演示失败重试和成功结果保留。")
  }

  const handleReconnectSSE = () => {
    if (!jobId || isTerminalStatus(jobStatus)) return
    setError(null)
    setDemoNotice("正在重新连接 SSE。后台任务不会因浏览器断线而中断。")
    subscribeToJob(jobId)
  }

  const handleRetryFailedAgents = async () => {
    if (!jobId || failedAgents.length === 0) return
    try {
      setError(null)
      setDemoNotice(`正在重试失败 Agent：${failedAgents.join(" + ")}`)
      await Promise.all(failedAgents.map((agent) => retryAgent(jobId, agent)))
      setAgentProgress((current) => {
        const next = { ...current }
        failedAgents.forEach((agent) => {
          next[agent] = makeAgentProgress(agent, 0, "pending", "等待重试调度")
        })
        return next
      })
      setJobStatus("running")
      subscribeToJob(jobId)
    } catch (retryError) {
      setError(retryError instanceof Error ? retryError.message : "重试失败 Agent 失败")
    }
  }

  const handleResetUpload = () => {
    activeJobRef.current = null
    unsubscribeRef.current?.()
    clearAgentTimeout()
    setMedia(null)
    setJobId(null)
    setResults([])
    setEvents([])
    setError(null)
    setPreference("")
    setAgentProgress(initialAgentState)
    setJobStatus("idle")
    setDemoNotice(null)
    router.replace("/analysis")
  }

  const handleRetry = () => {
    if (failedAgents.length > 0) {
      void handleRetryFailedAgents()
      return
    }
    if (media) {
      void handleStartAnalysis()
    }
  }

  const handleExportReport = () => {
    if (!results.length) {
      setError("暂无可导出的分析结果，请先完成分析或使用示例结果。")
      return
    }
    const report = buildAnalysisReport({
      jobId,
      media,
      preference,
      postResult: postPanelResult,
      coachResult: coachPanelResult,
      events,
    })
    const baseName = sanitizeFileName(media?.fileName || jobId || "photoai_analysis")
    downloadTextFile(`${baseName}_PhotoAI分析报告.md`, report)
    setError(null)
    setDemoNotice("分析报告已导出为 Markdown 文件，可用于提交或二次整理。")
  }

  const handleSaveResult = () => {
    if (!jobId || !results.length) {
      setError("暂无可保存的结果。任务完成后，结果会自动写入后端 ResultStore。")
      return
    }
    const savedRecord = {
      jobId,
      mediaId: media?.mediaId ?? null,
      fileName: media?.fileName ?? null,
      status: jobStatus,
      savedAt: new Date().toISOString(),
      agents: results.map((result) => ({
        agent: result.agent,
        status: result.status,
        summary: result.summary,
      })),
    }
    try {
      const raw = window.localStorage.getItem(SAVED_ANALYSIS_CACHE_KEY)
      const cached = raw ? (JSON.parse(raw) as unknown) : []
      const records = Array.isArray(cached) ? cached : []
      const nextRecords = [
        savedRecord,
        ...records.filter((item) => {
          return !item || typeof item !== "object" || (item as Record<string, unknown>).jobId !== jobId
        }),
      ].slice(0, 30)
      window.localStorage.setItem(SAVED_ANALYSIS_CACHE_KEY, JSON.stringify(nextRecords))
    } catch {
      // 后端 ResultStore 仍是主存储，本地收藏失败不影响真实结果。
    }
    setError(null)
    setDemoNotice("结果已保存：后端 Job/Result 可在历史页恢复，本地也已记录最近保存项。")
  }

  const handleCreatePlanningDraft = () => {
    if (!jobId && !media) {
      setError("请先上传照片或打开一个分析任务，再生成拍摄规划上下文。")
      return
    }
    const draft = {
      sourceJobId: jobId,
      sourceMediaId: media?.mediaId ?? null,
      sourceFileName: media?.fileName ?? null,
      userGoal: preference,
      postSummary: resultByAgent.post?.summary ?? postPanelResult.summary,
      coachSummary: resultByAgent.coach?.summary ?? "",
      styleDirection: postPanelResult.suggestions.find((section) => section.category === "后期风格方向")?.items ?? [],
      createdAt: new Date().toISOString(),
    }
    window.sessionStorage.setItem(PLANNING_DRAFT_CACHE_KEY, JSON.stringify(draft))
    setError(null)
    setDemoNotice("已整理当前照片的风格和学习反馈上下文，正在前往拍摄规划页。")
    router.push("/planning")
  }

  const handleSendToAssets = () => {
    if (!media) {
      setError("当前任务缺少可写入素材库的媒体详情。请从本次上传任务进入，或重新上传照片后再发送。")
      return
    }
    try {
      const asset = saveAnalysisMediaToAssets(media, resultByAgent.post, resultByAgent.coach)
      setError(null)
      setDemoNotice(`已送入素材库：${asset.file_name}。`)
      router.push("/assets")
    } catch (assetError) {
      setError(assetError instanceof Error ? assetError.message : "送去素材库失败，请稍后重试。")
    }
  }

  return (
    <div className="p-6 max-w-[1600px] mx-auto">
      <div className="flex items-center gap-2 text-sm text-slate-500 mb-6">
        <Link href="/" className="hover:text-slate-900 flex items-center gap-1">
          <ChevronLeft className="w-4 h-4" />
          返回工作台
        </Link>
        <span>/</span>
        <span>分析任务</span>
        <span className="text-slate-400">{jobId || "新任务"}</span>
        <Badge variant="outline" className={statusBadgeClass(jobStatus)}>
          {statusLabel(jobStatus)}
        </Badge>
      </div>

      {error && (
        <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm font-medium text-red-700">
          {error}
        </div>
      )}

      {demoNotice && (
        <div className="mb-4 rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm font-medium text-blue-700">
          {demoNotice}
        </div>
      )}

      <div className="mb-4 flex flex-wrap items-center gap-2">
        <Button variant="outline" size="sm" onClick={handleUseDemoPhoto}>
          使用示例照片
        </Button>
        <Button variant="outline" size="sm" onClick={handleUseDemoResults}>
          使用示例结果
        </Button>
        <Button variant="outline" size="sm" onClick={handleUsePartialDemoResults}>
          partial_completed 示例
        </Button>
        {jobId && !isTerminalStatus(jobStatus) && (
          <Button variant="outline" size="sm" onClick={handleReconnectSSE}>
            重新连接 SSE
          </Button>
        )}
        {failedAgents.length > 0 && (
          <Button variant="outline" size="sm" className="border-red-200 text-red-600" onClick={handleRetryFailedAgents}>
            重试失败 Agent
          </Button>
        )}
        {successfulResultCount > 0 && jobStatus === "partial_completed" && (
          <span className="text-sm text-slate-500">
            已保留 {successfulResultCount} 个成功结果，可直接查看。
          </span>
        )}
      </div>

      {!hasMediaOrJob ? (
        <UploadPlaceholder
          isUploading={jobStatus === "uploading"}
          onFileSelect={handleFileSelect}
        />
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-stretch lg:h-[calc(100vh-190px)] lg:min-h-[680px]">
          <div className="lg:col-span-3 min-h-0 flex flex-col gap-4">
            <div className="flex-1 min-h-0">
              <UploadPreviewPanel
                images={previewUrl ? [previewUrl] : []}
                fileName={media?.fileName}
                exif={toExif(media)}
                preference={preference}
                onPreferenceChange={setPreference}
                onRetake={handleResetUpload}
                onCancel={handleResetUpload}
              />
            </div>
            {media && !jobId && (
              <Button
                className="h-11 w-full shrink-0 bg-blue-600 text-white hover:bg-blue-700"
                disabled={isBusy}
                onClick={handleStartAnalysis}
              >
                {jobStatus === "creating" ? "正在创建任务..." : "开始智能分析"}
              </Button>
            )}
          </div>

          <div className="lg:col-span-4 flex min-h-0">
            <Card className="flex-1 flex flex-col min-h-0 overflow-hidden">
              <CardHeader className="pb-3 flex flex-row items-center justify-between shrink-0">
                <CardTitle className="text-lg font-bold flex items-center gap-2">
                  实时分析控制台
                  <AlertCircle className="w-4 h-4 text-slate-400" />
                </CardTitle>
                <Button variant="ghost" size="sm" className="text-slate-500">
                  收起
                </Button>
              </CardHeader>
              <CardContent className="space-y-4 flex-1 flex flex-col min-h-0 overflow-hidden">
                <AgentProgressCard agent={agentProgress.post} variant="post" />
                <AgentProgressCard agent={agentProgress.coach} variant="coach" />
                <div className="flex-1 min-h-0">
                  <LiveEventStream events={events} onClear={() => setEvents([])} />
                </div>
              </CardContent>
            </Card>
          </div>

          <div className="lg:col-span-5 flex min-h-0">
            <AnalysisResultPanel
              jobId={jobId}
              mediaId={media?.mediaId}
              postResult={postPanelResult}
              coachResult={coachPanelResult}
              onExport={handleExportReport}
              onSave={handleSaveResult}
              onRetry={handleRetry}
              onPlan={handleCreatePlanningDraft}
              onSendToAssets={handleSendToAssets}
            />
          </div>
        </div>
      )}
    </div>
  )
}
