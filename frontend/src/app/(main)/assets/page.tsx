"use client"

import { useEffect, useMemo, useRef, useState } from "react"
import { useRouter } from "next/navigation"
import {
  AssetUploadZone,
  AssetToolbar,
  AssetSidebar,
  AssetGrid,
  AssetDetailPanel,
  AssetBatchActionBar,
} from "@/components/assets"
import { failedFileToAssetItem, mediaToAssetItem } from "@/lib/assets"
import { isMockMode, scoreAssetsWithAssetAgent, sendAssetsToCoach, sendAssetsToPost, uploadManyMedia } from "@/lib/api"
import { demoAssetItems } from "@/lib/mocks"
import type { AssetFilter, AssetGrade, AssetItem, UploadError } from "@/types/assets"
import { DEMO_MODE } from "@/lib/demo/config"
import { seedDemoAssets } from "@/lib/demo/api"

const ENABLE_DEMO_FALLBACK = process.env.NEXT_PUBLIC_ENABLE_DEMO_FALLBACK !== "false"
const ASSET_LIBRARY_CACHE_KEY = DEMO_MODE ? "photoai.demo.assetLibrary.v2" : "photoai.assetLibrary.v1"
const ASSET_PROJECT_TITLE_CACHE_KEY = DEMO_MODE ? "photoai.demo.assetProjectTitle.v2" : "photoai.assetProjectTitle.v1"
const ASSET_FOLDER_NAMES_CACHE_KEY = DEMO_MODE ? "photoai.demo.assetFolderNames.v2" : "photoai.assetFolderNames.v1"
const ASSET_CUSTOM_FOLDERS_CACHE_KEY = DEMO_MODE ? "photoai.demo.assetCustomFolders.v2" : "photoai.assetCustomFolders.v1"
const ASSET_FOLDER_ASSIGNMENTS_CACHE_KEY = DEMO_MODE ? "photoai.demo.assetFolderAssignments.v2" : "photoai.assetFolderAssignments.v1"

type CustomAssetFolder = {
  id: string
  name: string
  created_at: string
}

type AssetFolderNode = {
  id: string
  name: string
  count: number
  isExpanded?: boolean
  canRename?: boolean
  canDelete?: boolean
  children?: AssetFolderNode[]
}

function statsFromAssets(assets: AssetItem[]) {
  return assets.reduce(
    (acc, asset) => {
      acc.total += 1
      if (asset.grade === "A") acc.gradeA += 1
      if (asset.grade === "B") acc.gradeB += 1
      if (asset.grade === "C") acc.gradeC += 1
      if (asset.grade === "reject") acc.rejected += 1
      if (asset.grade === "duplicate") acc.duplicate += 1
      return acc
    },
    { total: 0, gradeA: 0, gradeB: 0, gradeC: 0, rejected: 0, duplicate: 0 }
  )
}

function matchesKeyword(asset: AssetItem, keyword: string) {
  if (!keyword.trim()) return true
  const lower = keyword.trim().toLowerCase()
  return [
    asset.file_name,
    asset.media_id,
    asset.metadata?.location,
    ...asset.tags,
    ...asset.ai_reasons,
    ...(asset.issues || []),
  ]
    .filter(Boolean)
    .some((value) => String(value).toLowerCase().includes(lower))
}

function sortAssets(assets: AssetItem[], sortBy: AssetFilter["sort_by"]) {
  return [...assets].sort((a, b) => {
    if (sortBy === "score") return (b.score || 0) - (a.score || 0)
    if (sortBy === "file_name") return a.file_name.localeCompare(b.file_name)
    return new Date(b.created_at || 0).getTime() - new Date(a.created_at || 0).getTime()
  })
}

function groupAssets(assets: AssetItem[]) {
  const duplicates = assets.filter((asset) => asset.grade === "duplicate" || asset.duplicate_group_id)
  const regular = assets.filter((asset) => !duplicates.includes(asset))
  return [
    ...(duplicates.length
      ? [
          {
            id: "duplicates",
            name: "相似 / 重复组",
            assets: duplicates,
            isSimilarGroup: true,
          },
        ]
      : []),
    {
      id: "all",
      name: "素材网格",
      assets: regular,
    },
  ].filter((group) => group.assets.length > 0)
}

function parseAssetDate(asset: AssetItem) {
  const raw = asset.metadata?.captured_at || asset.created_at
  if (!raw) return null
  const date = new Date(raw)
  return Number.isNaN(date.getTime()) ? null : date
}

