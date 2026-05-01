/**
 * Planning Mock 数据
 * 拍摄规划相关 mock 数据
 */

import type {
  PlanningRequest,
  PlanningResult,
  PlanVariant,
} from "@/types/api"
import type { PlanResult as PlanningPagePlanResult } from "@/components/planning"

// ============================================================================
// Mock 规划请求
// ============================================================================

export const mockPlanningRequest: PlanningRequest = {
  city: "大理",
  date: "2024-05-01",
  timeSlots: ["日出", "上午", "下午"],
  subject: "风光人像、古城街拍",
  equipment: "Sony A7M4 + 35mm f/1.4",
  budget: "标准",
  referenceImages: [],
  requirements: "希望包含当地特色美食，需要兼顾老人和小孩的体力",
}

// ============================================================================
// Mock 规划方案变体
// ============================================================================

export const mockPlanVariants: PlanVariant[] = [
  {
    id: "A",
    name: "方案 A",
    spots: [
      {
        time: "06:00",
        title: "龙龛码头",
        description: "洱海日出经典机位，拍摄逆光剪影和水面倒影",
        position: "码头栈桥尽头",
        lighting: "逆光，金色时刻",
        method: "广角拍摄，低角度",
      },
      {
        time: "08:30",
        title: "喜洲古镇",
        description: "白族民居建筑群，人文与建筑结合",
        position: "四方街转角",
        lighting: "侧光，柔和",
        method: "35mm人文视角",
      },
      {
        time: "14:00",
        title: "双廊观景台",
        description: "俯瞰洱海全景，苍山背景",
        position: "观景台二层",
        lighting: "顶光，需HDR",
        method: "长焦压缩空间",
      },
    ],
    info: [
      {
        icon: "check",
        title: "推荐理由",
        content: "本方案涵盖洱海日出、人文古镇、全景风光三大主题，时间安排合理，光线条件优越。",
      },
      {
        icon: "camera",
        title: "器材建议",
        content: "广角16-35mm拍摄日出全景，35mm/85mm拍摄人文，70-200mm拍摄远景压缩",
      },
      {
        icon: "sun",
        title: "天气与光线提醒",
        content: "4月为云南旱季，晴天概率高。日出约6:15，建议提前30分钟到达机位",
      },
      {
        icon: "wand",
        title: "后期风格目标",
        content: "暖色调风光风格，提升橙色和金色饱和度，适当压暗天空增强层次感",
      },
    ],
  },
  {
    id: "B",
    name: "方案 B",
    spots: [
      {
        time: "07:00",
        title: "才村码头",
        description: "清晨渔船码头，人文风光结合",
        position: "码头东侧",
        lighting: "侧逆光",
        method: "中长焦抓拍",
      },
      {
        time: "10:00",
        title: "大理古城",
        description: "古城街景与五华楼",
        position: "南城门",
        lighting: "顶光",
        method: "广角建筑",
      },
      {
        time: "16:00",
        title: "崇圣寺三塔",
        description: "古建筑与倒影",
        position: "倒影池旁",
        lighting: "侧光",
        method: "对称构图",
      },
    ],
    info: [
      {
        icon: "check",
        title: "推荐理由",
        content: "侧重人文与市井生活，适合街拍爱好者",
      },
      {
        icon: "camera",
        title: "器材建议",
        content: "35mm为主，携带小型补光灯",
      },
      {
        icon: "sun",
        title: "天气与光线提醒",
        content: "上午光线较硬，建议后期加强对比度",
      },
      {
        icon: "wand",
        title: "后期风格目标",
        content: "高对比度街拍风格，增强纹理质感",
      },
    ],
  },
  {
    id: "C",
    name: "方案 C",
    spots: [
      {
        time: "17:00",
        title: "小普陀",
        description: "日落时分的小岛剪影",
        position: "西侧礁石",
        lighting: "逆光剪影",
        method: "长焦压缩",
      },
      {
        time: "19:00",
        title: "大理古城夜景",
        description: "华灯初上的古城街道",
        position: "复兴路",
        lighting: "暖色灯光",
        method: "大光圈手持",
      },
      {
        time: "20:30",
        title: "洱海边星空",
        description: "远离城市光污染的星空拍摄",
        position: "海东镇",
        lighting: "月光+星光",
        method: "长曝光，三脚架",
      },
    ],
    info: [
      {
        icon: "check",
        title: "推荐理由",
        content: "专注日落与夜景，适合喜欢弱光拍摄的摄影师",
      },
      {
        icon: "camera",
        title: "器材建议",
        content: "大光圈定焦必备，建议携带三脚架",
      },
      {
        icon: "sun",
        title: "天气与光线提醒",
        content: "关注日落时间与云层情况，星空拍摄需无月夜",
      },
      {
        icon: "wand",
        title: "后期风格目标",
        content: "冷暖对比风格，保留灯光暖调，星空降噪处理",
      },
    ],
  },
]

