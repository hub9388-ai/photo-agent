/**
 * Assets Mock 数据
 * 素材管理相关 mock 数据
 */

import type {
  Asset,
  AssetProject,
  AssetStats,
  AssetGroup,
} from "@/types/api"
import type { AssetItem } from "@/types/assets"
import type { Folder } from "@/components/assets"
import { mockExifData } from "./jobs"

type LegacyAssetGridItem = {
  id: string
  filename: string
  grade: "A" | "B" | "C" | "rejected" | "duplicate"
  exif?: string
  tags?: { name: string; color?: string }[]
  similarity?: number
}

type LegacyAssetGridGroup = {
  id: string
  name: string
  assets: LegacyAssetGridItem[]
  isSimilarGroup?: boolean
}

type LegacyAssetDetail = {
  id: string
  filename: string
  grade: "A" | "B" | "C" | "rejected" | "duplicate"
  gradeLevel?: number
  date?: string
  location?: string
  resolution?: string
  fileSize?: string
  exif?: string
  cameraInfo?: string
  qualityScore?: number
  tags?: { name: string; positive: boolean }[]
  aiNote?: string
  handoffAgents?: string[]
}

// ============================================================================
// Mock 素材统计
// ============================================================================

export const mockAssetStats: AssetStats = {
  total: 234,
  gradeA: 89,
  gradeB: 76,
  gradeC: 34,
  rejected: 21,
  duplicate: 14,
}

// ============================================================================
// Mock 项目/文件夹结构
// ============================================================================

export const mockAssetProjects: AssetProject[] = [
  {
    id: "all",
    name: "全部素材",
    count: 234,
  },
  {
    id: "p1",
    name: "2024-03 城市街拍",
    count: 58,
  },
  {
    id: "p2",
    name: "2024-04 云南旅拍",
    count: 234,
    children: [
      { id: "p2-1", name: "风光", count: 142 },
      { id: "p2-2", name: "人像", count: 92 },
    ],
  },
  {
    id: "p3",
    name: "2024-05 海边婚纱",
    count: 186,
  },
]

// ============================================================================
// Mock 单个素材
// ============================================================================

export const createMockAsset = (index: number, grade: Asset["grade"]): Asset => ({
  id: `asset_${String(index).padStart(3, "0")}`,
  filename: `IMG_${String(index).padStart(3, "0")}.jpg`,
  grade,
  url: `/mock/images/img_${String(index).padStart(3, "0")}.jpg`,
  thumbnailUrl: `/mock/images/thumb_${String(index).padStart(3, "0")}.jpg`,
  exif: {
    ...mockExifData,
    iso: 200 + Math.floor(Math.random() * 400),
  },
  metadata: {
    dateTaken: "2024-04-20T18:45:00",
    location: "云南 · 洱海",
    resolution: "6000 × 4000 (24MP)",
    fileSize: `${20 + Math.floor(Math.random() * 15)} MB`,
    tags: ["风光", "洱海日落"],
  },
  aiAnalysis: {
    qualityScore: grade === "A" ? 92 : grade === "B" ? 78 : grade === "C" ? 65 : 45,
    tags: [
      { name: "曝光准确", type: "positive" },
      { name: "对焦清晰", type: "positive" },
      ...(grade === "C" || grade === "rejected"
        ? [{ name: "构图一般", type: "warning" as const }]
        : []),
      ...(grade === "rejected"
        ? [{ name: "轻微模糊", type: "negative" as const }]
        : []),
    ],
    note: grade === "A"
      ? "主体清晰，曝光准确，构图稳定，色彩自然，无明显重复。"
      : grade === "B"
      ? "整体表现良好，部分细节可优化。"
      : grade === "C"
      ? "存在明显问题，建议重新拍摄或后期调整。"
      : "质量不佳，建议删除。",
    handoffAgents: grade === "A" || grade === "B" ? ["post", "coach"] : [],
  },
})

// ============================================================================
// Mock 素材列表
// ============================================================================