function assetMonthKey(asset: AssetItem) {
  const date = parseAssetDate(asset)
  if (!date) return "unknown"
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`
}

function assetMonthLabel(key: string) {
  return key === "unknown" ? "未识别日期" : `${key} 上传素材`
}

function dominantValue(values: Array<string | undefined | null>) {
  const counts = new Map<string, number>()
  values
    .map((value) => value?.trim())
    .filter(Boolean)
    .forEach((value) => counts.set(value as string, (counts.get(value as string) || 0) + 1))
  return [...counts.entries()].sort((a, b) => b[1] - a[1])[0]?.[0]
}

function buildProjectTitle(assets: AssetItem[], isDemoFallback: boolean) {
  if (isDemoFallback) return "示例素材库"
  if (!assets.length) return "素材库"
  const latest = [...assets].sort((a, b) => {
    return (parseAssetDate(b)?.getTime() || 0) - (parseAssetDate(a)?.getTime() || 0)
  })[0]
  const month = assetMonthKey(latest)
  const location = dominantValue(assets.map((asset) => asset.metadata?.location))
  return location ? `${month} ${location}素材` : `${assetMonthLabel(month)}`
}

function hasUsableExif(asset: AssetItem) {
  const metadata = asset.metadata
  return Boolean(metadata?.iso || metadata?.aperture || metadata?.shutter || metadata?.focal_length || metadata?.camera)
}

function buildProjectDescription(assets: AssetItem[], isDemoFallback: boolean) {
  if (isDemoFallback) return "当前使用示例素材数据；上传真实照片后会替换为你的素材库。"
  if (!assets.length) return "上传照片后，AssetAgent 会生成评分、分档和重复组。"
  return "当前分档由 AssetAgent 图像理解评分生成；素材列表已在本地缓存，后续可升级为后端项目库。"
}

function folderName(id: string, fallback: string, overrides: Record<string, string>) {
  return overrides[id]?.trim() || fallback
}

function categoryChildrenForAssets(
  folderId: string,
  assets: AssetItem[],
  collapsedFolderIds: Set<string>,
  folderNameOverrides: Record<string, string>
) {
  const childSpecs = [
    { suffix: "landscape", name: "横图", match: (asset: AssetItem) => asset.tags.includes("横图") },
    { suffix: "portrait", name: "竖图", match: (asset: AssetItem) => asset.tags.includes("竖图") },
    { suffix: "warm", name: "暖色", match: (asset: AssetItem) => asset.tags.includes("暖色") },
    { suffix: "cool", name: "冷色", match: (asset: AssetItem) => asset.tags.includes("冷色") },
    {
      suffix: "duplicate",
      name: "重复",
      match: (asset: AssetItem) => asset.grade === "duplicate" || Boolean(asset.duplicate_group_id),
    },
  ]

  return childSpecs
    .map((spec) => {
      const id = `${folderId}:${spec.suffix}`
      return {
        id,
        name: folderName(id, spec.name, folderNameOverrides),
        count: assets.filter(spec.match).length,
        isExpanded: !collapsedFolderIds.has(id),
        canRename: false,
        canDelete: false,
      }
    })
    .filter((folder) => folder.count > 0)
}

function buildAssetFolders(
  assets: AssetItem[],
  collapsedFolderIds: Set<string>,
  folderNameOverrides: Record<string, string>,
  customFolders: CustomAssetFolder[],
  folderAssignments: Record<string, string[]>
) {
  const unfiledAssets = assets.filter((asset) => !(folderAssignments[asset.asset_id] || []).length)
  const customFolderNodes = [
    {
      id: "custom:unfiled",
      name: folderName(
        "custom:unfiled",
        "未归档素材",
        folderNameOverrides
      ),
      count: unfiledAssets.length,
      canRename: false,
      canDelete: false,
      children: categoryChildrenForAssets("custom:unfiled", unfiledAssets, collapsedFolderIds, folderNameOverrides),
    },
    ...customFolders.map((folder) => {
      const folderAssets = assets.filter((asset) => (folderAssignments[asset.asset_id] || []).includes(folder.id))
      return {
        id: folder.id,
        name: folderName(folder.id, folder.name, folderNameOverrides),
        count: folderAssets.length,
        isExpanded: !collapsedFolderIds.has(folder.id),
        canRename: true,
        canDelete: true,
        children: categoryChildrenForAssets(folder.id, folderAssets, collapsedFolderIds, folderNameOverrides),
      }
    }),
  ]

  return [
    {
      id: "all",
      name: folderName("all", "全部素材", folderNameOverrides),
      count: assets.length,
      isExpanded: !collapsedFolderIds.has("all"),
      canRename: false,
      canDelete: false,
      children: customFolderNodes,
    },
  ]
}

function findFolderById(folders: AssetFolderNode[], folderId: string | null): AssetFolderNode | null {
  if (!folderId) return null
  for (const folder of folders) {
    if (folder.id === folderId) return folder
    const child = findFolderById(folder.children || [], folderId)
    if (child) return child
  }
  return null
}

function displayTitleForSelection(
  folders: AssetFolderNode[],
  selectedFolder: string,
  fallbackTitle: string
) {
  if (selectedFolder === "all") return fallbackTitle
  const selected = findFolderById(folders, selectedFolder)
  return selected ? selected.name : fallbackTitle
}

function matchesFolder(asset: AssetItem, folderId: string | null, folderAssignments: Record<string, string[]>) {
  if (!folderId || folderId === "all") return true
  if (folderId === "custom:unfiled") return !(folderAssignments[asset.asset_id] || []).length
  if (folderId.startsWith("custom:")) {
    const parts = folderId.split(":")
    const baseFolderId = parts.length >= 3 ? `${parts[0]}:${parts[1]}` : folderId
    const child = parts[2]
    const inBaseFolder =
      baseFolderId === "custom:unfiled"
        ? !(folderAssignments[asset.asset_id] || []).length
        : (folderAssignments[asset.asset_id] || []).includes(baseFolderId)
    if (!inBaseFolder) return false
    if (!child) return true
    if (child === "landscape") return asset.tags.includes("横图")
    if (child === "portrait") return asset.tags.includes("竖图")
    if (child === "warm") return asset.tags.includes("暖色")
    if (child === "cool") return asset.tags.includes("冷色")
    if (child === "duplicate") return asset.grade === "duplicate" || Boolean(asset.duplicate_group_id)
  }
  return true
}

function matchesGridFilter(asset: AssetItem, gridFilter: string) {
  if (gridFilter === "all") return true
  if (gridFilter === "landscape") return asset.tags.includes("横图")
  if (gridFilter === "portrait") return asset.tags.includes("竖图")
  if (gridFilter === "warm") return asset.tags.includes("暖色")
  if (gridFilter === "cool") return asset.tags.includes("冷色")
  if (gridFilter === "has_exif") return hasUsableExif(asset)
  if (gridFilter === "missing_exif") return !hasUsableExif(asset)
  if (gridFilter === "duplicate") return asset.grade === "duplicate" || Boolean(asset.duplicate_group_id)
  return true
}

function matchesDateFilter(asset: AssetItem, dateFilter: string) {
  return dateFilter === "all" || assetMonthKey(asset) === dateFilter
}

function buildDateOptions(assets: AssetItem[]) {
  const counts = new Map<string, number>()
  assets.forEach((asset) => {
    const key = assetMonthKey(asset)
    counts.set(key, (counts.get(key) || 0) + 1)
  })

  return [
    { key: "all", label: "全部日期", count: assets.length },
    ...[...counts.entries()]
      .sort((a, b) => b[0].localeCompare(a[0]))
      .map(([key, count]) => ({ key, label: assetMonthLabel(key), count })),
  ]
}

function loadCachedAssets() {
  if (typeof window === "undefined") return []
  try {
    const raw = window.localStorage.getItem(ASSET_LIBRARY_CACHE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? (parsed as AssetItem[]) : []
  } catch {
    return []
  }
}

function loadCachedProjectTitle() {
  if (typeof window === "undefined") return ""
  try {
    return window.localStorage.getItem(ASSET_PROJECT_TITLE_CACHE_KEY) || ""
  } catch {
    return ""
  }
}

function loadCachedFolderNames() {
  if (typeof window === "undefined") return {}
  try {
    const raw = window.localStorage.getItem(ASSET_FOLDER_NAMES_CACHE_KEY)
    if (!raw) return {}
    const parsed = JSON.parse(raw)
    return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? (parsed as Record<string, string>) : {}
  } catch {
    return {}
  }
}

function loadCachedCustomFolders() {
  if (typeof window === "undefined") return []
  try {
    const raw = window.localStorage.getItem(ASSET_CUSTOM_FOLDERS_CACHE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? (parsed as CustomAssetFolder[]) : []
  } catch {
    return []
  }
}

function loadCachedFolderAssignments() {
  if (typeof window === "undefined") return {}
  try {
    const raw = window.localStorage.getItem(ASSET_FOLDER_ASSIGNMENTS_CACHE_KEY)
    if (!raw) return {}
    const parsed = JSON.parse(raw)
    return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? (parsed as Record<string, string[]>) : {}
  } catch {
    return {}
  }
}

function saveCachedAssets(assets: AssetItem[]) {
  if (typeof window === "undefined") return
  try {
    const stableAssets = assets.filter((asset) => (DEMO_MODE || !asset.is_demo) && asset.upload_status !== "uploading")
    window.localStorage.setItem(ASSET_LIBRARY_CACHE_KEY, JSON.stringify(stableAssets))
  } catch {
    // Local cache is best-effort only. The UI should keep working even if storage is full.
  }
}

function saveCachedProjectTitle(title: string) {
  if (typeof window === "undefined") return
  try {
    if (title.trim()) {
      window.localStorage.setItem(ASSET_PROJECT_TITLE_CACHE_KEY, title.trim())
    } else {
      window.localStorage.removeItem(ASSET_PROJECT_TITLE_CACHE_KEY)
    }
  } catch {
    // Local cache is best-effort only. The UI should keep working even if storage is full.
  }
}

function saveCachedFolderNames(folderNames: Record<string, string>) {
  if (typeof window === "undefined") return
  try {
    window.localStorage.setItem(ASSET_FOLDER_NAMES_CACHE_KEY, JSON.stringify(folderNames))
  } catch {
    // Local cache is best-effort only. The UI should keep working even if storage is full.
  }
}

function saveCachedCustomFolders(folders: CustomAssetFolder[]) {
  if (typeof window === "undefined") return
  try {
    window.localStorage.setItem(ASSET_CUSTOM_FOLDERS_CACHE_KEY, JSON.stringify(folders))
  } catch {
    // Local cache is best-effort only. The UI should keep working even if storage is full.
  }
}

function saveCachedFolderAssignments(assignments: Record<string, string[]>) {
  if (typeof window === "undefined") return
  try {
    window.localStorage.setItem(ASSET_FOLDER_ASSIGNMENTS_CACHE_KEY, JSON.stringify(assignments))
  } catch {
    // Local cache is best-effort only. The UI should keep working even if storage is full.
  }
}

function isSupportedProjectFile(file: File) {
  if (file.type.startsWith("image/")) return true
  return /\.(jpe?g|png|heic|heif|dng|raw|arw|cr2|cr3|nef|raf)$/i.test(file.name)
}

function createCustomFolderId() {
  return `custom:${Date.now()}`
}

function assignableFolderId(folderId: string | null) {
  if (!folderId?.startsWith("custom:")) return null
  if (folderId === "custom:unfiled") return null
  const parts = folderId.split(":")
  return parts.length >= 2 ? `${parts[0]}:${parts[1]}` : folderId
}

function duplicateKey(asset: AssetItem) {
  const width = asset.metadata?.width || ""
  const height = asset.metadata?.height || ""
  const size = asset.metadata?.file_size || ""
  const mime = asset.mime_type || ""
  if (!size) return ""
  return `${size}_${width}_${height}_${mime}`
}

function clearDuplicateState(asset: AssetItem): AssetItem {
  const tags = asset.tags.filter((tag) => !["相似素材", "疑似重复", "重复"].includes(tag))
  const issues = (asset.issues || []).filter((issue) => !["疑似重复", "duplicate"].includes(issue))
  const ai_reasons = asset.ai_reasons.filter((reason) => !/重复|相似素材/.test(reason))
  const score = asset.score
  const restoredGrade =
    asset.grade === "duplicate"
      ? typeof score === "number" && score >= 85
        ? "A"
        : typeof score === "number" && score >= 60
          ? "B"
          : "C"
      : asset.grade

  return {
    ...asset,
    grade: restoredGrade,
    tags,
    issues,
    ai_reasons,
    duplicate_group_id: null,
  }
}

function applyLightweightDuplicateRules(items: AssetItem[]) {
  const normalizedItems = items.map(clearDuplicateState)
  const groups = new Map<string, AssetItem[]>()
  normalizedItems.forEach((asset) => {
    if (asset.upload_status === "failed") return
    const key = duplicateKey(asset)
    if (!key) return
    const group = groups.get(key) || []
    group.push(asset)
    groups.set(key, group)
  })

  const duplicateIds = new Map<string, string>()
  groups.forEach((group, key) => {
    if (group.length < 2) return
    group.forEach((asset) => duplicateIds.set(asset.asset_id, `dup_${key}`))
  })

  return normalizedItems.map((asset) => {
    const duplicateGroupId = duplicateIds.get(asset.asset_id)
    if (!duplicateGroupId) return asset
    return {
      ...asset,
      grade: "duplicate" as const,
      duplicate_group_id: duplicateGroupId,
      score: Math.min(asset.score || 72, 87),
      tags: Array.from(new Set([...asset.tags.filter((tag) => tag !== "精选"), "相似素材", "疑似重复"])),
      ai_reasons: Array.from(
        new Set([
          ...asset.ai_reasons,
          "与本次上传中的其他素材具有相同文件大小和基础图像信息，标记为轻量重复候选。",
        ])
      ),
      issues: Array.from(new Set([...(asset.issues || []), "疑似重复"])),
    }
  })
}

export default function AssetsPage() {
  const router = useRouter()
  const projectInputRef = useRef<HTMLInputElement | null>(null)
  const metadataRefreshMediaIdsRef = useRef<Set<string>>(new Set())
  const [assets, setAssets] = useState<AssetItem[]>([])
  const [selectedAssetIds, setSelectedAssetIds] = useState<string[]>([])
  const [activeAssetId, setActiveAssetId] = useState<string | null>(null)
  const [selectedFolder, setSelectedFolder] = useState<string>("all")
  const [customProjectTitle, setCustomProjectTitle] = useState<string>("")
  const [folderNameOverrides, setFolderNameOverrides] = useState<Record<string, string>>({})
  const [customFolders, setCustomFolders] = useState<CustomAssetFolder[]>([])
  const [folderAssignments, setFolderAssignments] = useState<Record<string, string[]>>({})
  const [collapsedFolderIds, setCollapsedFolderIds] = useState<Set<string>>(() => new Set())
  const [gridFilter, setGridFilter] = useState("all")
  const [dateFilter, setDateFilter] = useState("all")
  const [viewMode, setViewMode] = useState<"grid" | "list">("grid")
  const [filter, setFilter] = useState<AssetFilter>({
    keyword: "",
    grade: "all",
    sort_by: "created_at",
  })
  const [isUploading, setIsUploading] = useState(false)
  const [uploadErrors, setUploadErrors] = useState<UploadError[]>([])
  const [isHandoffSubmitting, setIsHandoffSubmitting] = useState(false)
  const [handoffError, setHandoffError] = useState<string | null>(null)
  const [handoffMessage, setHandoffMessage] = useState<string | null>(null)
  const [lastJobId, setLastJobId] = useState<string | null>(null)
  const [isDemoFallback, setIsDemoFallback] = useState(false)
  const [isCacheLoaded, setIsCacheLoaded] = useState(false)

  const filteredAssets = useMemo(() => {
    const next = assets.filter((asset) => {
      const gradeMatches = filter.grade === "all" || asset.grade === filter.grade
      return (
        gradeMatches &&
        matchesFolder(asset, selectedFolder, folderAssignments) &&
        matchesGridFilter(asset, gridFilter) &&
        matchesDateFilter(asset, dateFilter) &&
        matchesKeyword(asset, filter.keyword)
      )
    })
    return sortAssets(next, filter.sort_by)
  }, [assets, dateFilter, filter, folderAssignments, gridFilter, selectedFolder])

  const scopedAssets = useMemo(
    () =>
      assets.filter(
        (asset) =>
          matchesFolder(asset, selectedFolder, folderAssignments) &&
          matchesGridFilter(asset, gridFilter) &&
          matchesDateFilter(asset, dateFilter) &&
          matchesKeyword(asset, filter.keyword)
      ),
    [assets, dateFilter, filter.keyword, folderAssignments, gridFilter, selectedFolder]
  )
  const stats = useMemo(() => statsFromAssets(scopedAssets), [scopedAssets])
  const folders = useMemo(
    () => buildAssetFolders(assets, collapsedFolderIds, folderNameOverrides, customFolders, folderAssignments),
    [assets, collapsedFolderIds, customFolders, folderAssignments, folderNameOverrides]
  )
  const dateOptions = useMemo(() => buildDateOptions(assets), [assets])
  const baseProjectTitle = useMemo(
    () => customProjectTitle || buildProjectTitle(assets, isDemoFallback),
    [assets, customProjectTitle, isDemoFallback]
  )
  const projectTitle = useMemo(
    () => displayTitleForSelection(folders, selectedFolder, baseProjectTitle),
    [baseProjectTitle, folders, selectedFolder]
  )
  const projectDescription = useMemo(() => buildProjectDescription(assets, isDemoFallback), [assets, isDemoFallback])
  const groups = useMemo(() => groupAssets(filteredAssets), [filteredAssets])
  const activeAsset = useMemo(
    () => assets.find((asset) => asset.asset_id === activeAssetId) || filteredAssets[0] || null,
    [activeAssetId, assets, filteredAssets]
  )
  const activeIndex = activeAsset ? Math.max(1, filteredAssets.findIndex((asset) => asset.asset_id === activeAsset.asset_id) + 1) : 0
  const selectedAssets = assets.filter((asset) => selectedAssetIds.includes(asset.asset_id))
  const moveTargets = useMemo(
    () => [
      {
        id: "custom:unfiled",
        name: folderName(
          "custom:unfiled",
          "未归档素材",
          folderNameOverrides
        ),
        count: assets.filter((asset) => !(folderAssignments[asset.asset_id] || []).length).length,
      },
      ...customFolders.map((folder) => ({
        id: folder.id,
        name: folderName(folder.id, folder.name, folderNameOverrides),
        count: assets.filter((asset) => (folderAssignments[asset.asset_id] || []).includes(folder.id)).length,
      })),
    ],
    [assets, customFolders, folderAssignments, folderNameOverrides]
  )
  const uploadSummary =
    uploadErrors.length > 0
      ? `部分照片上传失败：成功 ${assets.filter((asset) => asset.upload_status === "uploaded").length} 张，失败 ${uploadErrors.length} 张`
      : null

  useEffect(() => {
    const timer = window.setTimeout(() => {
      if (DEMO_MODE) seedDemoAssets()
      const cachedAssets = loadCachedAssets()
      setAssets(cachedAssets)
      setActiveAssetId(cachedAssets[0]?.asset_id || null)
      setCustomProjectTitle(loadCachedProjectTitle())
      setFolderNameOverrides(loadCachedFolderNames())
      setCustomFolders(loadCachedCustomFolders())
      setFolderAssignments(loadCachedFolderAssignments())
      setIsCacheLoaded(true)
    }, 0)

    return () => window.clearTimeout(timer)
  }, [])

  useEffect(() => {
    if (!isCacheLoaded) return
    saveCachedAssets(assets)
  }, [assets, isCacheLoaded])

  useEffect(() => {
    if (!isCacheLoaded) return
    saveCachedProjectTitle(customProjectTitle)
  }, [customProjectTitle, isCacheLoaded])

  useEffect(() => {
    if (!isCacheLoaded) return
    saveCachedFolderNames(folderNameOverrides)
  }, [folderNameOverrides, isCacheLoaded])

  useEffect(() => {
    if (!isCacheLoaded) return
    saveCachedCustomFolders(customFolders)
  }, [customFolders, isCacheLoaded])

  useEffect(() => {
    if (!isCacheLoaded) return
    saveCachedFolderAssignments(folderAssignments)
  }, [folderAssignments, isCacheLoaded])

  useEffect(() => {
    if (!isCacheLoaded || isMockMode()) return
    const missingExifMediaIds = assets
      .filter((asset) => {
        if (!asset.media_id || asset.is_demo || asset.upload_status === "failed") return false
        if (metadataRefreshMediaIdsRef.current.has(asset.media_id)) return false
        const metadata = asset.metadata || {}
        return Boolean(metadata.camera) && (!metadata.iso || !metadata.aperture || !metadata.shutter || !metadata.focal_length)
      })
      .map((asset) => asset.media_id)

    if (!missingExifMediaIds.length) return
    missingExifMediaIds.forEach((mediaId) => metadataRefreshMediaIdsRef.current.add(mediaId))

    void scoreAssetsWithAssetAgent(missingExifMediaIds)
      .then((refreshedAssets) => {
        const refreshedByMediaId = new Map(refreshedAssets.map((asset) => [asset.media_id, asset]))
        setAssets((current) =>
          current.map((asset) => {
            const refreshed = refreshedByMediaId.get(asset.media_id)
            return refreshed
              ? {
                  ...refreshed,
                  preview_url: refreshed.preview_url || asset.preview_url,
                  created_at: asset.created_at || refreshed.created_at,
                }
              : asset
          })
        )
      })
      .catch(() => {
        missingExifMediaIds.forEach((mediaId) => metadataRefreshMediaIdsRef.current.delete(mediaId))
      })
  }, [assets, isCacheLoaded])

  const updateAsset = (assetId: string, nextAsset: AssetItem) => {
    setAssets((current) => applyLightweightDuplicateRules(current.map((asset) => (asset.asset_id === assetId ? nextAsset : asset))))
  }

  const assignAssetIdsToFolder = (assetIds: string[], folderId: string | null) => {
    if (!folderId || !assetIds.length) return
    setFolderAssignments((current) => {
      const next = { ...current }
      assetIds.forEach((assetId) => {
        next[assetId] = Array.from(new Set([...(next[assetId] || []), folderId]))
      })
      return next
    })
  }

  const handleUpload = async (files: File[], explicitFolderId?: string | null) => {
    const limitedFiles = files.slice(0, 50)
    if (!limitedFiles.length) return
    const targetFolderId = explicitFolderId ?? assignableFolderId(selectedFolder)
    setIsUploading(true)
    setUploadErrors([])
    setHandoffError(null)
    setHandoffMessage(null)
    setIsDemoFallback(false)

    const placeholders = limitedFiles.map((file, index): AssetItem => {
      const previewUrl = typeof URL !== "undefined" ? URL.createObjectURL(file) : null
      return {
        asset_id: `asset_upload_${Date.now()}_${index}`,
        media_id: "",
        file_name: file.name,
        preview_url: previewUrl,
        mime_type: file.type,
        media_category: file.type.startsWith("image/") ? "image" : "unknown",
        metadata: { file_size: String(file.size) },
        grade: "unscored",
        score: undefined,
        tags: ["上传中"],
        ai_reasons: ["正在上传，完成后会基于轻量规则生成分档。"],
        issues: [],
        upload_status: "uploading",
        created_at: new Date().toISOString(),
      }
    })

    setAssets((current) => (isDemoFallback ? placeholders : [...placeholders, ...current]))
    setActiveAssetId(placeholders[0]?.asset_id || null)

    const results = await uploadManyMedia(limitedFiles, (result, index) => {
      const placeholder = placeholders[index]
      if (!placeholder) return
      if (result.response) {
        const uploadedAsset = mediaToAssetItem(result.response, index)
        updateAsset(placeholder.asset_id, uploadedAsset)
      } else {
        const message = result.error || "上传失败"
        updateAsset(placeholder.asset_id, failedFileToAssetItem(result.file, message, index))
        setUploadErrors((current) => [...current, { file_name: result.file.name, message }])
      }
    })

    const successCount = results.filter((result) => result.response).length
    const failedCount = results.length - successCount
    const uploadedMediaIds = results
      .map((result) => result.response?.mediaId)
      .filter(Boolean) as string[]

    if (uploadedMediaIds.length) {
      try {
        const scoredAssets = await scoreAssetsWithAssetAgent(uploadedMediaIds)
        const scoredByMediaId = new Map(scoredAssets.map((asset) => [asset.media_id, asset]))
        assignAssetIdsToFolder(scoredAssets.map((asset) => asset.asset_id), targetFolderId)
        setAssets((current) =>
          current
            .filter((asset) => !asset.is_demo)
            .map((asset) => scoredByMediaId.get(asset.media_id) || asset)
        )
        setActiveAssetId(scoredAssets[0]?.asset_id || null)
      } catch (error) {
        setHandoffError(
          error instanceof Error
            ? `AssetAgent 评分暂不可用，已使用轻量规则兜底：${error.message}`
            : "AssetAgent 评分暂不可用，已使用轻量规则兜底。"
        )
        const fallbackAssetIds = results
          .map((result, index) => (result.response ? mediaToAssetItem(result.response, index).asset_id : null))
          .filter(Boolean) as string[]
        assignAssetIdsToFolder(fallbackAssetIds, targetFolderId)
        setAssets((current) => applyLightweightDuplicateRules(current.filter((asset) => !asset.is_demo)))
      }
    }

    if (!successCount && failedCount > 0 && ENABLE_DEMO_FALLBACK) {
      setAssets(demoAssetItems)
      setActiveAssetId(demoAssetItems[0]?.asset_id || null)
      setIsDemoFallback(true)
    } else if (!uploadedMediaIds.length) {
      setAssets((current) => applyLightweightDuplicateRules(current.filter((asset) => !asset.is_demo)))
      setIsDemoFallback(false)
    }
    setIsUploading(false)
  }

  const handleImportProject = () => {
    projectInputRef.current?.click()
  }

  const handleProjectFiles = (files: File[]) => {
    const supportedFiles = files.filter(isSupportedProjectFile)
    if (!supportedFiles.length) {
      setHandoffError("未在该项目文件夹中找到可导入的图片文件。")
      return
    }
    const firstPath = (supportedFiles[0] as File & { webkitRelativePath?: string }).webkitRelativePath
    const rootName = firstPath?.split("/")?.[0]
    let targetFolderId = assignableFolderId(selectedFolder)
    if (rootName) {
      setCustomProjectTitle(rootName)
      const folderId = createCustomFolderId()
      const nextFolder: CustomAssetFolder = {
        id: folderId,
        name: rootName,
        created_at: new Date().toISOString(),
      }
      setCustomFolders((current) => [nextFolder, ...current])
      setSelectedFolder(folderId)
      targetFolderId = folderId
      setCollapsedFolderIds((current) => {
        const next = new Set(current)
        next.delete("all")
        next.delete(folderId)
        return next
      })
    }
    void handleUpload(supportedFiles, targetFolderId)
  }

  const createFolder = () => {
    const nextIndex = customFolders.length + 1
    const name = window.prompt("请输入文件夹名称", `自定义文件夹 ${nextIndex}`)
    if (name === null) return
    const folderName = name.trim() || `自定义文件夹 ${nextIndex}`
    const folderId = createCustomFolderId()
    const nextFolder: CustomAssetFolder = {
      id: folderId,
      name: folderName,
      created_at: new Date().toISOString(),
    }
    setCustomFolders((current) => [nextFolder, ...current])
    if (selectedAssetIds.length) {
      setFolderAssignments((current) => {
        const next = { ...current }
        selectedAssetIds.forEach((assetId) => {
          next[assetId] = Array.from(new Set([...(next[assetId] || []), folderId]))
        })
        return next
      })
      setHandoffMessage(`已创建「${folderName}」，并归入 ${selectedAssetIds.length} 张已选素材。`)
    } else {
      setHandoffMessage(`已创建空文件夹「${folderName}」。`)
    }
    setSelectedFolder(folderId)
    setCollapsedFolderIds((current) => {
      const next = new Set(current)
      next.delete("all")
      next.delete("custom-root")
      return next
    })
  }

  const toggleFolder = (folderId: string) => {
    setCollapsedFolderIds((current) => {
      const next = new Set(current)
      if (next.has(folderId)) {
        next.delete(folderId)
      } else {
        next.add(folderId)
      }
      return next
    })
  }

  const renameFolder = (folderId: string, name: string) => {
    if (folderId.startsWith("custom:") && folderId !== "custom:unfiled") {
      setCustomFolders((current) => current.map((folder) => (folder.id === folderId ? { ...folder, name: name.trim() || folder.name } : folder)))
    }
    setFolderNameOverrides((current) => {
      const next = { ...current }
      if (name.trim()) {
        next[folderId] = name.trim()
      } else {
        delete next[folderId]
      }
      return next
    })
  }

  const deleteFolder = (folderId: string) => {
    const folder = customFolders.find((item) => item.id === folderId)
    if (!folder) return

    const assignedCount = Object.values(folderAssignments).filter((folderIds) => folderIds.includes(folderId)).length
    const confirmed = window.confirm(
      `确定删除文件夹「${folder.name}」吗？其中 ${assignedCount} 张素材不会被删除，会移回未归档素材。`
    )
    if (!confirmed) return

    setCustomFolders((current) => current.filter((item) => item.id !== folderId))
    setFolderAssignments((current) => {
      const next: Record<string, string[]> = {}
      Object.entries(current).forEach(([assetId, folderIds]) => {
        const keptFolderIds = folderIds.filter((id) => id !== folderId)
        if (keptFolderIds.length) next[assetId] = keptFolderIds
      })
      return next
    })
    setFolderNameOverrides((current) => {
      const next = { ...current }
      Object.keys(next).forEach((key) => {
        if (key === folderId || key.startsWith(`${folderId}:`)) delete next[key]
      })
      return next
    })
    setCollapsedFolderIds((current) => {
      const next = new Set(current)
      next.delete(folderId)
      return next
    })
    if (selectedFolder === folderId || selectedFolder.startsWith(`${folderId}:`)) {
      setSelectedFolder("custom:unfiled")
    }
    setHandoffError(null)
    setHandoffMessage(`已删除文件夹「${folder.name}」，素材已移回未归档。`)
  }

  const moveSelectedToFolder = (folderId: string) => {
    if (!selectedAssetIds.length) {
      setHandoffError("请先选择至少一张素材。")
      return
    }
    const targetName = moveTargets.find((target) => target.id === folderId)?.name || "目标文件夹"
    setFolderAssignments((current) => {
      const next = { ...current }
      selectedAssetIds.forEach((assetId) => {
        if (folderId === "custom:unfiled") {
          delete next[assetId]
        } else {
          next[assetId] = [folderId]
        }
      })
      return next
    })
    setSelectedFolder(folderId)
    setHandoffError(null)
    setHandoffMessage(`已将 ${selectedAssetIds.length} 张素材移动到「${targetName}」。`)
  }

  const deleteSelectedAssets = () => {
    if (!selectedAssetIds.length) {
      setHandoffError("请先选择至少一张素材。")
      return
    }
    const confirmed = window.confirm(
      `确定从素材库中删除 ${selectedAssetIds.length} 张照片吗？此操作会从当前素材列表和文件夹归档中移除它们。`
    )
    if (!confirmed) return

    const deletingIds = new Set(selectedAssetIds)
    setAssets((current) => applyLightweightDuplicateRules(current.filter((asset) => !deletingIds.has(asset.asset_id))))
    setFolderAssignments((current) => {
      const next = { ...current }
      selectedAssetIds.forEach((assetId) => {
        delete next[assetId]
      })
      return next
    })
    setActiveAssetId((current) => (current && deletingIds.has(current) ? null : current))
    setSelectedAssetIds([])
    setHandoffError(null)
    setHandoffMessage(`已从素材库删除 ${deletingIds.size} 张照片。`)
  }

  const toggleAsset = (assetId: string) => {
    setSelectedAssetIds((current) =>
      current.includes(assetId) ? current.filter((id) => id !== assetId) : [...current, assetId]
    )
  }

  const selectAdjacentAsset = (direction: -1 | 1) => {
    if (!filteredAssets.length) return
    const currentIndex = activeAsset
      ? filteredAssets.findIndex((asset) => asset.asset_id === activeAsset.asset_id)
      : -1
    const safeIndex = currentIndex >= 0 ? currentIndex : 0
    const nextIndex = (safeIndex + direction + filteredAssets.length) % filteredAssets.length
    setActiveAssetId(filteredAssets[nextIndex].asset_id)
  }

  const sendAssetBatch = async (target: "post" | "coach", batch: AssetItem[]) => {
    if (!batch.length) {
      setHandoffError("请先选择至少一张素材。")
      return
    }
    try {
      setIsHandoffSubmitting(true)
      setHandoffError(null)
      setHandoffMessage(null)
      const result = target === "post" ? await sendAssetsToPost(batch) : await sendAssetsToCoach(batch)
      setLastJobId(result.job_id)
      setHandoffMessage(result.message)
    } catch (error) {
      setHandoffError(error instanceof Error ? error.message : target === "post" ? "发送给后期 Agent 失败" : "发送给学习教练失败")
    } finally {
      setIsHandoffSubmitting(false)
    }
  }

  const sendSelected = (target: "post" | "coach") => sendAssetBatch(target, selectedAssets)

  const markSelectedGrade = (grade: AssetGrade) => {
    setAssets((current) =>
      applyLightweightDuplicateRules(
        current.map((asset) =>
          selectedAssetIds.includes(asset.asset_id)
            ? {
                ...asset,
                grade,
                tags: grade === "A" ? Array.from(new Set([...asset.tags, "精选"])) : asset.tags,
                score: grade === "A" ? Math.max(asset.score || 0, 90) : asset.score,
              }
            : asset
        )
      )
    )
  }

  const loadDemoAssets = () => {
    setAssets(demoAssetItems)
    setActiveAssetId(demoAssetItems[0]?.asset_id || null)
    setSelectedAssetIds([])
    setIsDemoFallback(true)
    setUploadErrors([])
  }

  return (
    <div className="p-6 max-w-[1600px] mx-auto space-y-4">
      <input
        ref={(node) => {
          projectInputRef.current = node
          node?.setAttribute("webkitdirectory", "")
          node?.setAttribute("directory", "")
        }}
        type="file"
        className="hidden"
        multiple
        accept="image/*,.heic,.heif,.dng,.raw,.arw,.cr2,.cr3,.nef,.raf"
        onChange={(event) => {
          handleProjectFiles(Array.from(event.target.files || []))
          event.target.value = ""
        }}
      />
      <AssetUploadZone
        onUpload={handleUpload}
        isUploading={isUploading}
        uploadSummary={uploadSummary}
      />

      {isDemoFallback ? (
        <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm font-bold text-amber-700">
          当前使用示例素材数据，真实素材服务暂不可用或尚未上传真实素材。
        </div>
      ) : null}

      {uploadErrors.length > 0 ? (
        <div className="flex items-center justify-between rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          <span>
            部分照片上传失败。已成功上传 {assets.filter((asset) => asset.upload_status === "uploaded").length} 张，失败 {uploadErrors.length} 张。
          </span>
          <button className="font-bold hover:text-red-800" onClick={() => setUploadErrors([])}>
            继续查看
          </button>
        </div>
      ) : null}

      {!isCacheLoaded ? (
        <div className="rounded-xl border border-slate-200 bg-white p-8 text-center">
          <h2 className="text-xl font-extrabold text-slate-900">正在加载素材库</h2>
          <p className="mt-2 text-sm text-slate-500">正在恢复本地素材、文件夹和筛选状态。</p>
        </div>
      ) : null}

      {isCacheLoaded && !assets.length ? (
        <div className="rounded-xl border border-dashed border-slate-300 bg-white p-8 text-center">
          <h2 className="text-xl font-extrabold text-slate-900">还没有素材</h2>
          <p className="mt-2 text-sm text-slate-500">上传一组照片，开始 AI 筛片与素材管理。</p>
          {ENABLE_DEMO_FALLBACK ? (
            <button
              type="button"
              onClick={loadDemoAssets}
              className="mt-4 rounded-md bg-slate-900 px-4 py-2 text-sm font-bold text-white hover:bg-slate-800"
            >
              加载示例素材
            </button>
          ) : null}
        </div>
      ) : null}

      <AssetToolbar
        stats={stats}
        projectTitle={projectTitle}
        projectDescription={projectDescription}
        onProjectTitleChange={(title) => {
          const selectedCustomFolderId = assignableFolderId(selectedFolder)
          if (selectedCustomFolderId && selectedCustomFolderId === selectedFolder) {
            renameFolder(selectedCustomFolderId, title)
          } else {
            setCustomProjectTitle(title)
          }
        }}
        onImportProject={handleImportProject}
        searchQuery={filter.keyword}
        onSearchChange={(keyword) => setFilter((current) => ({ ...current, keyword }))}
        selectedGrade={filter.grade}
        onSelectGrade={(grade) => setFilter((current) => ({ ...current, grade }))}
        gridFilter={gridFilter}
        onGridFilterChange={setGridFilter}
        dateFilter={dateFilter}
        dateOptions={dateOptions}
        onDateFilterChange={setDateFilter}
        sortBy={filter.sort_by}
        onSortChange={(sort_by) => setFilter((current) => ({ ...current, sort_by }))}
        viewMode={viewMode}
        onViewModeChange={setViewMode}
      />

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-stretch">
        <div className="lg:col-span-2 h-full">
          <AssetSidebar
            folders={folders}
            stats={stats}
            selectedFolder={selectedFolder}
            onSelectFolder={setSelectedFolder}
            onToggleFolder={toggleFolder}
            onRenameFolder={renameFolder}
            onDeleteFolder={deleteFolder}
            onCreateFolder={createFolder}
          />
        </div>

        <div className="lg:col-span-6 h-[960px] overflow-y-auto rounded-xl border border-b-2 border-slate-200 bg-white p-4 pr-3 shadow-sm">
          <AssetGrid
            groups={groups}
            activeAssetId={activeAsset?.asset_id || null}
            selectedAssetIds={selectedAssetIds}
            onSelectAsset={setActiveAssetId}
            onToggleAsset={toggleAsset}
            columns={viewMode === "grid" ? 3 : 4}
          />
        </div>

        <div className="lg:col-span-4 h-full">
          <AssetDetailPanel
            asset={activeAsset}
            currentIndex={activeIndex}
            totalCount={filteredAssets.length}
            onPrev={() => selectAdjacentAsset(-1)}
            onNext={() => selectAdjacentAsset(1)}
            onClose={() => setActiveAssetId(null)}
            onSendToPost={() => activeAsset && sendAssetBatch("post", [activeAsset])}
            onSendToCoach={() => activeAsset && sendAssetBatch("coach", [activeAsset])}
          />
        </div>
      </div>

      <AssetBatchActionBar
        selectedCount={selectedAssetIds.length}
        isSubmitting={isHandoffSubmitting}
        statusMessage={handoffMessage}
        errorMessage={handoffError}
        lastJobId={lastJobId}
        moveTargets={moveTargets}
        onViewJob={() => router.push("/history")}
        onClearSelection={() => setSelectedAssetIds([])}
        onSendToPost={() => sendSelected("post")}
        onSendToCoach={() => sendSelected("coach")}
        onMarkFavorite={() => markSelectedGrade("A")}
        onMarkIgnore={() => markSelectedGrade("reject")}
        onMoveToFolder={moveSelectedToFolder}
        onDeleteSelected={deleteSelectedAssets}
      />
    </div>
  )
}