// ============================================================================
// Mock 完整规划结果
// ============================================================================

export const mockPlanningResult: PlanningResult = {
  id: "plan_001",
  title: "2024-04 云南旅拍方案",
  plans: mockPlanVariants,
}

// ============================================================================
// Mock 前端规划页展示数据
// ============================================================================

export const mockPlanningPagePlans: PlanningPagePlanResult[] = [
  {
    id: "A",
    name: "方案 A",
    title: "方案 A：经典城市风光路线",
    spots: [
      {
        time: "06:00",
        title: "龙龛码头",
        description: "洱海日出经典机位，拍摄逆光剪影和水面倒影",
        position: "码头栈桥尽头",
        lighting: "逆光，金色时刻",
        method: "广角拍摄，低角度",
      },
      {
        time: "08:30",
        title: "喜洲古镇",
        description: "白族民居建筑群，人文与建筑结合",
        position: "四方街转角",
        lighting: "侧光，柔和",
        method: "35mm人文视角",
      },
      {
        time: "14:00",
        title: "双廊观景台",
        description: "俯瞰洱海全景，苍山背景",
        position: "观景台二层",
        lighting: "顶光，需HDR",
        method: "长焦压缩空间",
      },
    ],
    info: [
      { label: "推荐理由", value: "覆盖古建与现代地标，光线条件理想，动静结合，出片率高。" },
      { label: "器材建议", value: "广角 16–35mm + 中长焦 70–200mm；三脚架、ND 减光镜、渐变镜（可选）" },
      { label: "天气与光线提醒", value: "多云或晴天更佳；日出方向东南，注意早晚温差与逆光眩光控制。" },
      { label: "后期风格目标", value: "通透自然、色彩温暖、细节清晰、对比适中。" },
    ],
  },
  {
    id: "B",
    name: "方案 B",
    title: "方案 B：人文市井路线",
    spots: [
      {
        time: "07:00",
        title: "才村码头",
        description: "清晨渔船码头，人文风光结合",
        position: "码头东侧",
        lighting: "侧逆光",
        method: "中长焦抓拍",
      },
      {
        time: "10:00",
        title: "大理古城",
        description: "古城街景与五华楼",
        position: "南城门",
        lighting: "顶光",
        method: "广角建筑",
      },
    ],
    info: [
      { label: "推荐理由", value: "侧重人文与市井生活，适合街拍爱好者。" },
      { label: "器材建议", value: "35mm为主，携带小型补光灯。" },
      { label: "天气与光线提醒", value: "上午光线较硬，建议后期加强对比度。" },
      { label: "后期风格目标", value: "高对比度街拍风格，增强纹理质感。" },
    ],
  },
  {
    id: "C",
    name: "方案 C",
    title: "方案 C：日落夜景路线",
    spots: [
      {
        time: "17:00",
        title: "小普陀",
        description: "日落时分的小岛剪影",
        position: "西侧礁石",
        lighting: "逆光剪影",
        method: "长焦压缩",
      },
      {
        time: "19:00",
        title: "大理古城夜景",
        description: "华灯初上的古城街道",
        position: "复兴路",
        lighting: "暖色灯光",
        method: "大光圈手持",
      },
    ],
    info: [
      { label: "推荐理由", value: "专注日落与夜景，适合喜欢弱光拍摄的摄影师。" },
      { label: "器材建议", value: "大光圈定焦必备，建议携带三脚架。" },
      { label: "天气与光线提醒", value: "关注日落时间与云层情况。" },
      { label: "后期风格目标", value: "冷暖对比风格，保留灯光暖调。" },
    ],
  },
]
