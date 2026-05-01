"use client"

import { useState } from "react"
import { Sparkles, WandSparkles, ChevronDown, Upload, Loader2 } from "lucide-react"

export interface PlanningFormData {
  city: string
  date: string
  timePreference: string
  subject: string
  equipment: string
  budget: string
  referenceImages: string[]
  requirements: string
}

interface PlanningFormProps {
  onSubmit?: (data: PlanningFormData) => void
  initialData?: Partial<PlanningFormData>
  isGenerating?: boolean
}

export function PlanningForm({ onSubmit, initialData, isGenerating = false }: PlanningFormProps) {
  const [formData, setFormData] = useState<PlanningFormData>({
    city: initialData?.city || "",
    date: initialData?.date || "",
    timePreference: initialData?.timePreference || "",
    subject: initialData?.subject || "",
    equipment: initialData?.equipment || "",
    budget: initialData?.budget || "",
    referenceImages: initialData?.referenceImages || [],
    requirements: initialData?.requirements || "",
  })

  const updateField = (field: keyof PlanningFormData, value: string) => {
    setFormData((prev) => ({ ...prev, [field]: value }))
  }

  const handleSubmit = () => {
    onSubmit?.(formData)
  }

  const inputClass =
    "w-full h-[38px] px-3 rounded-[7px] border border-[#CBD5E1] bg-white text-sm text-[#0F172A] placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"

  const labelClass = "text-[13px] font-extrabold text-[#0F172A]"

  return (
    <div className="rounded-[10px] border border-[#E2E8F0] bg-white p-[22px] space-y-[18px] h-full flex flex-col"
    >
      {/* Title */}
      <div className="flex items-center gap-3"
      >
        <Sparkles className="w-[22px] h-[22px] text-[#0F172A]" />
        <h2 className="text-[22px] font-extrabold text-[#0F172A]"
        >拍摄规划助手</h2>
      </div>
      <p className="text-sm text-[#64748B]"
      >填写拍摄需求，AI 为你生成多套可执行方案</p>

      {/* City */}
      <div className="space-y-2"
      >
        <label className={labelClass}
        >城市 *</label>
        <input
          type="text"
          placeholder="如：大理、丽江"
          className={inputClass}
          value={formData.city}
          onChange={(e) => updateField("city", e.target.value)}
        />
      </div>

      {/* Date */}
      <div className="space-y-2"
      >
        <label className={labelClass}
        >拍摄日期 *</label>
        <input
          type="date"
          className={inputClass}
          value={formData.date}
          onChange={(e) => updateField("date", e.target.value)}
        />
      </div>

      {/* Time Preference */}
      <div className="space-y-2"
      >
        <label className={labelClass}
        >时段偏好</label>
        <div className="relative"
        >
          <select
            className={`${inputClass} appearance-none cursor-pointer`}
            value={formData.timePreference}
            onChange={(e) => updateField("timePreference", e.target.value)}
          >
            <option value=""
            >请选择时段偏好</option>
            <option value="日出"
            >日出</option>
            <option value="上午"
            >上午</option>
            <option value="整个白天"
            >整个白天</option>
            <option value="下午"
            >下午</option>
            <option value="日落"
            >日落</option>
            <option value="夜景"
            >夜景</option>
          </select>
          <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
        </div>
      </div>

      {/* Subject */}
      <div className="space-y-2"
      >
        <label className={labelClass}
        >题材</label>
        <div className="relative"
        >
          <select
            className={`${inputClass} appearance-none cursor-pointer`}
            value={formData.subject}
            onChange={(e) => updateField("subject", e.target.value)}
          >
            <option value=""
            >请选择题材</option>
            <option value="风光人像"
            >风光人像</option>
            <option value="古城街拍"
            >古城街拍</option>
            <option value="建筑摄影"
            >建筑摄影</option>
            <option value="人文纪实"
            >人文纪实</option>
          </select>
          <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
        </div>
      </div>

      {/* Equipment */}
      <div className="space-y-2"
      >
        <label className={labelClass}
        >器材</label>
        <div className="relative"
        >
          <select
            className={`${inputClass} appearance-none cursor-pointer`}
            value={formData.equipment}
            onChange={(e) => updateField("equipment", e.target.value)}
          >
            <option value=""
            >请选择器材配置</option>
            <option value="广角 + 长焦"
            >广角 + 长焦</option>
            <option value="定焦套装"
            >定焦套装</option>
            <option value="微单轻便"
            >微单轻便</option>
            <option value="全画幅旗舰"
            >全画幅旗舰</option>
          </select>
          <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
        </div>
      </div>

      {/* Budget */}
      <div className="space-y-2"
      >
        <label className={labelClass}
        >预算</label>
        <div className="relative"
        >
          <select
            className={`${inputClass} appearance-none cursor-pointer`}
            value={formData.budget}
            onChange={(e) => updateField("budget", e.target.value)}
          >
            <option value=""
            >请选择预算</option>
            <option value="经济型"
            >经济型</option>
            <option value="标准"
            >标准</option>
            <option value="豪华"
            >豪华</option>
          </select>
          <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
        </div>
      </div>

      {/* Reference Images */}
      <div className="space-y-2"
      >
        <label className={labelClass}
        >风格参考（可选）</label>
        <div className="border border-dashed border-[#CBD5E1] rounded-[7px] h-14 flex items-center justify-center gap-2 cursor-pointer hover:border-slate-400 transition-colors bg-white"
        >
          <Upload className="w-4 h-4 text-slate-400" />
          <span className="text-sm text-slate-500"
          >上传参考图片</span>
        </div>
      </div>

      {/* Other Requirements */}
      <div className="space-y-2"
      >
        <label className={labelClass}
        >其他要求</label>
        <textarea
          placeholder="如：希望包含当地特色美食、需要兼顾老人和小孩的体力..."
          rows={2}
          className="w-full px-3 py-2.5 rounded-[7px] border border-[#CBD5E1] bg-white text-sm text-[#0F172A] placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 resize-none"
          value={formData.requirements}
          onChange={(e) => updateField("requirements", e.target.value)}
        />
      </div>

      {/* Generate Button */}
      <button
        className="w-full h-12 rounded-[7px] bg-[#0F1F45] text-white text-base font-extrabold flex items-center justify-center gap-2.5 hover:bg-[#1a3055] transition-colors disabled:cursor-not-allowed disabled:bg-slate-400"
        disabled={isGenerating}
        onClick={handleSubmit}
      >
        {isGenerating ? (
          <Loader2 className="w-[19px] h-[19px] animate-spin" />
        ) : (
          <WandSparkles className="w-[19px] h-[19px]" />
        )}
        {isGenerating ? "正在生成方案..." : "生成拍摄方案"}
      </button>
      {isGenerating && (
        <p className="rounded-[7px] border border-blue-200 bg-blue-50 px-3 py-2 text-xs font-bold text-blue-700">
          PlanAgent 正在生成路线、机位和执行建议，完成后右侧会自动更新。
        </p>
      )}
    </div>
  )
}