export const mockAssets: Asset[] = [
  ...Array.from({ length: 3 }, (_, i) => createMockAsset(i + 1, "A")),
  ...Array.from({ length: 2 }, (_, i) => createMockAsset(i + 4, "B")),
  createMockAsset(6, "C"),
  createMockAsset(7, "rejected"),
  createMockAsset(8, "duplicate"),
]

// ============================================================================
// Mock 素材分组（含相似组）
// ============================================================================

export const mockAssetGroups: AssetGroup[] = [
  {
    id: "group-1",
    name: "相似组 A",
    isSimilarGroup: true,
    assets: [
      { ...mockAssets[0], aiAnalysis: { ...mockAssets[0].aiAnalysis, qualityScore: 95 } },
      { ...mockAssets[1], aiAnalysis: { ...mockAssets[1].aiAnalysis, qualityScore: 88 }, grade: "B" },
      { ...mockAssets[2], aiAnalysis: { ...mockAssets[2].aiAnalysis, qualityScore: 82 }, grade: "B" },
    ],
  },
  {
    id: "group-2",
    name: "其他素材",
    assets: mockAssets.slice(3),
  },
]

// ============================================================================
// Mock 选中素材详情
// ============================================================================

export const mockSelectedAsset: Asset = {
  id: "asset_001",
  filename: "IMG_001.jpg",
  grade: "A",
  url: "/mock/images/img_001.jpg",
  thumbnailUrl: "/mock/images/thumb_001.jpg",
  exif: mockExifData,
  metadata: {
    dateTaken: "2024-04-20T18:45:00",
    location: "云南 · 洱海",
    resolution: "6000 × 4000 (24MP)",
    fileSize: "24.8 MB",
    tags: ["风光", "洱海日落"],
  },
  aiAnalysis: {
    qualityScore: 92,
    tags: [
      { name: "曝光准确", type: "positive" },
      { name: "对焦清晰", type: "positive" },
      { name: "构图稳定", type: "positive" },
    ],
    note: "主体清晰，曝光准确，构图稳定，色彩自然，无明显重复。",
    handoffAgents: ["post", "coach"],
  },
}

// ============================================================================
// Mock 前端素材库页面展示数据
// ============================================================================

export const mockAssetFolders: Folder[] = [
  {
    id: "all",
    name: "全部素材",
    count: 234,
  },
  {
    id: "f1",
    name: "2024-03 城市街拍",
    count: 58,
  },
  {
    id: "f2",
    name: "2024-04 云南旅拍",
    count: 234,
    isExpanded: true,
    children: [
      { id: "f2-1", name: "风光", count: 142 },
      { id: "f2-2", name: "人像", count: 92 },
    ],
  },
  {
    id: "f3",
    name: "2024-05 海边婚纱",
    count: 186,
  },
]

export const mockAssetGridGroups: LegacyAssetGridGroup[] = [
  {
    id: "group-1",
    name: "相似组 A",
    isSimilarGroup: true,
    assets: [
      {
        id: "1",
        filename: "IMG_001.jpg",
        grade: "A",
        exif: "ISO 200 · f/2.8 · 1/500s · 35mm",
        tags: [
          { name: "曝光准确", color: "text-green-600" },
          { name: "对焦清晰", color: "text-green-600" },
          { name: "构图稳定", color: "text-green-600" },
        ],
      },
      {
        id: "2",
        filename: "IMG_002.jpg",
        grade: "A",
        exif: "ISO 200 · f/2.8 · 1/640s · 35mm",
        tags: [{ name: "A 档", color: "text-purple-600" }],
        similarity: 87,
      },
      {
        id: "3",
        filename: "IMG_003.jpg",
        grade: "B",
        exif: "ISO 400 · f/4 · 1/320s · 35mm",
        tags: [
          { name: "B 档", color: "text-blue-600" },
          { name: "对焦清晰", color: "text-blue-600" },
        ],
      },
    ],
  },
  {
    id: "group-2",
    name: "其他素材",
    assets: [
      {
        id: "4",
        filename: "IMG_004.jpg",
        grade: "B",
        exif: "ISO 200 · f/2.8 · 1/500s",
        tags: [
          { name: "B 档", color: "text-blue-600" },
          { name: "对焦清晰", color: "text-blue-600" },
        ],
      },
      {
        id: "5",
        filename: "IMG_005.jpg",
        grade: "C",
        exif: "ISO 200 · f/2.8 · 1/500s",
        tags: [
          { name: "C 档", color: "text-orange-600" },
          { name: "曝光偏暗", color: "text-orange-600" },
        ],
      },
      {
        id: "6",
        filename: "IMG_006.jpg",
        grade: "rejected",
        exif: "ISO 200 · f/2.8 · 1/500s",
        tags: [
          { name: "淘汰", color: "text-red-600" },
          { name: "模糊", color: "text-red-600" },
        ],
      },
    ],
  },
]

