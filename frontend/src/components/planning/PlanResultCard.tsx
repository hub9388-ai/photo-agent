"use client"

import { useState } from "react"
import {
  MapPinned,
  FileText,
  SlidersHorizontal,
  CheckSquare,
  RefreshCw,
  MapPin,
} from "lucide-react"
import { PlanTimeline, type TimelineSpot } from "./PlanTimeline"

export interface PlanInfo {
  label: string
  value: string
}

export interface PlanResult {
  id: string
  name: string
  title: string
  spots: TimelineSpot[]
  info: PlanInfo[]
}

interface PlanResultCardProps {
  plans: PlanResult[]
  onExport?: (planId: string) => void
  onGeneratePreset?: (planId: string) => void
  onAdopt?: (planId: string) => void
  adoptedPlanId?: string | null
}

export function PlanResultCard({
  plans,
  onExport,
  onGeneratePreset,
  onAdopt,
  adoptedPlanId,
}: PlanResultCardProps) {
  const [activeTab, setActiveTab] = useState(plans[0]?.id)
  const activePlan = plans.find((p) => p.id === activeTab)

  return (
    <div className="flex min-h-0 flex-[1.4] flex-col overflow-hidden rounded-[10px] border border-[#E2E8F0] bg-white p-5"
    >
      {/* Title */}
      <div className="flex shrink-0 items-center gap-3"
      >
        <MapPinned className="w-5 h-5 text-[#0F172A]" />
        <h2 className="text-[22px] font-extrabold text-[#0F172A]"
        >拍摄方案</h2>
      </div>

      {/* Tabs */}
      <div className="mt-4 flex shrink-0 gap-3"
      >
        {plans.map((plan) => {
          const isActive = plan.id === activeTab
          return (
            <button
              key={plan.id}
              onClick={() => setActiveTab(plan.id)}
              className={`h-9 px-5 rounded-[7px] text-sm font-extrabold border transition-colors ${
                isActive
                  ? "bg-[#0F1F45] text-white border-[#2563EB]"
                  : "bg-white text-[#0F172A] border-[#CBD5E1] hover:bg-slate-50"
              }`}
            >
              {plan.name}
            </button>
          )
        })}
      </div>

      {/* Route Card */}
      {activePlan && (
        <div className="mt-4 min-h-0 flex-1 overflow-y-auto rounded-[9px] border border-[#E2E8F0] bg-white p-[18px] space-y-3"
        >
          <h3 className="text-[19px] font-extrabold text-[#0F172A]"
          >{activePlan.title}</h3>

          <PlanTimeline spots={activePlan.spots} />

          {/* Reason Table */}
          <div className="rounded-[7px] border border-[#CBD5E1] bg-white overflow-hidden"
          >
            {activePlan.info.map((item, index) => (
              <div key={item.label}
              >
                <div className={`flex items-center gap-4 px-3 py-2 ${
                  item.label === "方案校验" && item.value.startsWith("需注意")
                    ? "bg-amber-50 text-amber-800"
                    : item.label === "方案校验"
                      ? "bg-green-50 text-green-800"
                      : ""
                }`}
                >
                  <span className={`text-[13px] font-extrabold whitespace-nowrap ${
                    item.label === "方案校验" && item.value.startsWith("需注意")
                      ? "text-amber-800"
                      : item.label === "方案校验"
                        ? "text-green-800"
                        : "text-[#0F172A]"
                  }`}
                  >{item.label}</span>
                  <span className={`text-[13px] ${
                    item.label === "方案校验" && item.value.startsWith("需注意")
                      ? "text-amber-800"
                      : item.label === "方案校验"
                        ? "text-green-800"
                        : "text-[#334155]"
                  }`}
                  >{item.value}</span>
                </div>
                {index < activePlan.info.length - 1 && (
                  <div className="h-px bg-[#E2E8F0]" />
                )}
              </div>
            ))}
          </div>

          {/* Actions */}
          <div className="flex items-center gap-3.5 pt-1"
          >
            <button
              className="h-[42px] px-4 rounded-[7px] border border-[#CBD5E1] bg-white text-sm font-bold text-[#334155] flex items-center gap-2 hover:bg-slate-50 transition-colors"
              onClick={() => onExport?.(activePlan.id)}
            >
              <FileText className="w-[17px] h-[17px]" />
              导出 PDF
            </button>
            <button
              className="h-[42px] px-4 rounded-[7px] border border-[#86EFAC] bg-[#F0FDF4] text-sm font-extrabold text-[#16A34A] flex items-center gap-2 hover:bg-green-100 transition-colors"
              onClick={() => onGeneratePreset?.(activePlan.id)}
            >
              <SlidersHorizontal className="w-[17px] h-[17px]" />
              生成后期预设
            </button>
            <button
              className={`h-[42px] px-5 rounded-[7px] text-sm font-extrabold flex items-center gap-2 transition-colors ${
                adoptedPlanId === activePlan.id
                  ? "bg-green-600 text-white hover:bg-green-700"
                  : "bg-[#0F1F45] text-white hover:bg-[#1a3055]"
              }`}
              onClick={() => onAdopt?.(activePlan.id)}
            >
              <CheckSquare className="w-[17px] h-[17px]" />
              {adoptedPlanId === activePlan.id ? "已采用方案" : "采用此方案"}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

interface PlanAdjustmentCardProps {
  onRegenerate?: (feedback: string) => void
  disabled?: boolean
}

export function PlanAdjustmentCard({ onRegenerate, disabled = false }: PlanAdjustmentCardProps) {
  const [feedback, setFeedback] = useState("")

  const handleRegenerate = () => {
    if (!feedback.trim()) return
    onRegenerate?.(feedback)
  }

  return (
    <div className="rounded-[9px] border border-[#E2E8F0] bg-white p-[18px] space-y-3"
    >
      {/* Title */}
      <div className="flex items-center gap-2.5"
      >
        <RefreshCw className="w-[19px] h-[19px] text-[#0F172A]" />
        <h3 className="text-lg font-extrabold text-[#0F172A]"
        >调整需求 / 迭代优化</h3>
      </div>
      <p className="text-[13px] text-[#64748B]"
      >输入调整意见，AI 将根据你的反馈重新生成优化方案</p>

      {/* Input + Button Row */}
      <div className="flex items-center gap-4"
      >
        <div className="flex-1 rounded-[7px] border border-[#CBD5E1] bg-white h-[70px] px-3.5 py-3 flex items-start"
        >
          <textarea
            placeholder="例如：希望增加更多室内场景、调整拍摄时间为傍晚、增加道具预算..."
            className="h-full w-full resize-none bg-transparent text-[13px] text-[#0F172A] placeholder:text-[#94A3B8] focus:outline-none"
            value={feedback}
            onChange={(e) => setFeedback(e.target.value)}
          />
        </div>
        <button
          className="h-12 px-5 rounded-[7px] bg-[#0F1F45] text-base font-extrabold text-white flex items-center justify-center hover:bg-[#1a3055] transition-colors shrink-0 disabled:cursor-not-allowed disabled:bg-slate-300"
          disabled={disabled || !feedback.trim()}
          onClick={handleRegenerate}
        >
          {disabled ? "生成中..." : "重新生成"}
        </button>
      </div>

      {/* Hint */}
      <div className="flex items-center gap-2"
      >
        <MapPin className="w-3.5 h-3.5 text-[#94A3B8]" />
        <p className="text-xs text-[#94A3B8]"
        >提示：会基于当前表单与已生成方案重新创建 trip_planning job，并保留你的调整意见。</p>
      </div>
    </div>
  )
}
