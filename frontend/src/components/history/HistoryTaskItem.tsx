import {
  BarChart3,
  CheckCircle2,
  CircleDot,
  Clock,
  FileText,
  FolderOpen,
  RefreshCw,
  XCircle,
  AlertTriangle,
  Loader2,
} from "lucide-react"

export type TaskType = "photo_review" | "trip_planning" | "asset_indexing" | string
export type TaskStatus = "queued" | "streaming" | "completed" | "running" | "partial_completed" | "failed" | "cancelled" | string

export interface HistoryTask {
  id: string
  title: string
  type: TaskType
  typeLabel: string
  status: TaskStatus
  statusLabel: string
  summary: string
  subSummary?: string
  detailSummary?: string
  time: string
  thumbGradient?: string
  thumbStyle?: "mosaic"
  failedAgents?: string[]
  actions: ("view" | "progress" | "rerun" | "retry" | "reuse" | "open" | "cancel")[]
}

interface HistoryTaskItemProps {
  task: HistoryTask
  onView?: () => void
  onRerun?: () => void
  onRetry?: () => void
  onReuse?: () => void
  onOpen?: () => void
}

const statusStyleMap: Record<string, { bg: string; text: string; Icon: typeof CheckCircle2 }> = {
  completed: { bg: "bg-[#DCFCE7]", text: "text-[#16A34A]", Icon: CheckCircle2 },
  running: { bg: "bg-[#DCFCE7]", text: "text-[#16A34A]", Icon: CircleDot },
  streaming: { bg: "bg-[#DBEAFE]", text: "text-[#2563EB]", Icon: Loader2 },
  queued: { bg: "bg-[#EFF6FF]", text: "text-[#2563EB]", Icon: Clock },
  partial_completed: { bg: "bg-[#FEF3C7]", text: "text-[#B45309]", Icon: AlertTriangle },
  failed: { bg: "bg-[#FEE2E2]", text: "text-[#EF4444]", Icon: XCircle },
  cancelled: { bg: "bg-[#F1F5F9]", text: "text-[#475569]", Icon: XCircle },
}

function MosaicThumb() {
  const colors = [
    "bg-[#93C5FD]", "bg-[#FDE68A]", "bg-[#94A3B8]", "bg-[#F97316]",
    "bg-[#64748B]", "bg-[#38BDF8]", "bg-[#FCA5A5]", "bg-[#93C5FD]",
    "bg-[#CBD5E1]", "bg-[#475569]", "bg-[#F59E0B]", "bg-[#2563EB]",
  ]
  return (
    <div className="w-[112px] h-[78px] rounded-[7px] bg-[#0F172A] overflow-hidden shrink-0 grid grid-cols-4 grid-rows-3 gap-1 p-1">
      {colors.map((c, i) => (
        <div key={i} className={`${c} rounded-sm`} />
      ))}
    </div>
  )
}

export function HistoryTaskItem({
  task,
  onView,
  onRerun,
  onRetry,
  onReuse,
  onOpen,
}: HistoryTaskItemProps) {
  const statusStyle = statusStyleMap[task.status] || { bg: "bg-slate-100", text: "text-slate-600", Icon: CheckCircle2 }
  const StatusIcon = statusStyle.Icon

  return (
    <div className="flex min-h-[104px] items-center justify-between rounded-[9px] border border-[#E2E8F0] bg-white px-[18px] py-3 shadow-[0_1px_2px_rgba(15,23,42,0.03)]">
      <div className="flex min-w-0 items-center gap-[26px]">
        {task.thumbStyle === "mosaic" ? (
          <MosaicThumb />
        ) : (
          <div
            className={`w-[112px] h-[78px] rounded-[7px] bg-gradient-to-br ${task.thumbGradient || "from-slate-200 to-slate-800"} shrink-0`}
          />
        )}

        <div className="min-w-0 space-y-1.5">
          <div className="flex min-w-0 items-center gap-3">
            <h3 className="max-w-[520px] truncate whitespace-nowrap text-lg font-extrabold text-[#0F172A]">{task.title}</h3>
            <span className="flex h-7 items-center justify-center rounded-[5px] bg-[#F1F5F9] px-3 text-xs font-medium text-[#475569]">
              {task.typeLabel}
            </span>
            <span className={`flex h-7 items-center justify-center gap-1.5 rounded-[5px] px-3 text-xs font-extrabold ${statusStyle.bg} ${statusStyle.text}`}>
              <StatusIcon className="h-[15px] w-[15px]" />
              {task.statusLabel}
            </span>
          </div>

          <p className="max-w-[920px] truncate text-sm text-[#334155]">{task.summary}</p>

          {task.subSummary && (
            <p className="max-w-[760px] truncate text-xs text-[#64748B]">{task.subSummary}</p>
          )}

          {task.detailSummary && (
            <p className="truncate text-xs font-medium text-[#64748B]">{task.detailSummary}</p>
          )}

          <div className="flex items-center gap-2">
            <Clock className="h-[15px] w-[15px] text-[#64748B]" />
            <span className="text-sm text-[#64748B]">{task.time}</span>
          </div>
        </div>
      </div>

      <div className="ml-6 flex shrink-0 items-center gap-3">
        <button
          className="flex h-[38px] w-[78px] items-center justify-center rounded-[7px] border border-[#CBD5E1] bg-white text-sm font-bold text-[#334155] transition-colors hover:bg-slate-50"
          onClick={onView}
        >
          {task.actions.includes("progress") ? "查看进度" : "查看"}
        </button>

        {task.actions.includes("retry") && (
          <button
            className="flex h-[38px] w-[178px] items-center justify-center gap-2 rounded-[7px] border border-[#FCA5A5] bg-[#FEF2F2] text-sm font-bold text-[#EF4444] transition-colors hover:bg-red-100"
            onClick={onRetry}
          >
            <RefreshCw className="h-4 w-4" />
            {task.failedAgents?.length ? `${task.failedAgents.join(" + ")} 重试` : "失败 Agent 重试"}
          </button>
        )}

        {task.actions.includes("rerun") && (
          <button
            className="flex h-[38px] w-[166px] items-center justify-center gap-2 rounded-[7px] border border-[#93C5FD] bg-[#EFF6FF] text-sm font-bold text-[#2563EB] transition-colors hover:bg-blue-100"
            onClick={onRerun}
          >
            <BarChart3 className="h-4 w-4" />
            重新分析
          </button>
        )}

        {task.actions.includes("reuse") && (
          <button
            className="flex h-[38px] w-[166px] items-center justify-center gap-2 rounded-[7px] border border-[#93C5FD] bg-[#EFF6FF] text-sm font-bold text-[#2563EB] transition-colors hover:bg-blue-100"
            onClick={onReuse}
          >
            <FileText className="h-4 w-4" />
            复用方案
          </button>
        )}

        {task.actions.includes("open") && (
          <button
            className="flex h-[38px] w-[166px] items-center justify-center gap-2 rounded-[7px] border border-[#93C5FD] bg-[#EFF6FF] text-sm font-bold text-[#2563EB] transition-colors hover:bg-blue-100"
            onClick={onOpen}
          >
            <FolderOpen className="h-4 w-4" />
            打开素材库
          </button>
        )}
      </div>
    </div>
  )
}
