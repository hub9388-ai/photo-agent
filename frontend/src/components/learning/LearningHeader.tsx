"use client"

import { GraduationCap, Flame, CheckCircle, Award } from "lucide-react"

export interface LearningStats {
  streak: number
  completed: number
  level: string
}

interface LearningHeaderProps {
  stats: LearningStats
}

export function LearningHeader({ stats }: LearningHeaderProps) {
  return (
    <div className="rounded-[10px] border border-[#E2E8F0] bg-white h-[104px] flex items-center justify-between px-6"
    >
      <div className="flex items-center gap-[18px]"
      >
        <div className="w-[58px] h-[58px] rounded-[29px] bg-[#0F172A] flex items-center justify-center"
        >
          <GraduationCap className="w-7 h-7 text-white" />
        </div>
        <div className="space-y-1"
        >
          <h1 className="text-[22px] font-extrabold text-[#0F172A]"
          >学习教练</h1>
          <p className="text-sm text-[#64748B]"
          >基于照片评估的持续成长体系 — 点评、练习、追踪</p>
        </div>
      </div>

      <div className="flex gap-[18px]"
      >
        <StatCard
          icon={<Flame className="w-5 h-5 text-orange-500" />}
          value={stats.streak}
          label="连续学习"
          width={138}
        />
        <StatCard
          icon={<CheckCircle className="w-5 h-5 text-blue-500" />}
          value={stats.completed}
          label="已完成练习"
          width={128}
        />
        <StatCard
          icon={<Award className="w-5 h-5 text-purple-500" />}
          value={stats.level}
          label="学习等级"
          width={170}
        />
      </div>
    </div>
  )
}

function StatCard({
  icon,
  value,
  label,
  width,
}: {
  icon: React.ReactNode
  value: string | number
  label: string
  width: number
}) {
  return (
    <div
      className="h-[70px] rounded-lg border border-[#E2E8F0] bg-white flex items-center justify-center gap-3.5"
      style={{ width }}
    >
      {icon}
      <div className="text-center"
      >
        <p className="text-xl font-extrabold text-[#0F172A]"
        >{value}</p>
        <p className="text-xs text-[#64748B]"
        >{label}</p>
      </div>
    </div>
  )
}
