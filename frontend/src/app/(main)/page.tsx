import {
  HeroSection,
  CapabilityCard,
  WorkflowSteps,
  RecentTaskList,
  DashboardStatsGrid,
} from "@/components/dashboard"
import { Camera, FolderOpen, MapPin, GraduationCap } from "lucide-react"

const capabilities = [
  {
    icon: Camera,
    title: "分析照片",
    tags: "后期建议 + 学习反馈",
    description: "并行 AI 分析照片，提供曝光、色彩、构图等专业建议",
    color: "blue" as const,
  },
  {
    icon: FolderOpen,
    title: "素材管理",
    tags: "AI 分档、去重、精选",
    description: "自动分类与去重，智能评分与精选，高效管理素材",
    color: "green" as const,
  },
  {
    icon: MapPin,
    title: "拍摄规划",
    tags: "路线、机位、时段",
    description: "生成拍摄路线与机位方案，推荐最佳时段与器材配置",
    color: "orange" as const,
  },
  {
    icon: GraduationCap,
    title: "学习教练",
    tags: "点评、练习、成长",
    description: "个性化点评与练习计划，跟踪成长曲线",
    color: "purple" as const,
  },
]

export default function DashboardPage() {
  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      {/* Hero Section */}
      <HeroSection />

      {/* Core Capabilities */}
      <div>
        <h2 className="text-lg font-semibold text-slate-900 mb-4 flex items-center gap-2">
          <span className="text-yellow-500">✨</span>
          核心能力
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {capabilities.map((cap) => (
            <CapabilityCard key={cap.title} {...cap} />
          ))}
        </div>
      </div>

      {/* Workflow Steps */}
      <WorkflowSteps />

      {/* Bottom Section */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Recent Tasks */}
        <RecentTaskList />

        {/* Statistics */}
        <DashboardStatsGrid />
      </div>
    </div>
  )
}
