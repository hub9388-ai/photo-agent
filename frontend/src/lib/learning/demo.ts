import type { PhotoEvaluation, SkillScore, WeeklyScore } from "@/types/api"
import type { PracticeAttempt, PracticeTask } from "@/types/learning"

const now = new Date().toISOString()

export const demoLearningBanner =
  "当前使用示例练习任务，用于展示学习教练闭环。真实 Coach 结果可用后会自动替换。"

export const demoPhotoEvaluations: PhotoEvaluation[] = [
  {
    id: "demo_eval_1",
    file: "IMG_045.jpg",
    thumbnailUrl: "",
    source: "CoachAgent 示例反馈",
    status: "pending_review",
    statusLabel: "待复习",
    comment: "主体突出，但高光区域略抢眼，背景层次仍可优化。",
    suggestion: "尝试降低曝光补偿，保留天空细节，并让主体与背景距离更明确。",
  },
  {
    id: "demo_eval_2",
    file: "IMG_062.jpg",
    thumbnailUrl: "",
    source: "CoachAgent 示例反馈",
    status: "mastered",
    statusLabel: "已整理",
    comment: "曝光准确，色彩层次丰富，前景框架增强了画面纵深。",
    suggestion: "继续探索不同框架元素，记录光线变化。",
  },
]

export const demoPracticeAttempts: PracticeAttempt[] = [
  {
    attemptId: "demo_attempt_1",
    practice_task_id: "practice_demo_bokeh",
    status: "completed",
    feedbackSummary: "基本完成：主体与背景分离更明显，但背景亮点仍略抢眼。",
    visibleText: "主体与背景分离更明显；下一步尝试更长焦段和更干净背景。",
    structuredPayload: {
      completion: "基本完成",
      progress: "主体更突出",
      next_steps: ["拉开主体与背景距离", "避开高亮杂物"],
    },
    createdAt: now,
    isDemo: true,
  },
]

export const demoPracticeTasks: PracticeTask[] = [
  {
    id: "practice_demo_bokeh",
    practice_task_id: "practice_demo_bokeh",
    title: "用大光圈虚化背景",
    description: "拍摄 3 张 f/2.8 以下的人像或静物，让主体清晰、背景简洁。",
    target: "背景干扰较多",
    problem: "主体与背景分离不足",
    sourceAgent: "coach",
    goal: "用大光圈虚化背景，突出主体，并减少背景亮色干扰。",
    status: "in_progress",
    statusLabel: "练习中",
    attempts: demoPracticeAttempts,
    createdAt: now,
    updatedAt: now,
    isDemo: true,
  },
  {
    id: "practice_demo_frame",
    practice_task_id: "practice_demo_frame",
    title: "练习前景框架构图",
    description: "使用门窗、树枝、栏杆等元素构建前景框架，让画面更有层次。",
    target: "构图层次不足",
    problem: "画面缺少引导线",
    sourceAgent: "coach",
    goal: "用前景元素组织画面，让主体位置更明确。",
    status: "not_started",
    statusLabel: "未开始",
    attempts: [],
    isDemo: true,
  },
  {
    id: "practice_demo_golden_light",
    practice_task_id: "practice_demo_golden_light",
    title: "黄金时刻光线捕捉",
    description: "在日出后或日落前 1 小时拍摄，记录同一场景 3 种光线角度。",
    target: "光线时机运用不足",
    problem: "氛围欠佳",
    sourceAgent: "coach",
    goal: "识别柔和侧光、逆光和轮廓光，并选择最适合主体的一张。",
    status: "not_started",
    statusLabel: "未开始",
    attempts: [],
    isDemo: true,
  },
]

export const demoSkillScores: SkillScore[] = [
  { name: "曝光控制", score: 42, color: "blue", icon: "sun" },
  { name: "构图能力", score: 46, color: "orange", icon: "scan-line" },
  { name: "色彩感知", score: 52, color: "green", icon: "palette" },
  { name: "后期思路", score: 38, color: "purple", icon: "wand-sparkles" },
]

export const demoWeeklyScores: WeeklyScore[] = [
  { week: "W1", score: 35 },
  { week: "W2", score: 38 },
  { week: "W3", score: 42 },
  { week: "W4", score: 48 },
  { week: "W5", score: 55 },
  { week: "W6", score: 62 },
  { week: "W7", score: 68 },
]

export const demoAttemptResult = {
  title: "示例复盘：基本完成",
  summary: "主体与背景分离更明显，但背景亮点仍然略抢眼。",
  nextStep: "尝试更长焦段，并让主体远离杂乱背景。",
}
