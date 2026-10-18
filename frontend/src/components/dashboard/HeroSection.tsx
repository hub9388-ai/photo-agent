import Link from "next/link"
import { ArrowRight, Camera, FolderOpen, History, MapPin } from "lucide-react"

const tasks = [
  { state: "准备出门拍摄", label: "规划一次拍摄", href: "/planning", icon: MapPin,
    detail: "确定目的地、拍摄题材与时间，安排拍摄方案。" },
  { state: "拍完一批照片", label: "导入照片并选片", href: "/assets", icon: FolderOpen,
    detail: "进入素材库整理、评分和筛选，再挑选照片继续分析。" },
  { state: "已有目标照片", label: "分析并优化照片", href: "/analysis", icon: Camera,
    detail: "获得后期与拍摄建议，再按需进入修图调整。" },
  { state: "继续之前的工作", label: "继续最近任务", href: "#recent-tasks", icon: History,
    detail: "从下方最近记录继续查看分析、规划或学习任务。" },
]

export function HeroSection() {
  return (
    <section aria-labelledby="dashboard-heading" className="space-y-6">
      <div className="space-y-3">
        <h1 id="dashboard-heading" className="text-3xl font-bold text-slate-900 sm:text-4xl">摄影多 Agent 工作台</h1>
        <p className="text-lg leading-8 text-slate-600">从出发前规划，到选片、分析、修图与学习复盘，按你当前的需要开始。</p>
      </div>
      <div>
        <h2 className="mb-4 text-lg font-semibold text-slate-900">你现在想做什么？</h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {tasks.map(({ state, label, href, icon: Icon, detail }) => (
            <Link key={href} href={href} className="group rounded-xl border border-slate-200 bg-white p-5 shadow-sm transition-colors hover:border-blue-400 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-blue-500">
              <div className="mb-4 flex items-center justify-between text-slate-500"><span className="text-sm">{state}</span><Icon className="h-5 w-5" aria-hidden="true" /></div>
              <h3 className="flex items-center justify-between gap-2 text-base font-semibold text-slate-900">{label}<ArrowRight className="h-4 w-4 text-blue-500" aria-hidden="true" /></h3>
              <p className="mt-2 text-sm leading-6 text-slate-600">{detail}</p>
            </Link>
          ))}
        </div>
      </div>
    </section>
  )
}
