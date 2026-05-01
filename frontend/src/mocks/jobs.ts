/**
 * Jobs Mock 数据
 * 分析任务和 SSE 事件相关 mock 数据
 */

import type {
  AnalysisJob,
  AgentProgress,
  SSEEvent,
  PostAgentResult,
  CoachAgentResult,
  ExifData,
} from "@/types/api"
import type { HistoryTask } from "@/components/history"

// ============================================================================
// Mock EXIF 数据
// ============================================================================

export const mockExifData: ExifData = {
  iso: 200,
  aperture: "f/2.8",
  shutterSpeed: "1/500s",
  focalLength: "35mm",
  cameraModel: "Sony A7IV",
  lensModel: "35mm f/1.4 GM",
  dateTaken: "2024-04-20T06:15:00",
}

// ============================================================================
// Mock Agent 进度
// ============================================================================

export const mockAgentProgress: { post: AgentProgress; coach: AgentProgress } = {
  post: {
    name: "Post Agent",
    progress: 78,
    status: "running",
    currentStep: "正在分析色彩与曝光...",
    steps: [
      { name: "曝光", status: "completed" },
      { name: "色彩", status: "running" },
      { name: "后期方向", status: "pending" },
      { name: "参数建议", status: "pending" },
    ],
  },
  coach: {
    name: "Coach Agent",
    progress: 100,
    status: "completed",
    currentStep: "已完成构图与主体表达分析",
    steps: [
      { name: "构图", status: "completed" },
      { name: "优点问题", status: "completed" },
      { name: "拍摄建议", status: "completed" },
      { name: "练习任务", status: "completed" },
    ],
  },
}

// ============================================================================
// Mock SSE 事件流
// ============================================================================

export const mockSSEEvents: SSEEvent[] = [
  { time: "10:24:31", agent: "post", message: "正在分析全局曝光分布与高光压制情况..." },
  { time: "10:24:33", agent: "coach", message: "构图主体清晰，前景树木形成良好框架。" },
  { time: "10:24:35", agent: "post", message: "曝光分布均匀，高光区域有轻微过曝。" },
  { time: "10:24:37", agent: "post", message: "色彩偏冷，建议增加暖色平衡，增强日出氛围。" },
  { time: "10:24:40", agent: "coach", message: "主体与背景层次清晰，景深控制得当。" },
  { time: "10:24:42", agent: "post", message: "正在生成后期调整参数建议..." },
  { time: "10:24:45", agent: "coach", message: "分析完成，生成学习建议中..." },
]

// ============================================================================
// Mock Post Agent 结果
// ============================================================================

export const mockPostResult: PostAgentResult = {
  status: "completed",
  summary: "本次结论：适合压暗背景并强化主体，建议下次尝试更低机位。",
  suggestions: [
    {
      category: "总体方向",
      items: ["压暗整体环境，强化山体主体与日出色彩"],
    },
    {
      category: "曝光",
      items: ["降低整体曝光，保留高光细节", "适度提升阴影，增强山体层次"],
    },
    {
      category: "色彩",
      items: ["白平衡偏冷，略微增加暖色温", "提升橙色与黄色饱和度，增强氛围"],
    },
  ],
  params: {
    exposure: "-0.3 EV",
    contrast: "+15",
    highlights: "-40",
    shadows: "+25",
    whites: "+10",
    blacks: "-5",
    clarity: "+20",
    vibrance: "+15",
    saturation: "+5",
  },
}

// ============================================================================
// Mock Coach Agent 结果
// ============================================================================

export const mockCoachResult: CoachAgentResult = {
  status: "completed",
  sections: [
    {
      title: "优点",
      icon: "check",
      items: ["主体明确，山体光影出色", "前景树木增加了层次与空间感"],
    },
    {
      title: "可改进点",
      icon: "alert",
      items: ["机位稍高，前景占比偏小", "前景较暗，存在视觉重量不足"],
    },
    {
      title: "下次怎么拍",
      icon: "map",
      items: [
        "尝试更低机位，扩大前景占比",
        "利用前景引导线增强纵深感",
        "注意日出前的色温变化，提前曝光",
      ],
    },
  ],
  practiceTask: {
    title: "练习任务",
    description: "拍摄一组日出风光，尝试不同机位与前景组合，记录光线变化。",
    isChallenge: true,
  },
}

