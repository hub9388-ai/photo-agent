/**
 * Learning Mock 数据
 * 学习教练相关 mock 数据
 */

import type {
  LearningStats,
  PhotoEvaluation,
  PracticeTask,
  SkillScore,
  WeeklyScore,
} from "@/types/api"

// ============================================================================
// Mock 学习统计
// ============================================================================

export const mockLearningStats: LearningStats = {
  streak: 12,
  completed: 28,
  level: "Lv.3",
}

// ============================================================================
// Mock 照片评估
// ============================================================================

export const mockPhotoEvaluations: PhotoEvaluation[] = [
  {
    id: "eval_001",
    file: "IMG_045.jpg",
    thumbnailUrl: "/mock/images/thumb_045.jpg",
    source: "Coach 分析",
    status: "pending_review",
    statusLabel: "待复习",
    comment: "主体突出，但高光区域轻微过曝，天空层次有所丢失；建议降低曝光补偿，使用渐变镜平衡明暗。",
    suggestion: "尝试低角度仰拍，利用天空作简洁背景，注意过曝控制。",
  },
  {
    id: "eval_002",
    file: "IMG_062.jpg",
    thumbnailUrl: "/mock/images/thumb_062.jpg",
    source: "Coach 分析",
    status: "mastered",
    statusLabel: "已掌握",
    comment: "曝光准确，色彩层次丰富；前景框架构图运用得当，增强了画面纵深感。",
    suggestion: "继续探索不同框架元素（门窗、树枝、建筑结构）。",
  },
  {
    id: "eval_003",
    file: "IMG_078.jpg",
    thumbnailUrl: "/mock/images/thumb_078.jpg",
    source: "Coach 分析",
    status: "pending_review",
    statusLabel: "待复习",
    comment: "人物光影氛围佳，但面部阴影区域偏重，建议使用反光板提高暗部，增强细节。",
    suggestion: "尝试侧逆光拍摄，保留轮廓光并补光提升立体感。",
  },
]

// ============================================================================
// Mock 练习任务
// ============================================================================

export const mockPracticeTasks: PracticeTask[] = [
  {
    id: "task_001",
    title: "练习 1：用大光圈虚化背景",
    description: "拍摄3张低于f/2.0的人像，主体清晰，背景明显虚化",
    target: "背景杂乱影响主体突出",
    problem: "背景干扰、层次不足",
    status: "completed",
    statusLabel: "已完成",
  },
  {
    id: "task_002",
    title: "练习 2：前景框架构图",
    description: "利用门窗、树枝、建筑结构等元素构建前景框架",
    target: "构图层次与纵深不足",
    problem: "画面平淡、缺少引导线",
    status: "in_progress",
    statusLabel: "进行中",
  },
  {
    id: "task_003",
    title: "练习 3：黄金时刻光线捕捉",
    description: "日出后或日落前1小时内拍摄，捕捉温暖柔和的光线",
    target: "光线时机运用不足",
    problem: "光线平硬、氛围欠佳",
    status: "not_started",
    statusLabel: "未开始",
  },
]

// ============================================================================
// Mock 技能分数
// ============================================================================

export const mockSkillScores: SkillScore[] = [
  { name: "曝光控制", score: 75, color: "blue", icon: "sun" },
  { name: "构图能力", score: 62, color: "orange", icon: "scan-line" },
  { name: "色彩感知", score: 88, color: "green", icon: "palette" },
  { name: "后期思路", score: 55, color: "purple", icon: "wand-sparkles" },
]

// ============================================================================
// Mock 周成长分数
// ============================================================================

export const mockWeeklyScores: WeeklyScore[] = [
  { week: "W1", score: 48 },
  { week: "W2", score: 60 },
  { week: "W3", score: 54 },
  { week: "W4", score: 67 },
  { week: "W5", score: 75 },
  { week: "W6", score: 86 },
  { week: "W7", score: 98 },
]
