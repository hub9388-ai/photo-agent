"use client"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { CalendarDays, ChevronDown, RefreshCw, Search } from "lucide-react"
import type { JobStatus, JobType } from "@/types/api"

interface HistoryFilterBarProps {
  searchQuery?: string
  onSearchChange?: (query: string) => void
  typeFilter?: JobType | "all"
  onTypeFilterChange?: (type: JobType | "all") => void
  statusFilter?: JobStatus | "all"
  onStatusFilterChange?: (status: JobStatus | "all") => void
  totalCount?: number
  onRefresh?: () => void
}

const typeOptions: { value: JobType | "all"; label: string }[] = [
  { value: "all", label: "类型: 全部" },
  { value: "photo_review", label: "photo_review" },
  { value: "trip_planning", label: "trip_planning" },
  { value: "asset_indexing", label: "asset_indexing" },
  { value: "post_process_advice", label: "post_process_advice" },
  { value: "coach_feedback", label: "coach_feedback" },
]

const statusOptions: { value: JobStatus | "all"; label: string }[] = [
  { value: "all", label: "状态: 全部" },
  { value: "completed", label: "已完成" },
  { value: "partial_completed", label: "部分完成" },
  { value: "failed", label: "失败" },
  { value: "running", label: "运行中" },
  { value: "streaming", label: "流式中" },
  { value: "cancelled", label: "已取消" },
]

export function HistoryFilterBar({
  searchQuery = "",
  onSearchChange,
  typeFilter = "all",
  onTypeFilterChange,
  statusFilter = "all",
  onStatusFilterChange,
  totalCount = 0,
  onRefresh,
}: HistoryFilterBarProps) {
  return (
    <div className="flex h-12 items-center justify-between">
      <div className="flex items-center gap-3">
        <div className="relative w-[326px]">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#64748B]" />
          <Input
            placeholder="搜索任务、标题或关键词..."
            className="h-10 rounded-[7px] border-[#CBD5E1] bg-white pl-10 text-sm shadow-none placeholder:text-[#64748B]"
            value={searchQuery}
            onChange={(e) => onSearchChange?.(e.target.value)}
          />
        </div>

        <div className="relative">
          <select
            value={typeFilter}
            onChange={(event) => onTypeFilterChange?.(event.target.value as JobType | "all")}
            className="h-10 w-[170px] appearance-none rounded-[7px] border border-[#CBD5E1] bg-white px-3 pr-8 text-sm font-semibold text-[#334155] shadow-none outline-none"
          >
            {typeOptions.map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
          <ChevronDown className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#475569]" />
        </div>

        <div className="relative">
          <select
            value={statusFilter}
            onChange={(event) => onStatusFilterChange?.(event.target.value as JobStatus | "all")}
            className="h-10 w-[142px] appearance-none rounded-[7px] border border-[#CBD5E1] bg-white px-3 pr-8 text-sm font-semibold text-[#334155] shadow-none outline-none"
          >
            {statusOptions.map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
          <ChevronDown className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#475569]" />
        </div>

        <Button variant="outline" className="h-10 w-[166px] justify-between rounded-[7px] border-[#CBD5E1] bg-white px-3 text-sm font-semibold text-[#334155] shadow-none">
          <span className="flex items-center gap-2">
            <CalendarDays className="h-4 w-4 text-[#334155]" />
            时间: 近 30 天
          </span>
          <ChevronDown className="h-4 w-4 text-[#475569]" />
        </Button>
      </div>

      <div className="flex items-center gap-4">
        <span className="text-sm text-[#334155]">共 {totalCount} 条</span>
        <Button
          variant="outline"
          size="icon"
          className="h-[38px] w-[38px] rounded-[7px] border-[#CBD5E1] bg-white shadow-none"
          onClick={onRefresh}
        >
          <RefreshCw className="h-[18px] w-[18px] text-[#334155]" />
        </Button>
      </div>
    </div>
  )
}
