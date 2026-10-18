import { useState } from "react"
import { Check, ChevronRight, Circle, Clock3, Frame, Mountain, Upload } from "lucide-react"
import type { PracticeAttempt, PracticeTask } from "@/types/learning"
import { PracticeAttemptList } from "./PracticeAttemptList"
import { DEMO_MODE } from "@/lib/demo/config"

export type { PracticeAttempt, PracticeTask }

interface PracticeTaskItemProps {
  task: PracticeTask
  onClick?: () => void
  onRequestUpload?: (task: PracticeTask) => void
  onRetryAttempt?: (task: PracticeTask, attempt: PracticeAttempt) => void
  onShowDemoAttempt?: () => void
  isUploading?: boolean
}

const statusStyles: Record<string, { className: string; Icon: typeof Check }> = {
  completed: { className: "bg-[#DCFCE7] text-[#16A34A]", Icon: Check },
  in_progress: { className: "bg-[#FFEDD5] text-[#F97316]", Icon: Clock3 },
  submitted: { className: "bg-[#DBEAFE] text-[#2563EB]", Icon: Clock3 },
  not_started: { className: "bg-[#EFF6FF] text-[#2563EB]", Icon: Circle },
  needs_retry: { className: "bg-[#FEE2E2] text-[#DC2626]", Icon: Clock3 },
  failed: { className: "bg-[#FEE2E2] text-[#DC2626]", Icon: Clock3 },
}

const taskIconStyles = [
  { bg: "bg-[#22C55E]", Icon: Mountain },
  { bg: "bg-[#FB923C]", Icon: Frame },
  { bg: "bg-[#A855F7]", Icon: Mountain },
]

export function PracticeTaskItem({
  task,
  onClick,
  onRequestUpload,
  onRetryAttempt,
  onShowDemoAttempt,
  isUploading = false,
}: PracticeTaskItemProps) {
  const [expanded, setExpanded] = useState(false)
  const status = statusStyles[task.status] || {
    className: "bg-slate-100 text-slate-600",
    Icon: Check,
  }
  const StatusIcon = status.Icon
  const taskIdText = task.id || task.practice_task_id || ""
  const parsedTaskNumber = Number(taskIdText.match(/\d+/)?.[0])
  const taskNumber = Number.isFinite(parsedTaskNumber) && parsedTaskNumber > 0 ? parsedTaskNumber : 1
  const iconStyle = taskIconStyles[(taskNumber - 1) % taskIconStyles.length] ?? taskIconStyles[0]
  const TaskIcon = iconStyle.Icon

  const handleExpand = () => {
    setExpanded((current) => !current)
    onClick?.()
  }

  return (
    <div className="rounded-lg border border-[#E2E8F0] bg-white px-2.5 py-2 transition-colors hover:border-slate-300">
      <div
        className="grid min-h-[58px] cursor-pointer grid-cols-[1fr_170px_150px_112px_132px_24px] items-center gap-4"
        onClick={handleExpand}
      >
        <div className="flex items-center gap-3.5 min-w-0">
          <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-full ${iconStyle.bg}`}>
            <TaskIcon className="h-5 w-5 text-white" />
          </div>
          <div className="min-w-0">
            <p className="line-clamp-2 text-sm font-bold leading-snug text-[#0F172A]">{task.title}</p>
            <p className="mt-0.5 line-clamp-2 text-xs leading-relaxed text-[#64748B]">{task.description}</p>
          </div>
        </div>

        <p className="text-[13px] font-bold text-[#2563EB] truncate">{task.target}</p>
        <p className="truncate text-[13px] text-[#475569]">{task.problem}</p>

        <div
          className={`flex h-8 items-center justify-center gap-1.5 rounded-md px-3 text-xs font-bold ${status.className}`}
        >
          <StatusIcon className="h-3.5 w-3.5" />
          {task.statusLabel}
        </div>

        <button
          type="button"
          className={`flex h-8 cursor-pointer items-center justify-center gap-1.5 rounded-md border border-blue-200 bg-blue-50 px-3 text-xs font-bold text-blue-600 hover:bg-blue-100 ${
            isUploading ? "pointer-events-none opacity-60" : ""
          }`}
          onClick={(event) => {
            event.stopPropagation()
            onRequestUpload?.(task)
          }}
        >
          <Upload className="h-3.5 w-3.5" />
          {DEMO_MODE ? task.statusLabel === "已领取" ? "已领取练习" : "领取练习" : isUploading ? "上传中" : "上传练习照片"}
        </button>

        <ChevronRight
          className={`w-[17px] h-[17px] text-[#475569] shrink-0 transition-transform ${expanded ? "rotate-90" : ""}`}
        />
      </div>

      {expanded && (
        <div className="ml-[54px] mt-2 rounded-md border border-slate-100 bg-slate-50 p-3 text-xs leading-relaxed text-[#475569]">
          <p className="font-extrabold text-[#0F172A]">{task.title}</p>
          <p className="mt-1">{task.description}</p>
          {task.goal && (
            <p className="mt-2">
              <span className="font-bold text-[#0F172A]">练习目标：</span>
              {task.goal}
            </p>
          )}
          {task.target && (
            <p className="mt-1">
              <span className="font-bold text-[#0F172A]">关联问题：</span>
              {task.target}
            </p>
          )}
          {task.problem && (
            <p className="mt-1">
              <span className="font-bold text-[#0F172A]">对应问题：</span>
              {task.problem}
            </p>
          )}
        </div>
      )}

      <div className="ml-[54px] mt-2 border-t border-slate-100 pt-2">
        <PracticeAttemptList
          attempts={task.attempts}
          onRetry={(attempt) => onRetryAttempt?.(task, attempt)}
          onShowDemo={onShowDemoAttempt}
        />
      </div>
    </div>
  )
}