// ============================================================================
// Mock 完整 Job 数据
// ============================================================================

export const mockAnalysisJob: AnalysisJob = {
  id: "job_abc123",
  title: "天鹅湖清晨拍摄",
  status: "running",
  progress: 85,
  createdAt: "2024-04-28T10:24:00",
  updatedAt: "2024-04-28T10:30:00",
  images: [
    {
      id: "img_001",
      filename: "IMG_001.jpg",
      url: "/mock/images/img_001.jpg",
      thumbnailUrl: "/mock/images/thumb_001.jpg",
      exif: mockExifData,
    },
    {
      id: "img_002",
      filename: "IMG_002.jpg",
      url: "/mock/images/img_002.jpg",
      thumbnailUrl: "/mock/images/thumb_002.jpg",
      exif: { ...mockExifData, iso: 400 },
    },
    {
      id: "img_003",
      filename: "IMG_003.jpg",
      url: "/mock/images/img_003.jpg",
      thumbnailUrl: "/mock/images/thumb_003.jpg",
      exif: { ...mockExifData, aperture: "f/4.0" },
    },
  ],
  agents: {
    post: mockPostResult,
    coach: mockCoachResult,
  },
}

// ============================================================================
// Mock Jobs 列表
// ============================================================================

export const mockJobs: AnalysisJob[] = [
  mockAnalysisJob,
  {
    ...mockAnalysisJob,
    id: "job_def456",
    title: "古城夜景分析",
    status: "completed",
    progress: 100,
  },
  {
    ...mockAnalysisJob,
    id: "job_ghi789",
    title: "人像街拍练习",
    status: "pending",
    progress: 0,
  },
]

// ============================================================================
// Mock 历史任务列表
// ============================================================================

export const mockHistoryTasks: HistoryTask[] = [
  {
    id: "1",
    title: "风光.jpg",
    type: "photo_review",
    typeLabel: "post + coach",
    status: "completed",
    statusLabel: "已完成",
    summary: "Post:  曝光 +0.7，色温 +800     Coach:  2 优点，2 改进点",
    time: "2024-04-25 14:32",
    thumbGradient: "from-[#FDE68A] via-[#64748B] to-[#0F172A]",
    actions: ["view", "rerun"],
  },
  {
    id: "2",
    title: "人像.jpg",
    type: "photo_review",
    typeLabel: "post + coach",
    status: "partial_completed",
    statusLabel: "部分完成",
    summary: "Post:  失败（超时）     Coach:  3 优点，1 改进点（Post 代理超时）",
    time: "2024-04-24 09:15",
    thumbGradient: "from-[#F8FAFC] via-[#FECACA] to-[#334155]",
    actions: ["view", "retry", "rerun"],
  },
  {
    id: "3",
    title: "北京拍摄规划",
    type: "trip_planning",
    typeLabel: "plan",
    status: "running",
    statusLabel: "进行中",
    summary: "3 个机位 / 日出时段 / 天气：多云",
    subSummary: "规划中：生成详细路线与机位建议",
    time: "2024-04-23 21:08",
    thumbGradient: "from-[#FDE68A] via-[#38BDF8] to-[#1E293B]",
    actions: ["view", "reuse"],
  },
  {
    id: "4",
    title: "云南旅拍素材库",
    type: "asset_indexing",
    typeLabel: "asset_indexing",
    status: "completed",
    statusLabel: "已完成",
    summary: "234 张 / A档 45 / B档 120 / C档 40 / 淘汰 29",
    time: "2024-04-15 11:20",
    thumbStyle: "mosaic",
    actions: ["view", "open"],
  },
  {
    id: "5",
    title: "西藏旅拍规划",
    type: "trip_planning",
    typeLabel: "plan",
    status: "cancelled",
    statusLabel: "已取消",
    summary: "用户取消任务",
    time: "2024-04-12 16:45",
    thumbGradient: "from-[#CBD5E1] via-[#64748B] to-[#0F172A]",
    actions: ["view"],
  },
]
