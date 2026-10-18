import type { AgentEventMessage, CreateJobRequest, JobDetailResponse } from "@/types/api"
import { catCase } from "./case"
import { demoResults, DEMO_MEDIA_ID, demoCatMedia, demoAsset } from "./fixtures"

const JOBS = "photoai.demo.jobs.v2"
export const DEMO_ASSETS_KEY = "photoai.demo.assetLibrary.v2"
export function readDemoJobs(): JobDetailResponse[] {
  try { return JSON.parse(localStorage.getItem(JOBS) ?? "[]") }
  catch { return [] }
}
function saveJobs(jobs: JobDetailResponse[]) { localStorage.setItem(JOBS, JSON.stringify(jobs)) }
export function seedDemoAssets() {
  if (!localStorage.getItem("photoai.demo.seed.v2")) {
    localStorage.setItem(DEMO_ASSETS_KEY, JSON.stringify([demoAsset]))
    localStorage.setItem("photoai.demo.seed.v2", "1")
  }
}
export async function demoRequest(path: string, options: RequestInit = {}): Promise<unknown> {
  const url = new URL(path, window.location.origin)
  const method = options.method ?? "GET"
  const body = typeof options.body === "string" ? JSON.parse(options.body) : {}
  const route = url.pathname
  if (method === "POST" && route === "/api/jobs") {
    const input = body as CreateJobRequest
    if (input.agents.includes("plan") && !/杭州|西湖/.test(String(input.context?.city ?? input.user_goal))) throw new Error("演示仅提供杭州西湖一日游案例，请选择杭州。")
    if (!input.agents.includes("plan") && !/自然|可爱|宠物|纪实|三花|猫|看看|后期|学习/.test(input.user_goal ?? "")) throw new Error("演示提供自然可爱或纪实偏好，请选择预置偏好后再分析。")
    if (input.media_ids?.some(id => id !== DEMO_MEDIA_ID)) throw new Error("本演示仅分析预置猫图，不对其他图片套用案例结果。")
    const jobId = input.agents.includes("plan") ? "demo-plan" : input.agents.length === 1 ? `demo-${input.agents[0]}` : "demo-cat"
    const job: JobDetailResponse = { jobId, userGoal: input.user_goal ?? catCase.preference,
      type: input.type, trigger: input.trigger ?? "user", status: "queued", agents: input.agents,
      mediaIds: input.agents.includes("plan") ? [] : [DEMO_MEDIA_ID], context: input.context ?? {}, progress: 0,
      createdAt: new Date().toISOString(), updatedAt: new Date().toISOString() }
    saveJobs([job, ...readDemoJobs().filter(j => j.jobId !== jobId)])
    return { jobId, status: "queued", eventsUrl: "demo://events", resultsUrl: "demo://results" }
  }
  if (route === "/api/jobs") {
    const jobs = readDemoJobs().filter(j => !url.searchParams.get("media_id") || j.mediaIds.includes(url.searchParams.get("media_id")!))
    return { jobs, count: jobs.length }
  }
  const match = route.match(/^\/api\/jobs\/([^/]+)(?:\/(.*))?$/)
  if (match) {
    const job = readDemoJobs().find(j => j.jobId === match[1])
    if (!job) throw new Error("此浏览器还没有该案例的分析记录，请回到分析页点击开始智能分析。")
    if (match[2] === "results") return { jobId: job.jobId, status: job.status, results: demoResults(job) }
    if (match[2]?.endsWith("retry")) { saveJobs(readDemoJobs().map(j => j.jobId === job.jobId ? { ...j, status: "queued" } : j)); return { jobId: job.jobId, status: "queued" } }
    return job
  }
  if (route === `/api/media/${DEMO_MEDIA_ID}`) return demoCatMedia
  if (route === "/api/learning/profile") return { streakDays: 0, completedPracticeTasks: 0, currentLevel: "演示", coachFeedbackCount: readDemoJobs().filter(j => j.agents.includes("coach")).length, source: "job_result_profile", generatedAt: new Date().toISOString() }
  if (route === "/api/handoff") {
    const result = await demoRequest("/api/jobs", { method: "POST", body: JSON.stringify({ type: body.targetAgent === "post" ? "post_process_advice" : "coach_feedback", agents: [body.targetAgent], media_ids: body.mediaIds, user_goal: "自然可爱的街头猫摄影" }) }) as { jobId: string }
    return { handoffId: "demo-handoff", jobId: result.jobId, status: "accepted", message: "已创建预置案例任务" }
  }
  if (route === "/api/agents/asset/score" && body.mediaIds?.some((id: string) => id !== DEMO_MEDIA_ID)) throw new Error("演示仅为原图提供预置评分，不会把原图评分套用到编辑版本。")
  if (route === "/api/agents/asset/score") return { assets: [{ assetId: demoAsset.asset_id, mediaId: DEMO_MEDIA_ID, fileName: demoAsset.file_name,
    previewUrl: demoAsset.preview_url, grade: "B", score: 78, tags: demoAsset.tags, aiReasons: ["示例评分：主体完整，背景略杂乱"],
    issues: ["背景文字和车轮抢眼"], metadata: { width: 768, height: 1024 }, uploadStatus: "uploaded" }], duplicateGroups: [], warnings: ["预置评分"], scoringMethod: "demo_fixture" }
  throw new Error("此操作需要完整服务；演示支持猫图分析、调色、圆润案例与西湖规划。")
}
export function subscribeDemoJob(jobId: string, emit: (event: AgentEventMessage) => void) {
  const job = readDemoJobs().find(j => j.jobId === jobId)
  if (!job) return () => {}
  const steps = [ { type: "job.started", agent: null, message: "开始回放预置案例" },
    ...job.agents.flatMap(agent => [ { type: "agent.started" as const, agent, message: `${agent}：读取案例` },
      { type: "agent.progress" as const, agent, message: `${agent}：回放分析过程` } ]),
    { type: "job.completed", agent: null, message: "案例回放完成，结果为预置示例" } ] as const
  const timers = steps.map((step, index) => window.setTimeout(() => {
    if (step.type === "job.completed") saveJobs(readDemoJobs().map(j => j.jobId === jobId ? { ...j, status: "completed", progress: 1 } : j))
    emit({ ...step, jobId, eventId: `demo-${index}`, seq: index + 1, createdAt: new Date().toISOString(), payload: { progress: 0.6 } })
  }, 300 * (index + 1)))
  return () => timers.forEach(window.clearTimeout)
}
