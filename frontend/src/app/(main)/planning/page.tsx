"use client"

import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react"
import { useSearchParams } from "next/navigation"
import { AlertTriangle, CheckCircle2, Loader2 } from "lucide-react"
import { PlanningForm, PlanResultCard, PlanAdjustmentCard } from "@/components/planning"
import type { PlanningFormData, PlanResult } from "@/components/planning"
import { createJob, getJob, getJobResults, subscribeJobEvents } from "@/lib/api"
import { mockPlanningPagePlans } from "@/lib/mocks"
import type { AgentEventMessage, AgentResultResponse, JobStatus } from "@/types/api"

type PlanningNoticeKind = "info" | "success" | "warning" | "error"
const PLANNING_DRAFT_CACHE_KEY = "photoai.planningDraft.v1"
const PLANNING_ADOPTED_PLAN_KEY = "photoai.adoptedPlanningPlan.v1"
const PLANNING_PRESET_DRAFT_KEY = "photoai.planningPresetDraft.v1"

type ParsedPlanningConstraints = {
  start_time: string | null
  end_time: string | null
  required_locations: string[]
  excluded_locations: string[]
  shooting_goals: string[]
  required_meals: {
    lunch: boolean
    lunch_time: string | null
    dinner: boolean
    dinner_time: string | null
  }
  route_pace: "relaxed" | "compact" | "normal"
  traffic_preferences: string[]
  budget: string
  style_preferences: string[]
  special_goals: string[]
  forbidden_assumptions: string[]
}

const SHOOTING_GOAL_PATTERN = /落日|日落|日出|蓝调|夜景|黄金时刻|晚霞|朝霞|剪影|星空/
const GENERIC_PLACE_PATTERN = /核心观景点|开阔步道|滨水平台|安静街巷|高处机位|目标地点|推荐机位|附近|路线中段|终点附近|POI 待确认/
const NON_PLACE_SPOT_TITLE_PATTERN =
  /模特|侧\d|侧脸|正面|背影|姿态|动作|表情|天空|云层|橙黄|渐变|构图|三分|引导线|压缩|焦段|虚化|光斑|色温|暖色|冷色|特写|半身|全身|逆光|侧光|顺光|剪影|光线|氛围|画面|色彩/
const TRANSFER_KEYWORD_PATTERN = /花果山|连岛|连云老街|海州湾|栈桥|灯塔|小青岛|西湖|白堤|苏堤|外滩|南京东路|橘子洲|岳麓山|洱海|喜洲|故宫|景山|海边|古城|老街|山|岛|湾|湖|街|桥/
const CHINESE_TIME_NUMBER = "[零〇一二两三四五六七八九十百\\d]{1,3}"
const TIME_TOKEN_SOURCE = `(?:上午|早上|早晨|下午|中午|晚上)?\\s*的?\\s*${CHINESE_TIME_NUMBER}(?:\\s*(?:点|:|：)\\s*(?:半|${CHINESE_TIME_NUMBER})?)?`

function textValue(value: unknown, fallback = ""): string {
  if (typeof value === "string") return value
  if (typeof value === "number") return String(value)
  return fallback
}

function arrayValue(value: unknown): unknown[] {
  return Array.isArray(value) ? value : []
}

function stringList(value: unknown): string[] {
  if (!value) return []
  if (Array.isArray(value)) return value.flatMap(stringList).filter(Boolean)
  if (typeof value === "object") return Object.values(value as Record<string, unknown>).flatMap(stringList)
  return [String(value)]
}

function payloadValue(payload: Record<string, unknown>, ...keys: string[]): unknown {
  for (const key of keys) {
    if (key in payload) return payload[key]
  }
  return undefined
}

function mapSpot(value: unknown, index: number) {
  const item = value && typeof value === "object" ? (value as Record<string, unknown>) : {}
  return {
    time: textValue(item.time ?? item.start_time ?? item.startTime, index === 0 ? "06:00" : index === 1 ? "10:00" : "16:30"),
    title: textValue(item.title ?? item.location ?? item.spot ?? item.name, `推荐机位 ${index + 1}`),
    description: textValue(item.description ?? item.reason ?? item.task, "根据当前拍摄需求安排的可执行机位。"),
    position: textValue(item.position ?? item.viewpoint ?? item.address, "现场选择开阔且安全的位置"),
    lighting: textValue(item.lighting ?? item.light ?? item.light_condition, "按当天光线微调"),
    method: textValue(item.method ?? item.shooting_method ?? item.tip, "先拍环境，再补主体特写"),
  }
}

function isGenericSpot(spot: ReturnType<typeof mapSpot>): boolean {
  return (
    /^推荐机位\s*\d+$/.test(spot.title) ||
    spot.title === "核心拍摄点" ||
    !isConcreteSpotTitle(spot.title) ||
    spot.description.includes("根据当前拍摄需求") ||
    spot.position.includes("现场选择") ||
    spot.position.includes("用户输入地点")
  )
}

function isLikelyNonPlacePhrase(value: string): boolean {
  const text = value.trim()
  if (!text) return true
  if (/^转场/.test(text)) return false
  if (/^(日出|日落|落日|蓝调|夜景|黄金时刻|剪影)$/.test(text)) return true
  return NON_PLACE_SPOT_TITLE_PATTERN.test(text) && !TRANSFER_KEYWORD_PATTERN.test(text)
}

function isConcreteSpotTitle(value: string): boolean {
  const text = value.trim()
  if (!text) return false
  if (GENERIC_PLACE_PATTERN.test(text)) return false
  if (isLikelyNonPlacePhrase(text)) return false
  return true
}

