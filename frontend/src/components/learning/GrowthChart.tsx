"use client"

import { ChartColumnIncreasing } from "lucide-react"

interface WeeklyScore {
  week: string
  score: number
}

interface GrowthChartProps {
  scores: WeeklyScore[]
  realRecordCount: number
  isDemo?: boolean
}

const barColors = [
  "bg-[#BFDBFE]",
  "bg-[#93C5FD]",
  "bg-[#93C5FD]",
  "bg-[#60A5FA]",
  "bg-[#3B82F6]",
  "bg-[#2563EB]",
  "bg-[#1D4ED8]",
]

export function GrowthChart({ scores, realRecordCount, isDemo = false }: GrowthChartProps) {
  const maxScore = 100
  const validScores = scores.filter((item) => item.score > 0)
  const firstScore = validScores[0]?.score ?? 0
  const lastScore = validScores[validScores.length - 1]?.score ?? 0
  const growth = firstScore > 0 ? Math.round(((lastScore - firstScore) / firstScore) * 100) : 0
  const hasEnoughRealData = isDemo || realRecordCount >= 3

  return (
    <div className="rounded-[10px] border border-[#E2E8F0] bg-white p-[22px] space-y-4 flex-1"
    >
      <div className="flex items-center gap-2.5"
      >
        <ChartColumnIncreasing className="w-5 h-5 text-[#0F172A]" />
        <h2 className="text-lg font-extrabold text-[#0F172A]"
        >成长曲线</h2>
      </div>
      <p className="text-sm text-[#64748B]"
      >拍摄质量评分趋势（基于 CoachAgent 历史反馈）</p>

      {/* Chart */}
      <div className="relative h-[170px] pt-2"
      >
        {/* Y-axis labels */}
        <div className="absolute left-0 top-0 h-full flex flex-col justify-between text-xs text-[#64748B] pr-2"
        >
          <span>100</span>
          <span>75</span>
          <span>50</span>
          <span>25</span>
        </div>

        {/* Grid lines */}
        <div className="absolute left-8 right-0 top-0 h-full flex flex-col justify-between"
        >
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="h-px bg-[#E2E8F0]" />
          ))}
        </div>

        {/* Bars */}
        <div className="absolute left-8 right-0 top-0 h-[140px] flex items-end justify-around"
        >
          {scores.map((item, index) => {
            const heightPercent = Math.min((item.score / maxScore) * 100, 100)
            return (
              <div key={item.week} className="flex flex-col items-center gap-2"
              >
                <div
                  className={`w-8 rounded-t ${item.score > 0 ? barColors[index % barColors.length] : "bg-[#E2E8F0]"}`}
                  style={{ height: `${Math.max(heightPercent, item.score > 0 ? 8 : 4)}%` }}
                />
                <span className="text-xs text-[#64748B]"
                >{item.week}</span>
              </div>
            )
          })}
        </div>
      </div>

      {/* Summary */}
      {hasEnoughRealData && validScores.length >= 2 ? (
        <p className={`text-base font-extrabold ${growth >= 0 ? "text-[#16A34A]" : "text-[#DC2626]"}`}
        >
          平均得分：{firstScore} → {lastScore}　　{growth >= 0 ? "+" : ""}{growth}% {growth >= 0 ? "↑" : "↓"}
        </p>
      ) : (
        <div className="rounded-lg bg-[#F8FAFC] border border-[#E2E8F0] px-3 py-2 text-sm text-[#64748B]">
          完成 3 次分析后生成趋势。
        </div>
      )}
      {isDemo ? (
        <p className="text-xs text-[#94A3B8]">当前为示例趋势，用于展示页面形态。</p>
      ) : null}
    </div>
  )
}

export type { WeeklyScore }