export const mockAssetDetail: LegacyAssetDetail = {
  id: "1",
  filename: "IMG_001.jpg",
  grade: "A",
  gradeLevel: 1,
  date: "2024-04-20 18:45",
  location: "云南 · 洱海",
  resolution: "6000 × 4000 (24MP)",
  fileSize: "24.8 MB",
  exif: "ISO 200 · f/2.8 · 1/500s · 35mm",
  cameraInfo: "Canon EOS R5 · 35mm f/1.4",
  qualityScore: 92,
  tags: [
    { name: "曝光准确", positive: true },
    { name: "对焦清晰", positive: true },
    { name: "构图稳定", positive: true },
  ],
  aiNote: "主体清晰，曝光准确，构图稳定，色彩自然，无明显重复。",
  handoffAgents: ["post", "coach"],
}

// ============================================================================
// 轻量真实化素材库 Demo Fallback 数据
// ============================================================================

export const demoAssetItems: AssetItem[] = [
  {
    asset_id: "asset_demo_001",
    media_id: "media_demo_001",
    file_name: "IMG_001.jpg",
    preview_url: "https://images.unsplash.com/photo-1500530855697-b586d89ba3ee?w=600&h=420&fit=crop&q=80",
    mime_type: "image/jpeg",
    media_category: "image",
    metadata: {
      iso: "200",
      aperture: "f/2.8",
      shutter: "1/500s",
      focal_length: "35mm",
      camera: "Canon EOS R5",
      captured_at: "2024-04-20 18:45",
      width: 6000,
      height: 4000,
      location: "云南 · 洱海",
    },
    grade: "A",
    score: 92,
    tags: ["曝光准确", "对焦清晰", "构图稳定"],
    ai_reasons: ["主体清晰", "曝光准确", "构图稳定，适合后期调色或学习构图"],
    issues: [],
    duplicate_group_id: null,
    upload_status: "uploaded",
    created_at: "2026-04-28T10:00:00.000Z",
    is_demo: true,
  },
  {
    asset_id: "asset_demo_002",
    media_id: "media_demo_002",
    file_name: "IMG_002.jpg",
    preview_url: "https://images.unsplash.com/photo-1500534314209-a25ddb2bd429?w=600&h=420&fit=crop&q=80",
    mime_type: "image/jpeg",
    media_category: "image",
    metadata: {
      iso: "200",
      aperture: "f/2.8",
      shutter: "1/640s",
      focal_length: "35mm",
      camera: "Sony A7IV",
      location: "云南 · 洱海",
    },
    grade: "duplicate",
    score: 87,
    tags: ["87% 相似", "构图相似"],
    ai_reasons: ["与 IMG_001 画面相似", "曝光和主体位置接近"],
    issues: ["重复组候选"],
    duplicate_group_id: "dup_demo_a",
    upload_status: "uploaded",
    created_at: "2026-04-28T10:03:00.000Z",
    is_demo: true,
  },
  {
    asset_id: "asset_demo_003",
    media_id: "media_demo_003",
    file_name: "IMG_003.jpg",
    preview_url: "https://images.unsplash.com/photo-1472214103451-9374bd1c798e?w=600&h=420&fit=crop&q=80",
    mime_type: "image/jpeg",
    media_category: "image",
    metadata: {
      iso: "400",
      aperture: "f/4",
      shutter: "1/320s",
      focal_length: "50mm",
      location: "云南 · 洱海",
    },
    grade: "B",
    score: 78,
    tags: ["主体明确", "可后期"],
    ai_reasons: ["主体比较明确", "色彩和层次还有后期空间"],
    issues: ["背景略杂"],
    upload_status: "uploaded",
    created_at: "2026-04-28T10:05:00.000Z",
    is_demo: true,
  },
  {
    asset_id: "asset_demo_004",
    media_id: "media_demo_004",
    file_name: "IMG_004.jpg",
    preview_url: "https://images.unsplash.com/photo-1482192505345-5655af888cc4?w=600&h=420&fit=crop&q=80",
    mime_type: "image/jpeg",
    media_category: "image",
    metadata: {
      iso: "800",
      aperture: "f/5.6",
      shutter: "1/250s",
      focal_length: "85mm",
      location: "云南 · 沙溪",
    },
    grade: "B",
    score: 74,
    tags: ["对焦清晰", "主体明确"],
    ai_reasons: ["主体清晰", "背景略有干扰，可送去学习复盘"],
    issues: ["背景干扰"],
    upload_status: "uploaded",
    created_at: "2026-04-28T10:08:00.000Z",
    is_demo: true,
  },
  {
    asset_id: "asset_demo_005",
    media_id: "media_demo_005",
    file_name: "IMG_005.jpg",
    preview_url: "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?w=600&h=420&fit=crop&q=80",
    mime_type: "image/jpeg",
    media_category: "image",
    metadata: {
      width: 4096,
      height: 2731,
    },
    grade: "C",
    score: 66,
    tags: ["EXIF 缺失", "待复核"],
    ai_reasons: ["预览图可用，但未读取到完整 EXIF 信息"],
    issues: ["未读取到完整 EXIF 信息"],
    upload_status: "uploaded",
    created_at: "2026-04-28T10:10:00.000Z",
    is_demo: true,
  },
  {
    asset_id: "asset_demo_006",
    media_id: "media_demo_006",
    file_name: "IMG_006.jpg",
    preview_url: "https://images.unsplash.com/photo-1493246507139-91e8fad9978e?w=600&h=420&fit=crop&q=80",
    mime_type: "image/jpeg",
    media_category: "image",
    metadata: {
      iso: "1600",
      aperture: "f/2",
      shutter: "1/60s",
      focal_length: "35mm",
    },
    grade: "reject",
    score: 42,
    tags: ["模糊", "淘汰候选"],
    ai_reasons: ["快门速度偏低", "主体边缘不清晰"],
    issues: ["轻微模糊", "对焦不实"],
    upload_status: "uploaded",
    created_at: "2026-04-28T10:12:00.000Z",
    is_demo: true,
  },
  {
    asset_id: "asset_demo_007",
    media_id: "media_demo_007",
    file_name: "IMG_007.jpg",
    preview_url: "https://images.unsplash.com/photo-1501785888041-af3ef285b470?w=600&h=420&fit=crop&q=80",
    mime_type: "image/jpeg",
    media_category: "image",
    metadata: {
      iso: "100",
      aperture: "f/8",
      shutter: "1/125s",
      focal_length: "24mm",
      camera: "Nikon Z6",
      location: "云南 · 大理",
    },
    grade: "A",
    score: 90,
    tags: ["风光", "层次稳定"],
    ai_reasons: ["前中后景层次清晰", "适合送去后期形成系列调色"],
    issues: [],
    upload_status: "uploaded",
    created_at: "2026-04-28T10:14:00.000Z",
    is_demo: true,
  },
  {
    asset_id: "asset_demo_008",
    media_id: "media_demo_008",
    file_name: "IMG_008.jpg",
    preview_url: null,
    mime_type: "image/jpeg",
    media_category: "image",
    metadata: {},
    grade: "reject",
    score: 0,
    tags: ["预览失败", "淘汰候选"],
    ai_reasons: ["预览图不可用，建议重传或人工检查源文件。"],
    issues: ["预览图不可用", "EXIF 缺失"],
    upload_status: "failed",
    error_message: "示例：缩略图生成失败",
    created_at: "2026-04-28T10:16:00.000Z",
    is_demo: true,
  },
]