function minutesToTime(totalMinutes: number): string {
  const hours = Math.floor(totalMinutes / 60) % 24
  const minutes = totalMinutes % 60
  return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}`
}

function timeToMinutes(time: string): number | null {
  const match = time.match(/(\d{1,2})[:：](\d{1,2})/)
  if (!match) return null
  return Number(match[1]) * 60 + Number(match[2])
}

function addHours(time: string, hours: number): string {
  const [hour = "9", minute = "0"] = time.split(":")
  return minutesToTime(Number(hour) * 60 + Number(minute) + Math.round(hours * 60))
}

function planningConstraintText(data?: Partial<PlanningFormData>): string {
  return [data?.city, data?.timePreference, data?.subject, data?.requirements].filter(Boolean).join(" ")
}

function uniqueStrings(values: string[]) {
  return Array.from(new Set(values.map((value) => value.trim()).filter(Boolean)))
}

function cleanLocationCandidate(value: string): string {
  return value
    .replace(SHOOTING_GOAL_PATTERN, "")
    .replace(/专项|窗口|时刻/g, "")
    .replace(/^(去|到|拍|安排|包含|包括|一下|一些|几个|：|:)/, "")
    .replace(/(机位|路线|景点|地点|方案|拍摄|游玩|打卡|看看).*$/, "$1")
    .replace(/^(当地|本地|特色|特有的?)/, "")
    .trim()
}

function splitLocationCandidate(value: string): string[] {
  const normalized = cleanLocationCandidate(value)
  if (!normalized) return []
  return normalized
    .split(/(?:以及|还有|并且|同时|和|及|、|,|，|\/|＋|\+)/)
    .map(cleanLocationCandidate)
    .filter((item) => item.length >= 2)
    .filter((item) => !/午饭|晚饭|早餐|吃饭|用餐|餐饮|美食|小吃|预算|不要|避开/.test(item))
    .map((item) => {
      if (/园林/.test(item) && !/拙政园|留园|狮子林|网师园|沧浪亭/.test(item)) return "园林类 POI"
      return item
    })
}

function extractListAfterKeywords(text: string, keywordPattern: string): string[] {
  const results: string[] = []
  const regex = new RegExp(`(?:${keywordPattern})([^。；;\\n]{2,48})`, "g")
  for (const match of text.matchAll(regex)) {
    results.push(...splitLocationCandidate(match[1]))
  }
  return uniqueStrings(results).slice(0, 6)
}

function extractShootingGoals(data?: Partial<PlanningFormData>): string[] {
  const text = planningConstraintText(data)
  return [
    /日落|落日|晚霞|黄金时刻/.test(text) ? "落日/黄金时刻" : "",
    /日出|朝霞/.test(text) ? "日出" : "",
    /蓝调/.test(text) ? "蓝调时刻" : "",
    /夜景/.test(text) ? "夜景" : "",
    /剪影/.test(text) ? "剪影" : "",
    /星空/.test(text) ? "星空" : "",
  ].filter(Boolean)
}

function extractRequiredLocations(data?: Partial<PlanningFormData>): string[] {
  const text = data?.requirements || ""
  return extractListAfterKeywords(text, "必须去|一定要去|想去|希望去|要去|包含|包括|重点拍|围绕|安排")
}

function extractExcludedLocations(data?: Partial<PlanningFormData>): string[] {
  const text = data?.requirements || ""
  return extractListAfterKeywords(text, "不要去|不去|避开|不要安排|不想去|排除")
}

function routePace(data?: Partial<PlanningFormData>): ParsedPlanningConstraints["route_pace"] {
  const text = planningConstraintText(data)
  if (/不要太赶|轻松|慢节奏|休闲|少走路|老人|小孩|体力/.test(text)) return "relaxed"
  if (/紧凑|多拍|多安排|效率|赶一点/.test(text)) return "compact"
  return "normal"
}

function trafficPreferences(data?: Partial<PlanningFormData>) {
  const text = planningConstraintText(data)
  return [
    /地铁/.test(text) ? "优先地铁" : "",
    /公交/.test(text) ? "可用公交" : "",
    /打车|出租|网约车/.test(text) ? "可打车衔接" : "",
    /步行|少走路/.test(text) ? "控制步行距离" : "",
    /自驾|开车/.test(text) ? "考虑停车与自驾路线" : "",
  ].filter(Boolean)
}

function stylePreferences(data?: Partial<PlanningFormData>) {
  const text = planningConstraintText(data)
  return [
    /电影感/.test(text) ? "电影感" : "",
    /ins|小红书/.test(text) ? "社交平台风格" : "",
    /日系/.test(text) ? "日系清透" : "",
    /复古/.test(text) ? "复古" : "",
    /夜景|蓝调/.test(text) ? "夜景/蓝调" : "",
    /人文|纪实/.test(text) ? "人文纪实" : "",
  ].filter(Boolean)
}

function specialGoals(data?: Partial<PlanningFormData>) {
  const text = planningConstraintText(data)
  return [
    /室内/.test(text) ? "增加室内备选" : "",
    /雨天|下雨/.test(text) ? "准备雨天替代方案" : "",
    /日落/.test(text) ? "覆盖日落机位" : "",
    /日出/.test(text) ? "覆盖日出机位" : "",
    /当地美食|美食|小吃/.test(text) ? "包含当地美食建议" : "",
  ].filter(Boolean)
}

function parsePlanningConstraints(data?: Partial<PlanningFormData>): ParsedPlanningConstraints {
  const lunchRequired = wantsLunchNode(data)
  const dinnerRequired = wantsDinnerNode(data)
  return {
    start_time: extractStartTime(data),
    end_time: extractEndTime(data),
    required_locations: extractRequiredLocations(data),
    excluded_locations: extractExcludedLocations(data),
    shooting_goals: extractShootingGoals(data),
    required_meals: {
      lunch: lunchRequired,
      lunch_time: lunchRequired ? extractLunchTime(data) : null,
      dinner: dinnerRequired,
      dinner_time: dinnerRequired ? extractDinnerTime(data) : null,
    },
    route_pace: routePace(data),
    traffic_preferences: trafficPreferences(data),
    budget: data?.budget || "",
    style_preferences: stylePreferences(data),
    special_goals: specialGoals(data),
    forbidden_assumptions: [
      lunchRequired ? "" : "不要默认加入午饭节点",
      dinnerRequired ? "" : "不要默认加入晚饭节点",
      "不要用上一次任务地点污染当前规划",
      "不要用系统兜底覆盖用户其他要求",
    ].filter(Boolean),
  }
}

function normalizePeriodHour(period: string, hour: number): number {
  if ((period === "下午" || period === "晚上") && hour < 12) return hour + 12
  if (period === "中午" && hour < 11) return hour + 12
  return hour
}

function parseChineseNumber(value: string | undefined): number | null {
  if (!value) return null
  if (/^\d+$/.test(value)) return Number(value)
  const normalized = value.replace(/两/g, "二").replace(/〇/g, "零")
  const digits: Record<string, number> = {
    零: 0,
    一: 1,
    二: 2,
    三: 3,
    四: 4,
    五: 5,
    六: 6,
    七: 7,
    八: 8,
    九: 9,
  }
  if (normalized === "十") return 10
  const tenIndex = normalized.indexOf("十")
  if (tenIndex >= 0) {
    const tensText = normalized.slice(0, tenIndex)
    const onesText = normalized.slice(tenIndex + 1)
    const tens = tensText ? digits[tensText] ?? 0 : 1
    const ones = onesText ? digits[onesText] ?? 0 : 0
    return tens * 10 + ones
  }
  return [...normalized].reduce((total, char) => total * 10 + (digits[char] ?? 0), 0)
}

function parseTimeToken(token: string): string | null {
  const match = token.match(new RegExp(`(上午|早上|早晨|下午|中午|晚上)?\\s*的?\\s*(${CHINESE_TIME_NUMBER})(?:\\s*(?:点|:|：)\\s*(半|${CHINESE_TIME_NUMBER})?)?`))
  if (!match) return null
  const parsedHour = parseChineseNumber(match[2])
  if (parsedHour === null) return null
  const parsedMinute = match[3] === "半" ? 30 : parseChineseNumber(match[3])
  const hour = normalizePeriodHour(match[1] || "", parsedHour)
  const minute = parsedMinute ?? 0
  return minutesToTime(hour * 60 + minute)
}

function extractTimeRangeFromText(text: string): { start: string; end: string } | null {
  const looseRange = text.match(new RegExp(`(${TIME_TOKEN_SOURCE})\\s*(?:开始|出发|起)?[^。；;\\n]{0,12}(?:到|至|直到|—|–|-|~|～)\\s*(${TIME_TOKEN_SOURCE})\\s*(?:结束|前|之前|以前|止|收尾)?`))
  if (looseRange) {
    const start = parseTimeToken(looseRange[1])
    const end = parseTimeToken(looseRange[2])
    if (start && end) return { start, end }
  }
  const range = text.match(new RegExp(`(${TIME_TOKEN_SOURCE})\\s*(?:到|至|直到|—|–|-|~|～)\\s*(${TIME_TOKEN_SOURCE})`))
  if (!range) return null
  const start = parseTimeToken(range[1])
  const end = parseTimeToken(range[2])
  return start && end ? { start, end } : null
}

function extractTimeNearKeywords(text: string, keywordPattern: string): string | null {
  const keywordFirst = new RegExp(`(?:${keywordPattern})[^0-9零〇一二两三四五六七八九十上午下午晚上中午早晨早上]{0,8}(${TIME_TOKEN_SOURCE})`)
  const keywordFirstMatch = text.match(keywordFirst)
  if (keywordFirstMatch) return parseTimeToken(keywordFirstMatch[1])

  const timeFirst = new RegExp(`(${TIME_TOKEN_SOURCE})([^午晚早餐饭美食]{0,8})(?:${keywordPattern})`)
  const matches = [...text.matchAll(new RegExp(timeFirst, "g"))]
  const lastMatch = [...matches].reverse().find((match) => !/游玩|玩|行程|结束|到|至|开始|出发/.test(match[2] || ""))
  if (lastMatch) return parseTimeToken(lastMatch[1])
  return null
}

function extractStartTime(data?: Partial<PlanningFormData>): string | null {
  const text = data?.requirements || ""
  const flexibleRange = extractTimeRangeFromText(text)
  if (flexibleRange) return flexibleRange.start
  const rangeMatch = text.match(/(\d{1,2})[:：](\d{1,2})\s*[–—-]\s*(\d{1,2})[:：](\d{1,2})/)
  if (rangeMatch) return minutesToTime(Number(rangeMatch[1]) * 60 + Number(rangeMatch[2]))
  const explicitStart = text.match(new RegExp(`(?:从|自)\\s*(${TIME_TOKEN_SOURCE})(?:\\s*(?:开始|出发|集合|到达|起))?`))
  if (explicitStart) return parseTimeToken(explicitStart[1])
  const suffixStart = text.match(new RegExp(`(${TIME_TOKEN_SOURCE})\\s*(?:开始|出发|集合|到达|起)`))
  if (suffixStart) return parseTimeToken(suffixStart[1])
  return null
}

function extractEndTime(data?: Partial<PlanningFormData>): string | null {
  const text = data?.requirements || ""
  const flexibleRange = extractTimeRangeFromText(text)
  if (flexibleRange) return flexibleRange.end
  const rangeMatch = text.match(/(\d{1,2})[:：](\d{1,2})\s*[–—-]\s*(\d{1,2})[:：](\d{1,2})/)
  if (rangeMatch) return minutesToTime(Number(rangeMatch[3]) * 60 + Number(rangeMatch[4]))
  const explicitEnd = text.match(new RegExp(`(?:到|至|直到|玩到|游玩到|结束到)\\s*(${TIME_TOKEN_SOURCE})\\s*(?:结束|前|之前|以前|止|收尾)`))
  if (explicitEnd) return parseTimeToken(explicitEnd[1])
  const matches = [...text.matchAll(new RegExp(`(?:到|至|直到|玩到|游玩到|结束到)\\s*(${TIME_TOKEN_SOURCE})`, "g"))]
  const validMatch = [...matches].reverse().find((match) => {
    const matchIndex = match.index ?? 0
    const prefix = text.slice(Math.max(0, matchIndex - 4), matchIndex)
    return !/调整|改|改成|变更|设置|修改/.test(prefix)
  })
  return validMatch ? parseTimeToken(validMatch[1]) : null
}

function distributeTimeSlots(start: string, end: string, count: number): string[] {
  const startMinutes = timeToMinutes(start)
  const endMinutes = timeToMinutes(end)
  if (startMinutes === null || endMinutes === null || endMinutes <= startMinutes) return [start]
  if (count <= 1) return [start]
  const step = (endMinutes - startMinutes) / (count - 1)
  return Array.from({ length: count }, (_, index) => minutesToTime(Math.round(startMinutes + step * index)))
}

function wantsFullDay(data?: Partial<PlanningFormData>): boolean {
  const start = extractStartTime(data)
  const end = extractEndTime(data)
  const dinner = extractDinnerTime(data)
  const startMinutes = start ? timeToMinutes(start) : null
  const endMinutes = end ? timeToMinutes(end) : null
  const dinnerMinutes = dinner ? timeToMinutes(dinner) : null
  return (
    /全天|整天|一整天|一天|整个白天|白天|上午.*下午|早.*晚/.test(planningConstraintText(data)) ||
    (startMinutes !== null && dinnerMinutes !== null && dinnerMinutes >= 18 * 60 && (endMinutes === null || endMinutes - startMinutes >= 6 * 60)) ||
    (startMinutes !== null && endMinutes !== null && endMinutes - startMinutes >= 7 * 60)
  )
}

function wantsDetailedRoute(data?: Partial<PlanningFormData>): boolean {
  return /细化|具体|机位|路线|站位|详细|玩一天|一天|整个白天/.test(planningConstraintText(data))
}

function wantsMealNode(data?: Partial<PlanningFormData>): boolean {
  return /午饭|午餐|晚饭|晚餐|早饭|早餐|吃饭|用餐|餐饮|饭点|美食|经济实惠|休息/.test(planningConstraintText(data))
}

function wantsDinnerNode(data?: Partial<PlanningFormData>): boolean {
  return /晚饭|晚餐|晚上.*吃饭|当地美食|美食推荐/.test(planningConstraintText(data))
}

function wantsLunchNode(data?: Partial<PlanningFormData>): boolean {
  return wantsMealNode(data) && !/只.*晚饭|只.*晚餐/.test(planningConstraintText(data))
}

function extractLunchTime(data?: Partial<PlanningFormData>): string | null {
  const text = planningConstraintText(data)
  if (!wantsMealNode(data)) return null
  const nearbyTime = extractTimeNearKeywords(text, "午饭|午餐|中饭|吃饭|用餐|餐饮|饭点")
  if (nearbyTime) return nearbyTime
  const rangeMatch = text.match(/(\d{1,2})[:：](\d{1,2})\s*[–—-]\s*(\d{1,2})[:：](\d{1,2}).{0,8}(午饭|午餐|中饭|吃饭|用餐|餐饮|饭点)/)
  if (rangeMatch) return minutesToTime(Number(rangeMatch[1]) * 60 + Number(rangeMatch[2]))
  const reverseRangeMatch = text.match(/(午饭|午餐|中饭|吃饭|用餐|餐饮|饭点).{0,8}(\d{1,2})[:：](\d{1,2})\s*[–—-]\s*(\d{1,2})[:：](\d{1,2})/)
  if (reverseRangeMatch) return minutesToTime(Number(reverseRangeMatch[2]) * 60 + Number(reverseRangeMatch[3]))
  return "12:00"
}

function extractDinnerTime(data?: Partial<PlanningFormData>): string | null {
  const text = planningConstraintText(data)
  if (!wantsDinnerNode(data)) return null
  const nearbyTime = extractTimeNearKeywords(text, "晚饭|晚餐|夜饭|美食|小吃")
  if (nearbyTime) return nearbyTime
  const rangeMatch = text.match(/(\d{1,2})[:：](\d{1,2})\s*[–—-]\s*(\d{1,2})[:：](\d{1,2}).{0,8}(晚饭|晚餐|夜饭|美食|小吃)/)
  if (rangeMatch) return minutesToTime(Number(rangeMatch[1]) * 60 + Number(rangeMatch[2]))
  return "18:30"
}

function timeSlotsForData(data?: Partial<PlanningFormData>): string[] {
  const startTime = extractStartTime(data)
  const endTime = extractEndTime(data)
  const timePreference = data?.timePreference || ""

  if (wantsFullDay(data)) {
    const start = startTime || (timePreference.includes("上午") ? "09:00" : "08:30")
    if (endTime) return distributeTimeSlots(start, endTime, 6)
    return [start, addHours(start, 1.5), addHours(start, 3), addHours(start, 5), addHours(start, 7), addHours(start, 8.5)]
  }

  if (timePreference.includes("日出")) return ["05:30", "06:20", "07:30"]
  if (timePreference.includes("上午")) {
    const start = startTime || "09:00"
    return endTime ? distributeTimeSlots(start, endTime, 4) : [start, addHours(start, 1.5), addHours(start, 2.75)]
  }
  if (timePreference.includes("下午")) return ["14:30", "16:00", "17:20"]
  if (timePreference.includes("日落")) return ["16:30", "17:40", "18:30"]
  if (timePreference.includes("夜")) return ["18:40", "19:40", "20:30"]
  if (timePreference.includes("白天")) return ["09:00", "11:00", "14:00", "16:30"]
  return ["09:00", "11:00", "15:30"]
}

function estimateSunsetTime(data?: Partial<PlanningFormData>): string {
  const text = planningConstraintText(data)
  const month = Number((data?.date || "").match(/[-/](\d{1,2})[-/]/)?.[1] || 5)
  const coastalLate = /连云港|青岛|大连|厦门|海边|海岸|连岛/.test(text)
  if (month >= 6 && month <= 8) return coastalLate ? "19:05" : "19:00"
  if (month === 5 || month === 9) return coastalLate ? "18:50" : "18:40"
  if (month === 4 || month === 10) return "18:15"
  return "17:35"
}

function estimateSunriseTime(data?: Partial<PlanningFormData>): string {
  const month = Number((data?.date || "").match(/[-/](\d{1,2})[-/]/)?.[1] || 5)
  if (month >= 6 && month <= 8) return "05:10"
  if (month === 5 || month === 9) return "05:35"
  if (month === 4 || month === 10) return "06:00"
  return "06:40"
}

function goldenWindow(data?: Partial<PlanningFormData>) {
  const sunset = estimateSunsetTime(data)
  const sunrise = estimateSunriseTime(data)
  const sunsetMinutes = timeToMinutes(sunset) ?? 18 * 60 + 40
  const sunriseMinutes = timeToMinutes(sunrise) ?? 5 * 60 + 40
  return {
    sunset,
    sunsetStart: minutesToTime(sunsetMinutes - 70),
    sunsetEnd: minutesToTime(sunsetMinutes + 20),
    sunrise,
    sunriseStart: minutesToTime(sunriseMinutes - 25),
    sunriseEnd: minutesToTime(sunriseMinutes + 55),
  }
}

function overlapsWindow(time: string | null, start: string, end: string, toleranceMinutes = 20): boolean {
  const value = time ? timeToMinutes(time) : null
  const startMinutes = timeToMinutes(start)
  const endMinutes = timeToMinutes(end)
  if (value === null || startMinutes === null || endMinutes === null) return false
  return value >= startMinutes - toleranceMinutes && value <= endMinutes + toleranceMinutes
}

function locationSeeds(data?: Partial<PlanningFormData>): string[] {
  const place = data?.city?.trim() || "目标地点"
  const text = planningConstraintText(data)
  if (/青岛|栈桥|灯塔|小青岛/.test(text)) return ["栈桥回澜阁西侧", "小青岛灯塔西向观景位", "青岛湾滨海步道", "鲁迅公园礁石外侧", "信号山公园俯拍位", "八大关临海道路"]
  if (/外滩/.test(text)) return ["外滩观景平台", "外滩源圆明园路口", "南京东路外滩入口步道", "外白渡桥北侧人行道", "黄浦江滨水平台"]
  if (/西湖/.test(text)) return ["断桥残雪北侧湖岸", "白堤中段临水步道", "曲院风荷荷塘边", "苏堤春晓林荫路段", "花港观鱼湖边平台", "长桥公园雷峰塔对景位"]
  if (/杭州/.test(text)) return ["西湖湖滨三公园", "北山街梧桐树影路段", "白堤临水步道", "苏堤林荫路段", "河坊街街口", "钱塘江城市阳台"]
  if (/长沙/.test(text)) return ["橘子洲头青年雕像东侧步道", "湘江风光带滨水平台", "岳麓山爱晚亭周边", "湖南大学老建筑街区", "IFS 国金中心街景点", "杜甫江阁夜景机位"]
  if (/大理|洱海/.test(text)) return ["才村码头湖边栈道", "龙龛码头日出平台", "磻溪 S 弯海岸线", "喜洲古镇转角巷口", "海舌公园外侧步道"]
  if (/故宫|北京/.test(text)) return ["景山万春亭", "故宫角楼护城河边", "东华门外侧红墙步道", "北海公园湖边", "什刹海银锭桥"]
  if (/连云港|花果山|连岛|海州湾|连云老街/.test(text)) {
    return [
      "花果山风景区游客中心外广场",
      "花果山九龙桥步道",
      "连岛大沙湾海岸木栈道",
      "苏马湾生态园海岸观景台",
      "连云老街石阶巷口",
      "海州湾跨海大桥远眺平台",
    ]
  }
  if (/威海|刘公岛|环海路|幸福门|火炬八街|那香海|国际海水浴场/.test(text)) {
    return [
      "威海幸福门海岸广场",
      "环海路猫头山二号观景台",
      "国际海水浴场西侧木栈道",
      "火炬八街坡顶海景路口",
      "刘公岛码头外侧海岸线",
      "那香海钻石沙滩西向观景位",
    ]
  }
  return [`POI 待确认：${place}中心地标外侧开阔处`, `POI 待确认：${place}公共滨水/公园步道`, `POI 待确认：${place}交通便利的高处观景位`]
}

function normalizeLocationCandidate(value: string): string[] {
  const withoutMeta = value
    .replace(/（评分[^）]*）|\(评分[^)]*\)/g, "")
    .replace(/（[^）]*(?:路线|方案|经济型|深度|轻松|全天|视觉|版本)[^）]*）/g, "")
    .replace(/^(方案\s*[A-ZＡ-Ｚ]?\s*[：:]\s*)/, "")
    .replace(/^\d{1,2}[:：]\d{2}\s*/, "")
    .replace(/^(转场[:：]\s*)/, "")
    .trim()

  return withoutMeta
    .split(/(?:×|->|→|、|，|,|；|;|\/|\||和|及|以及|还有)/)
    .map((item) =>
      item
        .replace(/(?:全天|半天)?(?:深度|轻松|沉浸|经典|核心|参考)?(?:路线|方案|线|版)$/g, "")
        .replace(/^.*?[：:]\s*/, "")
        .replace(/(?:入口|外侧|周边|附近|游客中心|公交站|风景区)$/g, (match) => match)
        .replace(/^(城市|目标城市|地点数据来自高德 POI[:：]?)/, "")
        .trim(),
    )
    .filter((item) => item.length >= 2)
    .filter((item) => !GENERIC_PLACE_PATTERN.test(item))
    .filter((item) => !isLikelyNonPlacePhrase(item))
    .filter((item) => !/午饭|午餐|晚饭|晚餐|美食|休息|天气|光线|预算|器材|风格|推荐理由|本地|人像|顺时针|逆时针|湖光|专项|主题/.test(item))
}

function locationCandidatesFromProviderItem(item: unknown): string[] {
  if (typeof item === "string") return normalizeLocationCandidate(item)
  if (!item || typeof item !== "object") return []
  const record = item as Record<string, unknown>
  return normalizeLocationCandidate(textValue(record.name ?? record.title ?? record.location ?? record.location_name ?? record.locationName))
}

function locationCandidatesFromProviderNote(note: string): string[] {
  if (!note) return []
  const match = note.match(/高德\s*POI[：:]\s*([^；;\n]+)/)
  return normalizeLocationCandidate(match?.[1] || "")
}

function locationCandidatesFromPlanRecord(plan: Record<string, unknown>): string[] {
  const title = textValue(plan.title)
  const routeSegment =
    title.includes("→") || title.includes("|")
      ? title.split(/[：:]/).at(-1) || title
      : title

  const shotList = plan.shot_list && typeof plan.shot_list === "object" ? (plan.shot_list as Record<string, unknown>) : {}
  const shotText = stringList(shotList.opening).concat(stringList(shotList.must_have)).join("；")

  return uniqueStrings([
    ...normalizeLocationCandidate(routeSegment),
    ...normalizeLocationCandidate(textValue(plan.location_name ?? plan.locationName)),
    ...normalizeLocationCandidate(textValue(plan.name)),
    ...normalizeLocationCandidate(shotText),
  ])
}

function locationCandidatesFromTimelineItem(item: unknown): string[] {
  if (typeof item !== "string") return []
  const arrowParts = item.split(/->|→/)
  if (arrowParts.length >= 2) return normalizeLocationCandidate(arrowParts[1])
  return normalizeLocationCandidate(item)
}

function locationCandidatesFromVisibleText(text: string): string[] {
  const candidates: string[] = []
  for (const match of text.matchAll(/\*\*\s*\d{1,2}[:：]\d{2}\s+([^*\n—-]{2,40})/g)) {
    candidates.push(...normalizeLocationCandidate(match[1]))
  }
  for (const match of text.matchAll(/(?:地点数据来自高德\s*POI[：:])([^；;\n]+)/g)) {
    candidates.push(...normalizeLocationCandidate(match[1]))
  }
  return uniqueStrings(candidates)
}

function providerLocationCandidates(payload?: Record<string, unknown>, visibleText = ""): string[] {
  const source = payload || {}
  const providerItems = arrayValue(payloadValue(source, "provider_place_candidates", "providerPlaceCandidates", "places"))
  const rawPlans = arrayValue(payloadValue(source, "plans", "plan_variants", "planVariants"))
  const rawTimeline = arrayValue(payloadValue(source, "execution_timeline", "executionTimeline", "timeline", "spots"))
  const providerNote = textValue(payloadValue(source, "provider_note", "providerNote"))

  return uniqueStrings([
    ...providerItems.flatMap(locationCandidatesFromProviderItem),
    ...rawPlans.flatMap((item) => (item && typeof item === "object" ? locationCandidatesFromPlanRecord(item as Record<string, unknown>) : [])),
    ...rawTimeline.flatMap(locationCandidatesFromTimelineItem),
    ...locationCandidatesFromProviderNote(providerNote),
    ...locationCandidatesFromVisibleText(visibleText),
  ]).slice(0, 12)
}

function rankProviderLocationsForIntent(locations: string[], data?: Partial<PlanningFormData>): string[] {
  const text = planningConstraintText(data)
  const wantsGarden = /园林|古典园林|苏州园林/.test(text)
  const wantsGate = /东方之门/.test(text)
  const wantsOldStreet = /老街|古城|古镇|平江路|山塘/.test(text)
  const wantsWaterfront = /海边|湖边|滨水|外滩|江边|河边|日落|落日/.test(text)
  return [...locations].sort((a, b) => {
    const score = (name: string) =>
      (wantsGate && /东方之门/.test(name) ? 120 : 0) +
      (wantsGarden && /拙政园|留园|狮子林|网师园|沧浪亭|园林/.test(name) ? 100 : 0) +
      (wantsOldStreet && /平江路|山塘街|老街|古镇/.test(name) ? 60 : 0) +
      (wantsWaterfront && /湖|江|河|海|湾|岸|桥/.test(name) ? 40 : 0)
    return score(b) - score(a)
  })
}

function mealLocationSeed(data?: Partial<PlanningFormData>): string {
  const text = planningConstraintText(data)
  if (/青岛|栈桥|灯塔|小青岛/.test(text)) return "中山路/栈桥周边经济午饭与休息点"
  if (/威海|刘公岛|环海路|幸福门|火炬八街|那香海|国际海水浴场/.test(text)) return "威高广场或幸福门周边午饭与休息点"
  if (/西湖|杭州/.test(text)) return "湖滨银泰/龙翔桥周边经济午饭"
  if (/外滩|上海/.test(text)) return "南京东路或外滩源周边简餐"
  if (/长沙/.test(text)) return "五一广场/坡子街周边经济午饭"
  if (/大理|洱海/.test(text)) return "才村或古城周边本地简餐"
  if (/北京|故宫/.test(text)) return "景山西街或东华门周边简餐"
  return "路线中段附近经济午饭与休息点"
}

function dinnerLocationSeed(data?: Partial<PlanningFormData>): string {
  const text = planningConstraintText(data)
  if (/青岛|栈桥|灯塔|小青岛/.test(text)) return "劈柴院/中山路周边晚饭与青岛本地小吃"
  if (/连云港|花果山|连岛|海州湾|连云老街/.test(text)) return "墟沟海鲜街或连岛游客中心周边晚饭"
  if (/威海|刘公岛|环海路|幸福门|火炬八街|那香海|国际海水浴场/.test(text)) return "韩乐坊夜市或威高广场周边海鲜晚饭"
  if (/长沙/.test(text)) return "坡子街/太平老街周边晚饭与本地小吃"
  if (/西湖|杭州/.test(text)) return "湖滨步行街/武林夜市周边晚饭"
  if (/外滩|上海/.test(text)) return "南京东路步行街周边晚饭"
  if (/大理|洱海/.test(text)) return "大理古城人民路周边晚饭"
  return "终点附近本地晚饭与休息点"
}

function localFoodAdvice(data?: Partial<PlanningFormData>): string {
  const text = planningConstraintText(data)
  if (/连云港|花果山|连岛|海州湾|连云老街/.test(text)) {
    return "本地美食建议：墟沟海鲜街或连岛游客中心周边；优先海鲜面、梭子蟹/皮皮虾、海蛎煎、紫菜包饭，人均约 60-120 元。"
  }
  if (/威海|刘公岛|环海路|幸福门|火炬八街|那香海|国际海水浴场/.test(text)) {
    return "本地美食建议：午饭可选威高广场/幸福门周边简餐；晚饭优先韩乐坊夜市或海鲜市场，推荐鲅鱼水饺、海鲜烧烤、海肠捞饭、扇贝和海胆，人均约 70-150 元。"
  }
  if (/青岛/.test(text)) return "本地美食建议：中山路/劈柴院周边；海鲜锅贴、鲅鱼水饺、辣炒蛤蜊，人均约 50-100 元。"
  if (/长沙/.test(text)) return "本地美食建议：坡子街/太平老街；臭豆腐、糖油粑粑、小龙虾或湘菜简餐，人均约 40-90 元。"
  if (/杭州|西湖/.test(text)) return "本地美食建议：湖滨/武林周边；片儿川、葱包桧、西湖醋鱼可选，人均约 50-120 元。"
  return "本地美食建议：选择终点机位附近评分较高、返程方便的本地餐饮区，人均预算按用户预算控制。"
}

function locationArea(location: string): string {
  const match = location.match(TRANSFER_KEYWORD_PATTERN)
  return match?.[0] || location.slice(0, 3)
}

function needsTransfer(prevTitle: string, nextTitle: string): boolean {
  if (!prevTitle || !nextTitle) return false
  if (/午饭|晚饭|餐|美食|休息|转场/.test(prevTitle + nextTitle)) return false
  const prevArea = locationArea(prevTitle)
  const nextArea = locationArea(nextTitle)
  return prevArea !== nextArea
}

function buildTransferSpot(prev: ReturnType<typeof mapSpot>, next: ReturnType<typeof mapSpot>) {
  const prevMinutes = timeToMinutes(prev.time)
  const nextMinutes = timeToMinutes(next.time)
  const transferTime =
    prevMinutes !== null && nextMinutes !== null
      ? minutesToTime(
          nextMinutes - prevMinutes > 12
            ? Math.min(nextMinutes - 5, Math.max(prevMinutes + 5, Math.round((prevMinutes + nextMinutes) / 2)))
            : Math.max(prevMinutes, nextMinutes - 1),
        )
      : prev.time
  return {
    time: transferTime,
    title: `转场：${prev.title} → ${next.title}`,
    description: "预留交通与整理时间，避免拍摄节点直接相连导致路线过赶。",
    position: "优先打车或公交直达，出发前确认导航时间和景区出入口。",
    lighting: "转场不作为主拍摄时段，可记录路途花絮。",
    method: "整理电量、存储卡和服装妆造，抵达后先踩点再拍摄。",
  }
}

function buildConcreteSpots(
  data: Partial<PlanningFormData> | undefined,
  visibleText: string,
  planIndex: number,
  providerLocations: string[] = [],
) {
  const constraints = parsePlanningConstraints(data)
  const times = timeSlotsForData(data)
  const startTime = extractStartTime(data)
  const endTime = extractEndTime(data)
  const golden = goldenWindow(data)
  const rankedProviderLocations = rankProviderLocationsForIntent(providerLocations, data)
  const providerBackedRequired = constraints.required_locations.flatMap((location) => {
    if (/园林类 POI/.test(location)) {
      return rankedProviderLocations.filter((candidate) => /拙政园|留园|狮子林|网师园|沧浪亭|园林/.test(candidate)).slice(0, 2)
    }
    const matched = rankedProviderLocations.find((candidate) => candidate.includes(location) || location.includes(candidate))
    return matched ? [matched] : [location]
  })
  const seededLocations = uniqueStrings([
    ...providerBackedRequired,
    ...rankedProviderLocations,
    ...locationSeeds(data),
  ])
  const locations = seededLocations.filter((location) => !constraints.excluded_locations.some((excluded) => location.includes(excluded) || excluded.includes(location)))
  const requiredLocationSet = new Set(providerBackedRequired)
  const requiredRouteLocations = locations.filter((location) => requiredLocationSet.has(location))
  const optionalRouteLocations = locations.filter((location) => !requiredLocationSet.has(location))
  const optionalOffset = optionalRouteLocations.length
    ? (planIndex * Math.max(1, Math.ceil(optionalRouteLocations.length / 2))) % optionalRouteLocations.length
    : 0
  const rotatedOptionalLocations = optionalRouteLocations.length
    ? [...optionalRouteLocations.slice(optionalOffset), ...optionalRouteLocations.slice(0, optionalOffset)]
    : []
  const routeLocations = uniqueStrings([...requiredRouteLocations, ...rotatedOptionalLocations])
  const subject = data?.subject || "拍摄主题"
  const gear = data?.equipment || "现有器材"
  const detailRequested = wantsDetailedRoute(data)
  const fullDay = wantsFullDay(data)
  const planOffset = planIndex % 2
  const includeLunch = constraints.required_meals.lunch
  const includeDinner = constraints.required_meals.dinner
  const lunchTime = constraints.required_meals.lunch_time
  const dinnerConflictsWithSunset = constraints.shooting_goals.includes("落日/黄金时刻") && overlapsWindow(constraints.required_meals.dinner_time, golden.sunsetStart, golden.sunsetEnd)
  const dinnerTime = dinnerConflictsWithSunset
    ? minutesToTime((timeToMinutes(golden.sunsetEnd) ?? 19 * 60) + 30)
    : constraints.required_meals.dinner_time
  const desiredCount = fullDay ? (constraints.route_pace === "relaxed" ? 6 : 7) : detailRequested ? 5 : 3
  const mealCount = Number(includeLunch) + Number(includeDinner)
  const photoSpotCount = Math.min(Math.max(3, desiredCount - mealCount), routeLocations.length)

  const photoTimes = startTime && endTime ? distributeTimeSlots(startTime, endTime, photoSpotCount) : times
  const lunchMinutes = lunchTime ? timeToMinutes(lunchTime) : null
  const dinnerMinutes = dinnerTime ? timeToMinutes(dinnerTime) : null
  const adjustedPhotoTimes = photoTimes.map((time, index) => {
    const minutes = timeToMinutes(time)
    if (minutes === null) return time
    if (lunchMinutes !== null && Math.abs(minutes - lunchMinutes) <= 35) {
      return minutesToTime(minutes + (index % 2 === 0 ? -45 : 45))
    }
    if (dinnerMinutes !== null && Math.abs(minutes - dinnerMinutes) <= 45) {
      return minutesToTime(minutes - 60)
    }
    return time
  })
  const photoSpots = routeLocations.slice(0, photoSpotCount).map((location, index) => {
    const isSunsetSpot = constraints.shooting_goals.includes("落日/黄金时刻") && index === photoSpotCount - 1
    const isSunriseSpot = constraints.shooting_goals.includes("日出") && index === 0
    return {
      time: isSunsetSpot ? golden.sunsetStart : isSunriseSpot ? golden.sunriseStart : adjustedPhotoTimes[(index + planOffset) % adjustedPhotoTimes.length],
      title: location,
      description:
        isSunsetSpot
          ? `落日专项机位，围绕 ${golden.sunsetStart}-${golden.sunsetEnd} 的黄金时刻安排，不与晚饭节点冲突。`
          : isSunriseSpot
            ? `日出专项机位，围绕 ${golden.sunriseStart}-${golden.sunriseEnd} 安排，提前到位确认安全站位。`
            : index === 0
              ? `按用户要求从这里开始，先建立${subject}的环境关系，确认人流、背景和安全站位。`
            : index === 1
                ? `补充主体与地标的中近景组合，避开游客密集方向，并形成第二组画面。`
                : `继续推进路线，补足环境、人物互动和局部细节，避免整组照片只有单一景别。`,
      position:
        isSunsetSpot
          ? `选择${location}面向西侧或开阔海面/天际线的位置，预留人物轮廓和前景层次`
          : index === 0
            ? `站在${location}外侧开阔处，预留前景和主体活动空间`
            : index === 1
              ? `沿${location}侧边移动 10-20 米，寻找干净背景和引导线`
              : `选择${location}附近较高或较低机位，压缩杂乱背景`,
      lighting: isSunsetSpot
        ? `落日前约 70 分钟到落后 20 分钟，优先侧逆光、剪影和暖色天空`
        : data?.timePreference
          ? `${data.timePreference}侧逆光优先，避开直射硬光`
          : "优先侧光、逆光或蓝调时刻，现场按云量微调",
      method: `${gear}分工执行：广角交代环境，中长焦压缩主体；先拍全景，再拍半身与细节。${visibleText ? "" : ""}`,
    }
  })

  const withLunch = includeLunch
    ? [
        ...photoSpots.slice(0, Math.max(2, Math.floor(photoSpots.length / 2))),
        {
          time: lunchTime || "12:00",
          title: mealLocationSeed(data),
          description: "午间补给与休息节点，避开正午硬光，同时满足用户提出的经济实惠午饭需求。",
          position: "选择距离上一机位步行或地铁可达、翻台快且预算友好的餐饮区域",
          lighting: "正午硬光不作为主拍摄时段，可顺手拍环境记录或休息整理素材",
          method: "安排 45-60 分钟用餐与补水，顺便检查电量、存储卡和下一段路线。",
        },
        ...photoSpots.slice(Math.max(2, Math.floor(photoSpots.length / 2))),
      ]
    : photoSpots

  const withDinner = includeDinner
    ? [
        ...withLunch,
        {
          time: dinnerTime || "18:30",
          title: dinnerLocationSeed(data),
          description: dinnerConflictsWithSunset
            ? `用户要求晚饭与落日窗口冲突，已顺延到 ${dinnerTime}，先完成落日拍摄再用餐。${localFoodAdvice(data)}`
            : `晚饭与本地美食节点，承接傍晚到夜间拍摄前后的体力恢复，也满足用户提出的当地美食推荐需求。${localFoodAdvice(data)}`,
          position: "选择靠近夜景机位或返程交通的餐饮区域，避免为吃饭大幅绕路",
          lighting: "可顺手记录街景、灯牌和人文氛围，不作为高强度主拍摄节点",
          method: "安排 60 分钟用餐与休息，整理当天素材，准备夜景或返程。",
        },
      ]
    : withLunch

  const sorted = [...withDinner].sort((a, b) => (timeToMinutes(a.time) ?? 0) - (timeToMinutes(b.time) ?? 0))
  return sorted.flatMap((spot, index) => {
    const next = sorted[index + 1]
    if (!next || !needsTransfer(spot.title, next.title)) return [spot]
    return [spot, buildTransferSpot(spot, next)]
  })
}

function normalizeSpots(
  spots: ReturnType<typeof mapSpot>[],
  data: Partial<PlanningFormData> | undefined,
  visibleText: string,
  planIndex: number,
  providerLocations: string[] = [],
) {
  const constraints = parsePlanningConstraints(data)
  const golden = goldenWindow(data)
  const userAllowsLunch = constraints.required_meals.lunch
  const userAllowsDinner = constraints.required_meals.dinner
  const filteredSpots = spots.filter((spot) => {
    const text = `${spot.title} ${spot.description} ${spot.position} ${spot.method}`
    const lunchLike = /午饭|午餐|中饭|经济午饭|简餐/.test(text)
    const dinnerLike = /晚饭|晚餐|夜饭|美食|小吃|夜市/.test(text)
    if (lunchLike && !userAllowsLunch) return false
    if (dinnerLike && !userAllowsDinner) return false
    return true
  })
  const startMinutes = extractStartTime(data) ? timeToMinutes(extractStartTime(data) || "") : null
  const endMinutes = extractEndTime(data) ? timeToMinutes(extractEndTime(data) || "") : null
  const hasTimeViolation = filteredSpots.some((spot) => {
    const spotMinutes = timeToMinutes(spot.time)
    if (spotMinutes === null) return false
    if (startMinutes !== null && spotMinutes < startMinutes) return true
    if (endMinutes !== null && spotMinutes > endMinutes) return true
    return false
  })
  const lunchSpot = filteredSpots.find((spot) => /午饭|午餐|中饭|吃饭|用餐|餐饮|简餐|休息/.test(`${spot.title} ${spot.description} ${spot.method}`))
  const dinnerSpot = filteredSpots.find((spot) => /晚饭|晚餐|夜饭|美食|小吃|夜市/.test(`${spot.title} ${spot.description} ${spot.method}`))
  const expectedLunchTime = extractLunchTime(data)
  const expectedDinnerTime = extractDinnerTime(data)
  const lunchMinutes = expectedLunchTime ? timeToMinutes(expectedLunchTime) : null
  const dinnerMinutes = expectedDinnerTime ? timeToMinutes(expectedDinnerTime) : null
  const actualLunchMinutes = lunchSpot ? timeToMinutes(lunchSpot.time) : null
  const actualDinnerMinutes = dinnerSpot ? timeToMinutes(dinnerSpot.time) : null
  const hasMealViolation =
    wantsLunchNode(data) &&
    (!lunchSpot || (lunchMinutes !== null && actualLunchMinutes !== null && Math.abs(actualLunchMinutes - lunchMinutes) > 75))
  const hasDinnerViolation =
    wantsDinnerNode(data) &&
    (!dinnerSpot || (dinnerMinutes !== null && actualDinnerMinutes !== null && Math.abs(actualDinnerMinutes - dinnerMinutes) > 90))
  const hasMealCollision =
    Boolean(lunchSpot && dinnerSpot && lunchSpot !== dinnerSpot && lunchSpot.time === dinnerSpot.time) ||
    Boolean(actualDinnerMinutes !== null && actualDinnerMinutes < 16 * 60 && wantsDinnerNode(data))
  const sunsetSpot = filteredSpots.find((spot) => /日落|落日|晚霞|黄金时刻|剪影/.test(`${spot.title} ${spot.description} ${spot.lighting} ${spot.method}`))
  const sunsetSpotTime = sunsetSpot ? timeToMinutes(sunsetSpot.time) : null
  const sunsetStart = timeToMinutes(golden.sunsetStart)
  const sunsetEnd = timeToMinutes(golden.sunsetEnd)
  const hasSunsetViolation =
    constraints.shooting_goals.includes("落日/黄金时刻") &&
    (!sunsetSpot ||
      sunsetSpotTime === null ||
      sunsetStart === null ||
      sunsetEnd === null ||
      sunsetSpotTime < sunsetStart - 20 ||
      sunsetSpotTime > sunsetEnd + 20)
  const hasDinnerSunsetConflict =
    constraints.shooting_goals.includes("落日/黄金时刻") &&
    wantsDinnerNode(data) &&
    overlapsWindow(expectedDinnerTime, golden.sunsetStart, golden.sunsetEnd)
  const spanTooShort = wantsFullDay(data) && (() => {
    const start = extractStartTime(data)
    const end = extractEndTime(data)
    if (!start || !end || filteredSpots.length < 2) return false
    const ordered = [...filteredSpots].sort((a, b) => (timeToMinutes(a.time) ?? 0) - (timeToMinutes(b.time) ?? 0))
    const first = timeToMinutes(ordered[0]?.time || "")
    const last = timeToMinutes(ordered[ordered.length - 1]?.time || "")
    const startMinutes = timeToMinutes(start)
    const endMinutes = timeToMinutes(end)
    if (first === null || last === null || startMinutes === null || endMinutes === null) return false
    return first > startMinutes + 30 || last < endMinutes - 60
  })()
  const planText = filteredSpots.map((spot) => `${spot.title} ${spot.description} ${spot.position} ${spot.method}`).join(" ")
  const missingRequiredLocations = constraints.required_locations.some((location) => !planText.includes(location))
  const includesExcludedLocations = constraints.excluded_locations.some((location) => planText.includes(location))
  const tooFewForUserPace =
    constraints.route_pace === "relaxed"
      ? wantsFullDay(data) && filteredSpots.length < 4
      : wantsFullDay(data) && filteredSpots.length < 5
  const tooFewForCoreRoute =
    (constraints.shooting_goals.length > 0 || wantsMealNode(data) || /游玩|路线|方案|规划/.test(planningConstraintText(data))) &&
    filteredSpots.length < 3
  const tooFewForMealSunsetRoute =
    constraints.shooting_goals.includes("落日/黄金时刻") &&
    wantsLunchNode(data) &&
    wantsDinnerNode(data) &&
    filteredSpots.length < 5

  if (!filteredSpots.length || filteredSpots.some(isGenericSpot) || hasTimeViolation || hasMealViolation || hasDinnerViolation || hasMealCollision || hasSunsetViolation || hasDinnerSunsetConflict || spanTooShort || missingRequiredLocations || includesExcludedLocations || tooFewForUserPace || tooFewForCoreRoute || tooFewForMealSunsetRoute || (wantsDetailedRoute(data) && filteredSpots.length < 4)) {
    return buildConcreteSpots(data, visibleText, planIndex, providerLocations)
  }
  return filteredSpots.sort((a, b) => (timeToMinutes(a.time) ?? 0) - (timeToMinutes(b.time) ?? 0))
}

function validatePlanFeasibility(plan: PlanResult, data?: Partial<PlanningFormData> | null): string[] {
  const constraints = parsePlanningConstraints(data || undefined)
  const warnings: string[] = []
  const golden = goldenWindow(data || undefined)
  const planText = plan.spots.map((spot) => `${spot.title} ${spot.description} ${spot.position} ${spot.lighting} ${spot.method}`).join(" ")
  const startMinutes = constraints.start_time ? timeToMinutes(constraints.start_time) : null
  const endMinutes = constraints.end_time ? timeToMinutes(constraints.end_time) : null

  if (startMinutes !== null && plan.spots.some((spot) => (timeToMinutes(spot.time) ?? startMinutes) < startMinutes)) {
    warnings.push(`存在早于用户开始时间 ${constraints.start_time} 的节点`)
  }
  if (endMinutes !== null && plan.spots.some((spot) => (timeToMinutes(spot.time) ?? endMinutes) > endMinutes)) {
    warnings.push(`存在晚于用户结束时间 ${constraints.end_time} 的节点`)
  }
  const missingLocations = constraints.required_locations.filter((location) => !planText.includes(location))
  if (missingLocations.length) warnings.push(`缺少用户指定地点：${missingLocations.join("、")}`)

  const excludedHits = constraints.excluded_locations.filter((location) => planText.includes(location))
  if (excludedHits.length) warnings.push(`包含用户要求避开的地点：${excludedHits.join("、")}`)

  if (constraints.shooting_goals.includes("落日/黄金时刻")) {
    const sunsetSpot = plan.spots.find((spot) => /日落|落日|晚霞|黄金时刻|剪影/.test(`${spot.title} ${spot.description} ${spot.lighting} ${spot.method}`))
    const sunsetMinutes = sunsetSpot ? timeToMinutes(sunsetSpot.time) : null
    const start = timeToMinutes(golden.sunsetStart)
    const end = timeToMinutes(golden.sunsetEnd)
    if (!sunsetSpot || sunsetMinutes === null || start === null || end === null || sunsetMinutes < start - 20 || sunsetMinutes > end + 20) {
      warnings.push(`落日目标未落在建议窗口 ${golden.sunsetStart}-${golden.sunsetEnd}`)
    }
    if (constraints.required_meals.dinner && overlapsWindow(constraints.required_meals.dinner_time, golden.sunsetStart, golden.sunsetEnd)) {
      warnings.push(`晚饭时间与落日黄金时刻冲突，已建议顺延到落日后`)
    }
  }

  if (plan.spots.some((spot) => GENERIC_PLACE_PATTERN.test(spot.title) || !isConcreteSpotTitle(spot.title))) {
    warnings.push("部分地点仍需现场确认或等待 provider 返回更具体 POI")
  }

  const hasTransfer = plan.spots.some((spot) => spot.title.startsWith("转场："))
  const distinctAreas = new Set(plan.spots.filter((spot) => !/午饭|晚饭|餐|美食|休息|转场/.test(spot.title)).map((spot) => locationArea(spot.title)))
  if (distinctAreas.size >= 2 && !hasTransfer) warnings.push("跨区域路线缺少明确转场时间")

  return warnings
}

function withRouteValidation(plans: PlanResult[], data?: Partial<PlanningFormData> | null): PlanResult[] {
  return plans.map((plan) => {
    const warnings = validatePlanFeasibility(plan, data)
    const info = plan.info.filter((item) => item.label !== "方案校验")
    const constraints = parsePlanningConstraints(data || undefined)
    const shouldAddFoodAdvice = constraints.special_goals.includes("包含当地美食建议") && !info.some((item) => item.label === "本地美食建议")
    return {
      ...plan,
      info: [
        ...info,
        ...(shouldAddFoodAdvice
          ? [
              {
                label: "本地美食建议",
                value: localFoodAdvice(data || undefined),
              },
            ]
          : []),
        {
          label: "方案校验",
          value: warnings.length ? `需注意：${warnings.join("；")}` : "通过：时间范围、餐饮节点、黄金时刻和转场安排未发现明显冲突。",
        },
      ],
    }
  })
}

function infoFromPayload(payload: Record<string, unknown>, visibleText: string): PlanResult["info"] {
  const providerNote = textValue(payload.provider_note ?? payload.providerNote)
  const styleHandoff = textValue(payload.style_handoff ?? payload.styleHandoff)
  const brief = textValue(payload.brief)

  return [
    {
      label: "推荐理由",
      value: brief || textValue(payload.summary, "根据城市、日期、题材和器材生成可执行拍摄路线。"),
    },
    {
      label: "器材建议",
      value: stringList(payload.gear_advice ?? payload.gearAdvice).join("；") || "按现有器材优先轻装执行，广角负责环境，中长焦负责主体压缩。",
    },
    {
      label: "天气与光线提醒",
      value: providerNote || "实时天气暂不可用，已基于通用拍摄经验生成参考方案；出发前请再次确认天气和开放时间。",
    },
    {
      label: "后期风格目标",
      value: styleHandoff || visibleText.slice(0, 120) || "围绕目标风格保留光线氛围，后期再细调色温、对比和高光层次。",
    },
  ]
}

function planFromVisibleText(result: AgentResultResponse): PlanResult[] {
  return [
    {
      id: "A",
      name: "方案 A",
      title: result.summary || "方案 A：参考拍摄路线",
      spots: [
        {
          time: "日出/黄金时刻",
          title: "核心拍摄点",
          description: result.visibleText.slice(0, 90) || "PlanAgent 已生成文本方案，当前按通用时间线展示。",
          position: "以用户输入地点为中心选择安全开阔机位",
          lighting: "优先选择侧光、逆光或蓝调时刻",
          method: "先拍环境建立氛围，再拍主体和局部细节",
        },
      ],
      info: infoFromPayload(result.structuredPayload, result.visibleText),
    },
  ]
}

function fallbackPlanFromConstraints(
  result: AgentResultResponse,
  formData: Partial<PlanningFormData>,
  index: number,
  providerLocations: string[] = [],
): PlanResult {
  const letter = String.fromCharCode(65 + index)
  const text = planningConstraintText(formData)
  const hasWaterfrontGoal = /海边|海岸|湖边|江边|河边|滨水|外滩|日落|落日/.test(text)
  const routeNames = hasWaterfrontGoal
    ? ["滨水/落日与美食线", "人文轻松线", "备选雨天与室内线"]
    : ["核心景点与美食线", "人文轻松线", "备选雨天与室内线"]
  return {
    id: letter,
    name: `方案 ${letter}`,
    title: `方案 ${letter}：${formData.city || "目标城市"}${routeNames[index] || "可执行路线"}`,
    spots: buildConcreteSpots(formData, result.visibleText, index, providerLocations),
    info: infoFromPayload(result.structuredPayload || {}, result.visibleText),
  }
}

function routeSignature(plan: PlanResult): string {
  return plan.spots
    .filter((spot) => !/午饭|午餐|晚饭|晚餐|美食|用餐|餐饮|休息|转场/.test(spot.title))
    .map((spot) => spot.title.replace(/^POI 待确认：/, "").trim())
    .filter(Boolean)
    .slice(0, 5)
    .join("|")
}

function routesTooSimilar(a: PlanResult, b: PlanResult): boolean {
  const aTitles = routeSignature(a).split("|").filter(Boolean)
  const bTitles = routeSignature(b).split("|").filter(Boolean)
  if (!aTitles.length || !bTitles.length) return false
  const overlap = aTitles.filter((title) => bTitles.includes(title)).length
  const ratio = overlap / Math.min(aTitles.length, bTitles.length)
  const sameFirstTwo =
    aTitles.slice(0, 2).join("|") === bTitles.slice(0, 2).join("|") &&
    aTitles.length >= 2 &&
    bTitles.length >= 2
  return ratio >= 0.8 || sameFirstTwo
}

function ensurePlanVariants(plans: PlanResult[], result: AgentResultResponse, formData?: Partial<PlanningFormData> | null): PlanResult[] {
  const validated = withRouteValidation(plans, formData)
  if (!formData) return validated

  const providerLocations = providerLocationCandidates(result.structuredPayload || {}, result.visibleText)
  const distinctPlans = validated.map((plan, index, allPlans) => {
    const isDuplicate = allPlans.slice(0, index).some((previous) => routesTooSimilar(previous, plan))
    return isDuplicate ? fallbackPlanFromConstraints(result, formData, index, providerLocations) : plan
  })

  while (distinctPlans.length < 2) {
    distinctPlans.push(fallbackPlanFromConstraints(result, formData, distinctPlans.length, providerLocations))
  }

  return withRouteValidation(distinctPlans, formData)
}

function mapPlanResult(result?: AgentResultResponse, formData?: Partial<PlanningFormData> | null): PlanResult[] {
  if (!result || result.status === "failed") return mockPlanningPagePlans
  const payload = result.structuredPayload || {}
  const providerLocations = providerLocationCandidates(payload, result.visibleText)
  const rawPlans = arrayValue(payloadValue(payload, "plans", "plan_variants", "planVariants"))
  const rawTimeline = arrayValue(payloadValue(payload, "execution_timeline", "executionTimeline", "timeline", "spots"))

  if (rawPlans.length) {
    return ensurePlanVariants(rawPlans.slice(0, 3).map((rawPlan, index) => {
      const plan = rawPlan && typeof rawPlan === "object" ? (rawPlan as Record<string, unknown>) : {}
      const spotsSource = arrayValue(plan.spots ?? plan.timeline ?? plan.execution_timeline)
      return {
        id: textValue(plan.id, String.fromCharCode(65 + index)),
        name: textValue(plan.name, `方案 ${String.fromCharCode(65 + index)}`),
        title: textValue(plan.title, `方案 ${String.fromCharCode(65 + index)}：可执行拍摄路线`),
        spots: normalizeSpots((spotsSource.length ? spotsSource : rawTimeline).map(mapSpot), formData || undefined, result.visibleText, index, providerLocations),
        info: infoFromPayload({ ...payload, ...plan }, result.visibleText),
      }
    }), result, formData)
  }

  if (rawTimeline.length) {
    return ensurePlanVariants([
      {
        id: "A",
        name: "方案 A",
        title: result.summary || "方案 A：可执行拍摄路线",
        spots: normalizeSpots(rawTimeline.map(mapSpot), formData || undefined, result.visibleText, 0, providerLocations),
        info: infoFromPayload(payload, result.visibleText),
      },
    ], result, formData)
  }

  if (formData) {
    return withRouteValidation([
      fallbackPlanFromConstraints(result, formData, 0, providerLocations),
      fallbackPlanFromConstraints(result, formData, 1, providerLocations),
    ], formData)
  }

  return withRouteValidation(planFromVisibleText(result), formData)
}

function buildUserGoal(data: PlanningFormData): string {
  const constraints = parsePlanningConstraints(data)
  const base = [
    data.date ? `${data.date}` : "",
    data.city ? `在${data.city}` : "",
    data.subject ? `拍${data.subject}` : "拍摄",
    data.timePreference ? `，偏好${data.timePreference}` : "",
    data.equipment ? `，器材${data.equipment}` : "",
    data.budget ? `，预算${data.budget}` : "",
    data.requirements ? `，其他要求：${data.requirements}` : "",
  ].join("")

  const hardConstraints = [
    "用户写在“其他要求”里的内容优先级最高，必须先满足，再考虑系统默认补全",
    constraints.start_time ? `必须从 ${constraints.start_time} 或更晚开始，不能安排早于该时间的机位` : "",
    constraints.end_time ? `必须在 ${constraints.end_time} 或更早结束，不能安排晚于该时间的机位` : "",
    constraints.required_locations.length ? `必须包含这些用户指定地点/机位：${constraints.required_locations.join("、")}` : "",
    constraints.excluded_locations.length ? `必须避开这些地点/场景：${constraints.excluded_locations.join("、")}` : "",
    constraints.shooting_goals.length ? `拍摄目标：${constraints.shooting_goals.join("、")}；其中落日/黄金时刻建议窗口为 ${goldenWindow(data).sunsetStart}-${goldenWindow(data).sunsetEnd}，不能把“落日”当作上午地点` : "",
    wantsFullDay(data) ? "用户要求全天/玩一天，请覆盖上午、午后、下午、傍晚等完整白天节奏，每套方案至少 5 个时间节点" : "",
    constraints.required_meals.lunch ? `必须加入午饭/餐饮/休息节点，时间建议为 ${constraints.required_meals.lunch_time || "12:00"}，且说明位置、预算和休息目的` : "用户未明确要求午饭时，不要把午饭作为硬性节点",
    constraints.required_meals.dinner ? `必须加入晚饭/当地美食节点，时间建议为 ${constraints.required_meals.dinner_time || "18:30"}，且说明本地美食、位置和返程便利性；如果与落日窗口冲突，先保留落日拍摄，晚饭顺延到落日后` : "用户未明确要求晚饭/美食时，不要把晚饭作为硬性节点",
    constraints.route_pace !== "normal" ? `路线节奏：${constraints.route_pace === "relaxed" ? "轻松，不要太赶，控制步行和换点频率" : "紧凑，提高拍摄覆盖效率"}` : "",
    constraints.traffic_preferences.length ? `交通偏好：${constraints.traffic_preferences.join("、")}` : "",
    constraints.style_preferences.length ? `风格偏好：${constraints.style_preferences.join("、")}` : "",
    constraints.special_goals.length ? `特殊目标：${constraints.special_goals.join("、")}` : "",
    data.requirements ? `必须优先满足其他要求：${data.requirements}` : "",
  ].filter(Boolean).join("；")

  return `${base}。${hardConstraints ? `硬性约束：${hardConstraints}。` : ""}请生成 2-3 套可执行拍摄方案，并把每套方案的具体机位名称、站位、时间、光线、拍法、器材分工、跨区域转场时间、餐饮休息和备选路线写清楚；不要只写“推荐机位 1/2”，不要把“落日/日出/蓝调/夜景”当成地点标题，不要忽略用户写在“其他要求”里的时间、地点、午饭、晚饭和当地美食安排。`
}

function validateForm(data: PlanningFormData): string | null {
  if (!data.city.trim()) return "请先填写城市。"
  if (!data.date.trim()) return "请先选择拍摄日期。"
  if (!data.subject.trim()) return "请先选择题材。"
  return null
}

function inferPlanningDataFromResult(result: AgentResultResponse): Partial<PlanningFormData> {
  const payload = result.structuredPayload || {}
  const text = [
    result.summary,
    result.visibleText,
    textValue(payload.provider_note ?? payload.providerNote),
    textValue(payload.brief),
  ].join(" ")

  const city =
    textValue(payload.city) ||
    (text.includes("外滩") ? "外滩" : "") ||
    (text.includes("西湖") ? "西湖" : "") ||
    (/大理|洱海/.test(text) ? "大理" : "") ||
    (/故宫|北京/.test(text) ? "北京" : "")

  return {
    city,
    timePreference: /全天|09:00|17:00|白天/.test(text) ? "整个白天" : text.includes("日落") ? "日落" : text.includes("日出") ? "日出" : text.includes("夜") ? "夜景" : "",
    subject: text.includes("人像") ? "风光人像" : text.includes("街拍") ? "古城街拍" : "风光人像",
    equipment: text.includes("长焦") ? "广角 + 长焦" : "",
    requirements: [
      /09:00|17:00/.test(text) ? "09:00-17:00 全天执行" : "",
      /午饭|午餐|餐饮|经济实惠/.test(text) ? "包含11:30-12:30经济实惠午饭节点" : "",
      /晚饭|晚餐|美食|小吃/.test(text) ? "包含晚饭和当地美食节点" : "",
      "从历史结果恢复，若结构化机位不足则补全具体站位。",
    ].filter(Boolean).join("；"),
  }
}

function noticeClass(kind: PlanningNoticeKind): string {
  if (kind === "success") return "border-green-200 bg-green-50 text-green-700"
  if (kind === "warning") return "border-amber-200 bg-amber-50 text-amber-700"
  if (kind === "error") return "border-red-200 bg-red-50 text-red-700"
  return "border-blue-200 bg-blue-50 text-blue-700"
}

function ConstraintSummaryCard({ data }: { data?: Partial<PlanningFormData> | null }) {
  if (!data?.city && !data?.requirements && !data?.timePreference && !data?.subject) return null
  const constraints = parsePlanningConstraints(data)
  const items = [
    data.city ? `城市：${data.city}` : "",
    data.date ? `日期：${data.date}` : "",
    data.timePreference ? `时段：${data.timePreference}` : "",
    data.subject ? `题材：${data.subject}` : "",
    constraints.start_time || constraints.end_time
      ? `时间：${constraints.start_time || "未指定开始"} - ${constraints.end_time || "未指定结束"}`
      : "",
    constraints.required_locations.length ? `必须包含：${constraints.required_locations.join("、")}` : "",
    constraints.shooting_goals.length ? `拍摄目标：${constraints.shooting_goals.join("、")}` : "",
    constraints.excluded_locations.length ? `必须避开：${constraints.excluded_locations.join("、")}` : "",
    constraints.required_meals.lunch || constraints.required_meals.dinner
      ? `餐饮：${[
          constraints.required_meals.lunch ? `午饭${constraints.required_meals.lunch_time ? ` ${constraints.required_meals.lunch_time}` : ""}` : "",
          constraints.required_meals.dinner ? `晚饭/美食${constraints.required_meals.dinner_time ? ` ${constraints.required_meals.dinner_time}` : ""}` : "",
        ].filter(Boolean).join("；")}`
      : "餐饮：未明确要求，不作为硬性节点",
    constraints.route_pace !== "normal" ? `节奏：${constraints.route_pace === "relaxed" ? "轻松" : "紧凑"}` : "",
    constraints.traffic_preferences.length ? `交通：${constraints.traffic_preferences.join("、")}` : "",
    constraints.style_preferences.length ? `风格：${constraints.style_preferences.join("、")}` : "",
    constraints.special_goals.length ? `特殊目标：${constraints.special_goals.join("、")}` : "",
  ].filter(Boolean)

  return (
    <div className="rounded-[10px] border border-blue-100 bg-blue-50/60 px-4 py-3 text-sm text-slate-700">
      <p className="mb-2 font-extrabold text-slate-900">已识别用户要求</p>
      <div className="flex flex-wrap gap-2">
        {items.map((item) => (
          <span key={item} className="rounded-full border border-blue-200 bg-white px-3 py-1 text-xs font-bold text-slate-700">
            {item}
          </span>
        ))}
      </div>
    </div>
  )
}

function escapeHtml(value: string) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;")
}

function getPlanInfo(plan: PlanResult, label: string) {
  return plan.info.find((item) => item.label === label)?.value || ""
}

function buildPlanActionPayload(plan: PlanResult, data?: Partial<PlanningFormData> | null, jobId?: string | null) {
  return {
    plan_id: plan.id,
    plan_name: plan.name,
    title: plan.title,
    source_job_id: jobId || null,
    city: data?.city || "",
    date: data?.date || "",
    subject: data?.subject || "",
    equipment: data?.equipment || "",
    budget: data?.budget || "",
    requirements: data?.requirements || "",
    spots: plan.spots,
    info: plan.info,
    adopted_at: new Date().toISOString(),
  }
}

function buildPresetText(plan: PlanResult, data?: Partial<PlanningFormData> | null) {
  const styleTarget = getPlanInfo(plan, "后期风格目标")
  const lighting = getPlanInfo(plan, "天气与光线提醒")
  const routeTone = plan.spots
    .slice(0, 3)
    .map((spot) => `${spot.time} ${spot.title}：${spot.lighting}`)
    .join("；")

  return [
    `后期预设草稿｜${plan.name} ${plan.title}`,
    data?.subject ? `适用题材：${data.subject}` : "",
    data?.city ? `拍摄地：${data.city}` : "",
    styleTarget ? `风格目标：${styleTarget}` : "风格目标：保留现场光线氛围，控制高光与阴影层次。",
    lighting ? `光线依据：${lighting}` : "",
    routeTone ? `关键场景：${routeTone}` : "",
    "建议参数区间：",
    "- 曝光：按现场亮度微调，优先保留高光层次。",
    "- 高光：建议降低 -40 ~ -15，用于压回天空、水面或灯光细节。",
    "- 阴影：建议 +5 ~ +25，避免暗部死黑，但保留氛围。",
    "- 色温：按风格微调；暖色氛围 +200K ~ +600K，清冷风格 -200K ~ -500K。",
    "- 自然饱和度：+5 ~ +18，避免肤色和天空过饱和。",
    "- 清晰度/纹理：+5 ~ +15，增强建筑、山体或街景细节。",
  ].filter(Boolean).join("\n")
}

function buildPlanReportHtml(plan: PlanResult, data?: Partial<PlanningFormData> | null, jobId?: string | null) {
  const rows = plan.spots
    .map((spot, index) => `
      <tr>
        <td>${index + 1}</td>
        <td>${escapeHtml(spot.time)}</td>
        <td><strong>${escapeHtml(spot.title)}</strong><br />${escapeHtml(spot.description)}</td>
        <td>${escapeHtml(spot.position)}</td>
        <td>${escapeHtml(spot.lighting)}</td>
        <td>${escapeHtml(spot.method)}</td>
      </tr>
    `)
    .join("")
  const infoRows = plan.info
    .map((item) => `<p><strong>${escapeHtml(item.label)}：</strong>${escapeHtml(item.value)}</p>`)
    .join("")

  return `<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <title>${escapeHtml(plan.name)} - PhotoAI 拍摄规划报告</title>
  <style>
    body { font-family: Arial, "Microsoft YaHei", sans-serif; color: #0f172a; padding: 28px; }
    h1 { font-size: 24px; margin-bottom: 8px; }
    .meta { color: #475569; margin-bottom: 20px; line-height: 1.7; }
    table { width: 100%; border-collapse: collapse; margin: 18px 0; }
    th, td { border: 1px solid #cbd5e1; padding: 10px; text-align: left; vertical-align: top; font-size: 13px; }
    th { background: #f1f5f9; }
    .info { border: 1px solid #cbd5e1; padding: 14px; border-radius: 8px; }
    @media print { button { display: none; } body { padding: 0; } }
  </style>
</head>
<body>
  <button onclick="window.print()">打印 / 另存为 PDF</button>
  <h1>${escapeHtml(plan.name)}：${escapeHtml(plan.title)}</h1>
  <div class="meta">
    <div>来源任务：${escapeHtml(jobId || "未关联任务")}</div>
    <div>城市：${escapeHtml(data?.city || "未填写")}　日期：${escapeHtml(data?.date || "未填写")}　题材：${escapeHtml(data?.subject || "未填写")}</div>
    <div>器材：${escapeHtml(data?.equipment || "未填写")}　预算：${escapeHtml(data?.budget || "未填写")}</div>
    <div>用户要求：${escapeHtml(data?.requirements || "未填写")}</div>
  </div>
  <table>
    <thead>
      <tr><th>#</th><th>时间</th><th>地点与任务</th><th>站位</th><th>光线</th><th>拍法</th></tr>
    </thead>
    <tbody>${rows}</tbody>
  </table>
  <div class="info">${infoRows}</div>
</body>
</html>`
}

function PresetDraftCard({
  preset,
  onCopy,
  onSendToAnalysis,
}: {
  preset: string
  onCopy: () => void
  onSendToAnalysis: () => void
}) {
  return (
    <div className="rounded-[10px] border border-green-200 bg-green-50 px-4 py-3 text-sm text-slate-700">
      <div className="mb-2 flex items-center justify-between gap-3">
        <p className="font-extrabold text-green-800">后期预设草稿已生成</p>
        <div className="flex gap-2">
          <button
            type="button"
            className="rounded-md border border-green-200 bg-white px-3 py-1 text-xs font-bold text-green-700 hover:bg-green-100"
            onClick={onCopy}
          >
            复制预设
          </button>
          <button
            type="button"
            className="rounded-md bg-green-600 px-3 py-1 text-xs font-bold text-white hover:bg-green-700"
            onClick={onSendToAnalysis}
          >
            带去分析页
          </button>
        </div>
      </div>
      <pre className="max-h-40 overflow-y-auto whitespace-pre-wrap rounded-md bg-white p-3 text-xs leading-6 text-slate-700">
        {preset}
      </pre>
    </div>
  )
}

function readPlanningDraft(): Partial<PlanningFormData> | null {
  const raw = window.sessionStorage.getItem(PLANNING_DRAFT_CACHE_KEY)
  if (!raw) return null
  try {
    const draft = JSON.parse(raw) as Record<string, unknown>
    const styleDirection = stringList(draft.styleDirection).join("；")
    const requirements = [
      draft.sourceFileName ? `参考分析照片：${textValue(draft.sourceFileName)}` : "",
      draft.userGoal ? `用户分析偏好：${textValue(draft.userGoal)}` : "",
      draft.postSummary ? `后期风格目标：${textValue(draft.postSummary)}` : "",
      styleDirection ? `风格方向：${styleDirection}` : "",
      draft.coachSummary ? `学习反馈重点：${textValue(draft.coachSummary)}` : "",
      draft.sourceJobId ? `来源分析任务：${textValue(draft.sourceJobId)}` : "",
    ].filter(Boolean).join("；")

    return {
      subject: "风光人像",
      equipment: "广角 + 长焦",
      timePreference: "整个白天",
      requirements,
    }
  } catch {
    return null
  }
}

function PlanningPageContent() {
  const searchParams = useSearchParams()
  const unsubscribeRef = useRef<(() => void) | null>(null)
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const formDataRef = useRef<PlanningFormData | null>(null)

  const [jobId, setJobId] = useState<string | null>(searchParams.get("job_id"))
  const [status, setStatus] = useState<JobStatus | "idle" | "creating">("idle")
  const [plans, setPlans] = useState<PlanResult[]>(mockPlanningPagePlans)
  const [notice, setNotice] = useState<{ kind: PlanningNoticeKind; message: string } | null>(null)
  const [events, setEvents] = useState<string[]>([])
  const [lastFormData, setLastFormData] = useState<PlanningFormData | null>(null)
  const [initialFormData, setInitialFormData] = useState<Partial<PlanningFormData>>({
    city: "大理",
    subject: "风光人像",
  })
  const [planningFormKey, setPlanningFormKey] = useState("default")
  const [generatedPreset, setGeneratedPreset] = useState<string>("")
  const [adoptedPlanId, setAdoptedPlanId] = useState<string | null>(null)

  const clearPlanTimeout = useCallback(() => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current)
      timeoutRef.current = null
    }
  }, [])

  const loadPlanResults = useCallback(async (targetJobId: string) => {
    const response = await getJobResults(targetJobId)
    clearPlanTimeout()
    setStatus(response.status)
    const planResult = response.results.find((result) => result.agent === "plan")
    if (!planResult) {
      setNotice({
        kind: "warning",
        message: "任务存在，但 PlanAgent 结果暂不可用；可能仍在运行或结果尚未写入。",
      })
      return
    }
    if (planResult.status === "failed") {
      setPlans(mockPlanningPagePlans)
      setGeneratedPreset("")
      setAdoptedPlanId(null)
      setNotice({
        kind: "error",
        message: planResult.agentError || "方案生成失败，当前展示示例规划方案，便于 Demo 继续。",
      })
      return
    }
    setPlans(mapPlanResult(planResult, formDataRef.current ?? inferPlanningDataFromResult(planResult)))
    setGeneratedPreset("")
    setAdoptedPlanId(null)
    const providerNote = textValue(planResult.structuredPayload.provider_note ?? planResult.structuredPayload.providerNote)
    const fallbackHint =
      /未配置|不可用|降级|超出|实时/.test(providerNote + planResult.visibleText)
        ? "实时天气/地点数据可能不可用，已基于通用拍摄经验生成参考方案。"
        : "PlanAgent 已生成拍摄方案。"
    setNotice({ kind: providerNote ? "warning" : "success", message: fallbackHint })
  }, [clearPlanTimeout])

  const subscribeToPlanJob = useCallback((targetJobId: string) => {
    unsubscribeRef.current?.()
    unsubscribeRef.current = subscribeJobEvents(targetJobId, {
      onEvent: (event: AgentEventMessage) => {
        setEvents((current) => [...current.slice(-4), event.message || event.type])
        if (event.type === "job.started" || event.type === "agent.progress") {
          setStatus("running")
        }
        if (event.type === "job.completed" || event.type === "job.partial_completed" || event.type === "job.failed") {
          void loadPlanResults(targetJobId)
        }
      },
      onError: () => {
        setNotice({
          kind: "warning",
          message: "SSE 连接暂时中断，后台规划任务不会因此停止；可稍后从历史记录恢复结果。",
        })
      },
    })
    clearPlanTimeout()
    timeoutRef.current = setTimeout(() => {
      setNotice({
        kind: "warning",
        message: "PlanAgent 运行时间较长，可能是模型或 provider 较慢；你可以继续等待，或先查看示例规划方案。",
      })
    }, 90_000)
  }, [clearPlanTimeout, loadPlanResults])

  useEffect(() => {
    const targetJobId = searchParams.get("job_id")
    if (!targetJobId) return
    const timer = window.setTimeout(async () => {
      try {
        const job = await getJob(targetJobId)
        setJobId(targetJobId)
        setStatus(job.status)
        if (job.status === "completed" || job.status === "partial_completed" || job.status === "failed") {
          await loadPlanResults(targetJobId)
        } else {
          subscribeToPlanJob(targetJobId)
        }
      } catch (error) {
        setNotice({
          kind: "error",
          message: error instanceof Error ? `历史规划任务恢复失败：${error.message}` : "历史规划任务恢复失败。",
        })
      }
    }, 0)
    return () => window.clearTimeout(timer)
  }, [loadPlanResults, searchParams, subscribeToPlanJob])

  useEffect(() => {
    if (searchParams.get("job_id")) return
    const timer = window.setTimeout(() => {
      const draft = readPlanningDraft()
      if (!draft) return
      setInitialFormData((current) => ({ ...current, ...draft }))
      setPlanningFormKey(`analysis-draft-${Date.now()}`)
      setNotice({
        kind: "info",
        message: "已从分析页带入照片风格、后期方向和学习反馈，可继续补充城市/日期后生成拍摄规划。",
      })
    }, 0)
    return () => window.clearTimeout(timer)
  }, [searchParams])

  useEffect(() => {
    return () => {
      unsubscribeRef.current?.()
      clearPlanTimeout()
    }
  }, [clearPlanTimeout])

  const createPlanningJob = async (data: PlanningFormData, refinement = "") => {
    const validationError = validateForm(data)
    if (validationError) {
      setNotice({ kind: "error", message: validationError })
      return
    }

    try {
      const requestData = {
        ...data,
        requirements: [data.requirements, refinement ? `迭代优化：${refinement}` : ""].filter(Boolean).join("；"),
      }
      const parsedConstraints = parsePlanningConstraints(requestData)
      formDataRef.current = requestData
      setLastFormData(requestData)
      setNotice({ kind: "info", message: "正在创建 trip_planning job..." })
      setStatus("creating")
      setEvents([])
      setGeneratedPreset("")
      setAdoptedPlanId(null)
      const createdJob = await createJob({
        type: "trip_planning",
        agents: ["plan"],
        user_goal: buildUserGoal(requestData),
        context: {
          city: requestData.city,
          shoot_date: requestData.date,
          time_window: requestData.timePreference,
          subject: requestData.subject,
          gear: requestData.equipment ? [requestData.equipment] : [],
          style_keywords: requestData.requirements ? [requestData.requirements] : [],
          budget: requestData.budget,
          requirements: requestData.requirements,
          refinement_request: refinement,
          constraints: [
            requestData.requirements ? `其他要求优先：${requestData.requirements}` : "",
            parsedConstraints.start_time ? `开始时间：${parsedConstraints.start_time}` : "",
            parsedConstraints.end_time ? `结束时间：${parsedConstraints.end_time}` : "",
            parsedConstraints.required_locations.length
              ? `必须包含地点：${parsedConstraints.required_locations.join("、")}`
              : "",
            parsedConstraints.excluded_locations.length
              ? `必须避开地点：${parsedConstraints.excluded_locations.join("、")}`
              : "",
            parsedConstraints.shooting_goals.length
              ? `拍摄目标：${parsedConstraints.shooting_goals.join("、")}；落日/黄金时刻窗口参考 ${goldenWindow(requestData).sunsetStart}-${goldenWindow(requestData).sunsetEnd}，不要把目标写成地点`
              : "",
            parsedConstraints.required_meals.lunch
              ? `午饭要求：${parsedConstraints.required_meals.lunch_time || "用户要求安排午饭"}`
              : "用户未要求午饭，不要默认插入午饭节点",
            parsedConstraints.required_meals.dinner
              ? `晚饭要求：${parsedConstraints.required_meals.dinner_time || "用户要求安排晚饭"}；如与黄金时刻冲突，先拍落日，晚饭顺延`
              : "用户未要求晚饭，不要默认插入晚饭节点",
            parsedConstraints.route_pace !== "normal" ? `路线节奏：${parsedConstraints.route_pace}` : "",
            ...parsedConstraints.forbidden_assumptions,
          ].filter(Boolean),
          hard_constraints: {
            user_requirements_first: true,
            start_time: parsedConstraints.start_time,
            end_time: parsedConstraints.end_time,
            required_locations: parsedConstraints.required_locations,
            excluded_locations: parsedConstraints.excluded_locations,
            shooting_goals: parsedConstraints.shooting_goals,
            golden_window: goldenWindow(requestData),
            required_meals: parsedConstraints.required_meals,
            forbidden_assumptions: parsedConstraints.forbidden_assumptions,
            route_pace: parsedConstraints.route_pace,
            traffic_preferences: parsedConstraints.traffic_preferences,
            budget: parsedConstraints.budget,
            style_preferences: parsedConstraints.style_preferences,
            special_goals: parsedConstraints.special_goals,
            full_day: wantsFullDay(requestData),
            detailed_route: wantsDetailedRoute(requestData),
            min_spots_per_plan: wantsFullDay(requestData) ? 5 : wantsDetailedRoute(requestData) ? 4 : 3,
            user_requirements: requestData.requirements,
          },
          output_requirements: {
            concrete_spots: true,
            include_position: true,
            include_lighting: true,
            include_method: true,
            include_transfer_nodes: true,
            include_route_validation: true,
            include_local_food_area_dish_budget: parsedConstraints.special_goals.includes("包含当地美食建议"),
            avoid_generic_spot_titles: true,
          },
        },
      })
      setJobId(createdJob.jobId)
      setStatus(createdJob.status)
      window.history.replaceState(null, "", `/planning?job_id=${createdJob.jobId}`)
      subscribeToPlanJob(createdJob.jobId)
    } catch (error) {
      setStatus("idle")
      setPlans(mockPlanningPagePlans)
      setGeneratedPreset("")
      setAdoptedPlanId(null)
      setNotice({
        kind: "error",
        message: error instanceof Error ? `方案生成失败：${error.message}。当前展示示例规划方案。` : "方案生成失败，当前展示示例规划方案。",
      })
    }
  }

  const handleSubmit = async (data: PlanningFormData) => {
    await createPlanningJob(data)
  }

  const handleRegenerate = async (feedback: string) => {
    const trimmedFeedback = feedback.trim()
    if (!trimmedFeedback) {
      setNotice({ kind: "error", message: "请先输入需要调整或细化的方向。" })
      return
    }
    const baseData = lastFormData || formDataRef.current
    if (!baseData) {
      setNotice({ kind: "error", message: "请先生成一次拍摄方案，再进行迭代优化。" })
      return
    }
    await createPlanningJob(baseData, trimmedFeedback)
  }

  const handleUseDemo = () => {
    unsubscribeRef.current?.()
    clearPlanTimeout()
    setPlans(mockPlanningPagePlans)
    setGeneratedPreset("")
    setAdoptedPlanId(null)
    setStatus("completed")
    setNotice({ kind: "info", message: "当前展示 Demo 规划方案，用于 provider 或模型不可用时稳定演示。" })
  }

  const findPlan = useCallback((planId: string) => plans.find((plan) => plan.id === planId), [plans])

  const handleExportPlan = useCallback((planId: string) => {
    const plan = findPlan(planId)
    if (!plan) {
      setNotice({ kind: "error", message: "未找到当前方案，无法导出报告。" })
      return
    }
    const html = buildPlanReportHtml(plan, lastFormData || initialFormData, jobId)
    const reportWindow = window.open("", "_blank", "noopener,noreferrer")
    if (!reportWindow) {
      const blob = new Blob([html], { type: "text/html;charset=utf-8" })
      const url = window.URL.createObjectURL(blob)
      const link = document.createElement("a")
      link.href = url
      link.download = `PhotoAI_${plan.name}_拍摄规划报告.html`
      link.click()
      window.URL.revokeObjectURL(url)
      setNotice({ kind: "warning", message: "浏览器阻止了打印窗口，已导出 HTML 报告，可打开后另存为 PDF。" })
      return
    }
    reportWindow.document.open()
    reportWindow.document.write(html)
    reportWindow.document.close()
    reportWindow.focus()
    setNotice({ kind: "success", message: "已打开拍摄规划报告窗口，可点击打印并另存为 PDF。" })
  }, [findPlan, initialFormData, jobId, lastFormData])

  const handleGeneratePreset = useCallback((planId: string) => {
    const plan = findPlan(planId)
    if (!plan) {
      setNotice({ kind: "error", message: "未找到当前方案，无法生成后期预设。" })
      return
    }
    const preset = buildPresetText(plan, lastFormData || initialFormData)
    setGeneratedPreset(preset)
    setNotice({ kind: "success", message: "已根据当前拍摄方案生成后期预设草稿，可复制或带去分析页作为后期偏好。" })
  }, [findPlan, initialFormData, lastFormData])

  const handleAdoptPlan = useCallback((planId: string) => {
    const plan = findPlan(planId)
    if (!plan) {
      setNotice({ kind: "error", message: "未找到当前方案，无法采用。" })
      return
    }
    const payload = buildPlanActionPayload(plan, lastFormData || initialFormData, jobId)
    window.localStorage.setItem(PLANNING_ADOPTED_PLAN_KEY, JSON.stringify(payload))
    window.sessionStorage.setItem(PLANNING_ADOPTED_PLAN_KEY, JSON.stringify(payload))
    setAdoptedPlanId(plan.id)
    setNotice({ kind: "success", message: `已采用 ${plan.name}，方案已保存到本地，可用于 Demo 恢复和后续执行。` })
  }, [findPlan, initialFormData, jobId, lastFormData])

  const handleCopyPreset = useCallback(async () => {
    if (!generatedPreset) return
    try {
      await navigator.clipboard.writeText(generatedPreset)
      setNotice({ kind: "success", message: "后期预设草稿已复制。" })
    } catch {
      setNotice({ kind: "warning", message: "浏览器未允许自动复制，请手动选择预设文本复制。" })
    }
  }, [generatedPreset])

  const handleSendPresetToAnalysis = useCallback(() => {
    if (!generatedPreset) return
    window.sessionStorage.setItem(
      PLANNING_PRESET_DRAFT_KEY,
      JSON.stringify({
        source: "planning",
        intent: "send_to_analysis",
        source_job_id: jobId,
        preset: generatedPreset,
        created_at: new Date().toISOString(),
      }),
    )
    setNotice({ kind: "success", message: "已保存后期预设草稿，正在前往分析页。" })
    window.location.href = "/analysis"
  }, [generatedPreset, jobId])

  const isBusy = status === "creating" || status === "queued" || status === "running" || status === "streaming"

  const statusText = useMemo(() => {
    if (status === "creating") return "正在创建任务"
    if (status === "queued") return "任务排队中"
    if (status === "running" || status === "streaming") return "PlanAgent 正在生成方案"
    if (status === "completed") return "规划完成"
    if (status === "failed") return "规划失败"
    return "填写需求后生成方案"
  }, [status])
  const recognizedConstraintData = lastFormData || initialFormData

  return (
    <div className="p-6 max-w-[1400px] mx-auto space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-slate-200 bg-white px-4 py-3">
        <div>
          <p className="text-sm font-bold text-slate-900">{statusText}</p>
          <p className="text-xs text-slate-500">
            {jobId ? `当前任务：${jobId}` : "规划页通过统一 Job/SSE/Result 机制恢复结果"}
          </p>
        </div>
        <button
          className="h-9 rounded-md border border-slate-300 px-3 text-sm font-bold text-slate-700 hover:bg-slate-50"
          onClick={handleUseDemo}
        >
          查看示例规划
        </button>
      </div>

      {notice && (
        <div className={`flex items-center gap-2 rounded-lg border px-4 py-3 text-sm font-medium ${noticeClass(notice.kind)}`}>
          {notice.kind === "success" ? <CheckCircle2 className="h-4 w-4" /> : <AlertTriangle className="h-4 w-4" />}
          {notice.message}
        </div>
      )}

      {events.length > 0 && (
        <div className="rounded-lg border border-slate-200 bg-white px-4 py-2 text-xs text-slate-500">
          {isBusy && <Loader2 className="mr-2 inline h-3.5 w-3.5 animate-spin" />}
          {events.join(" / ")}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-stretch lg:h-[calc(100vh-150px)] lg:min-h-[860px]">
        <div className="lg:col-span-4 min-h-0">
          <PlanningForm
            key={planningFormKey}
            onSubmit={handleSubmit}
            initialData={initialFormData}
            isGenerating={isBusy}
          />
        </div>

        <div className="lg:col-span-8 min-h-0 flex flex-col gap-4">
          <ConstraintSummaryCard data={recognizedConstraintData} />
          {isBusy && (
            <div className="flex shrink-0 items-center gap-3 rounded-[10px] border border-blue-200 bg-blue-50 px-4 py-3 text-sm font-bold text-blue-700 shadow-sm">
              <Loader2 className="h-4 w-4 animate-spin" />
              <span>{statusText}，正在生成可执行路线、具体机位和拍摄建议...</span>
            </div>
          )}
          <PlanResultCard
            plans={plans}
            onExport={handleExportPlan}
            onGeneratePreset={handleGeneratePreset}
            onAdopt={handleAdoptPlan}
            adoptedPlanId={adoptedPlanId}
          />

          {generatedPreset && (
            <PresetDraftCard
              preset={generatedPreset}
              onCopy={handleCopyPreset}
              onSendToAnalysis={handleSendPresetToAnalysis}
            />
          )}

          <PlanAdjustmentCard onRegenerate={handleRegenerate} disabled={isBusy} />
        </div>
      </div>
    </div>
  )
}

function PlanningPageFallback() {
  return (
    <div className="p-6 max-w-[1400px] mx-auto space-y-4">
      <div className="rounded-lg border border-slate-200 bg-white px-4 py-3">
        <p className="text-sm font-bold text-slate-900">正在加载拍摄规划页</p>
        <p className="text-xs text-slate-500">正在准备历史任务恢复与规划表单...</p>
      </div>
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-stretch lg:h-[calc(100vh-150px)] lg:min-h-[860px]">
        <div className="lg:col-span-4 rounded-xl border border-slate-200 bg-white" />
        <div className="lg:col-span-8 rounded-xl border border-slate-200 bg-white" />
      </div>
    </div>
  )
}

export default function PlanningPage() {
  return (
    <Suspense fallback={<PlanningPageFallback />}>
      <PlanningPageContent />
    </Suspense>
  )
}
