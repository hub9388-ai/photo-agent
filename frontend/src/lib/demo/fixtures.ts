import type { AgentResultResponse, JobDetailResponse, UploadMediaResponse } from "@/types/api"
import type { AssetItem } from "@/types/assets"
import type { PlanResult } from "@/components/planning/PlanResultCard"
import { catCase, westLakePlan } from "./case"

export const DEMO_MEDIA_ID = "demo-cat-original"
export const demoCatMedia: UploadMediaResponse = {
  mediaId: DEMO_MEDIA_ID, previewUrl: catCase.original, fileName: "街角三花猫.png",
  mimeType: "image/png", storageUri: "demo://street-cat/original",
  metadata: { width: 768, height: 1024 },
}
export const demoAsset: AssetItem = {
  asset_id: DEMO_MEDIA_ID, media_id: DEMO_MEDIA_ID, file_name: demoCatMedia.fileName,
  preview_url: catCase.original, mime_type: "image/png", media_category: "image",
  metadata: { width: 768, height: 1024 }, grade: "unscored", tags: ["宠物", "街头", "三花猫", "竖图"],
  ai_reasons: ["预置案例原图，保留自然街头生活感"], upload_status: "uploaded", is_demo: true,
}
export const demoPlanningInput = {
  city: "杭州", date: "2026-10-24", timePreference: "整个白天", subject: "人文纪实", equipment: "微单轻便", budget: "经济型",
  requirements: "去杭州西湖游玩一天，以摄影为主，想拍湖景和有生活感的人物，步行适中，中午休息。", referenceImages: [],
}
export function demoPlans(): PlanResult[] {
  return [
    { id: "demo-plan-a", name: "方案 A", title: "西湖一日 · 湖岸慢行", indices: [0, 1, 2, 3, 4, 5] },
    { id: "demo-plan-b", name: "方案 B", title: "西湖北岸 · 少走路版", indices: [0, 1, 2, 5] },
    { id: "demo-plan-c", name: "方案 C", title: "西侧湖岸 · 午后细节练习", indices: [2, 3, 4, 5] },
  ].map(plan => ({
    id: plan.id, name: plan.name, title: plan.title,
    spots: plan.indices.map(index => ({ time: westLakePlan[index].time, title: westLakePlan[index].place,
      description: westLakePlan[index].task, position: westLakePlan[index].place,
      lighting: "观察现场光线，时段为演示示意，不代表实时预测", method: westLakePlan[index].equipment })),
    info: [ { label: "案例说明", value: "预置方案；未查询实时天气、交通、开放和日落信息" },
      { label: "器材", value: "轻便相机或手机，按现场条件调整" }, { label: "步行", value: "量力选择路线，预留休息与返程" } ],
  }))
}
export function demoResults(job: JobDetailResponse): AgentResultResponse[] {
  const documentary = /纪实/.test(job.userGoal ?? "")
  const summary = documentary ? "保留三花猫的自然体态与街头环境，适度提升层次，避免用生成式修改替代真实记录。" : "保留街头生活感，小幅提升主体可读性；想要更可爱的表情和体态，可在修图中另行体验圆润预置效果。"
  return job.agents.map(agent => ({
    agent, status: "succeeded", createdAt: job.updatedAt, warnings: ["预置案例，非实时模型分析"],
    summary: agent === "post" ? summary : agent === "coach" ? "用机位做减法：让猫头与背景文字、车轮错开，保留清晰眼神。" : "杭州西湖一日摄影游 · 固定方案示例",
    visibleText: agent === "post" ? [summary, ...catCase.issues].join("\n") : catCase.practice,
    structuredPayload: agent === "post" ? {
      main_issues: catCase.issues, style_directions: [summary],
      adjustments: ["少量增加对比度，让毛发与路面更有层次。", "压低背景亮部，保留猫的白毛细节。", "轻微降低饱和度，减少车牌与背景抢眼的感觉。"],
      xmp_params: { Contrast2012: 8, Highlights2012: -15, Shadows2012: 10, Saturation: -5 },
      source_note: `原图案例，偏好：${job.userGoal || catCase.preference}。固定示例；未经 RAW 分析，数值仅供近似预览。`,
    } : agent === "coach" ? {
      strengths: catCase.strengths, improvements: catCase.improvements, preview_url: catCase.original, source_filename: demoCatMedia.fileName,
      next_exercise: { title: "用机位做减法", description: catCase.practice,
        requirements: ["同一主体拍摄三个机位", "对焦眼睛，保留肢体完整"], acceptance: ["选择主体背景最干净的一张并说明原因"] },
    } : { plans: demoPlans(), provider_note: "预置规划案例，未查询实时数据" },
  }))
}
export function demoAdvice() {
  const rows = [ ["Contrast2012", "对比度", "contrast", 8], ["Highlights2012", "高光", "highlights", -15],
    ["Shadows2012", "阴影", "shadows", 10], ["Saturation", "饱和度", "saturation", -5] ] as const
  return { policy_version: "post-sliders-v1", source_job_id: "demo-cat", source_media_id: DEMO_MEDIA_ID,
    source_result_id: "demo-post", params: Object.fromEntries(rows.map(r => [r[2], r[3] / 100])),
    converted: rows.map(([parameter, label, target, value]) => ({ parameter, label, target, source_value: value,
      source_unit: "摄影软件参考值", value: value / 100, approximate: true, clamped: false, rule: "演示近似初值 v/100", preview: true })),
    skipped: [{ parameter: "局部眼部提亮", reason: "需要局部选区，本例不自动用全局亮度替代" }],
  }
}
