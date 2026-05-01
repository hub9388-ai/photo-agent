import { AlertCircle, CheckCircle2, Clock3 } from "lucide-react"
import type { PracticeAttempt } from "@/types/learning"

const statusCopy: Record<PracticeAttempt["status"], { label: string; className: string; icon: typeof CheckCircle2 }> = {
  uploading: { label: "上传中", className: "bg-blue-50 text-blue-600", icon: Clock3 },
  uploaded: { label: "已上传", className: "bg-blue-50 text-blue-600", icon: CheckCircle2 },
  job_created: { label: "任务已创建", className: "bg-blue-50 text-blue-600", icon: Clock3 },
  reviewing: { label: "复盘中", className: "bg-blue-50 text-blue-600", icon: Clock3 },
  completed: { label: "已完成", className: "bg-green-50 text-green-600", icon: CheckCircle2 },
  needs_retry: { label: "需复练", className: "bg-amber-50 text-amber-600", icon: AlertCircle },
  failed: { label: "失败", className: "bg-red-50 text-red-600", icon: AlertCircle },
  archive_failed: { label: "归档失败", className: "bg-red-50 text-red-600", icon: AlertCircle },
}

interface PracticeResultCardProps {
  attempt: PracticeAttempt
  index: number
  onRetry?: (attempt: PracticeAttempt) => void
  onShowDemo?: () => void
}

export function PracticeResultCard({ attempt, index, onRetry, onShowDemo }: PracticeResultCardProps) {
  const meta = statusCopy[attempt.status]
  const Icon = meta.icon
  const isProblem = attempt.status === "failed" || attempt.status === "archive_failed" || attempt.status === "needs_retry"

  return (
    <div className="rounded-md border border-slate-200 bg-white p-3 text-xs text-[#475569]">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="font-extrabold text-[#0F172A]">
            尝试 {index + 1}
            {attempt.fileName || attempt.mediaId ? `：${attempt.fileName || attempt.mediaId}` : ""}
          </p>
          <p className="mt-1 leading-5">
            {attempt.feedbackSummary ||
              attempt.visibleText ||
              (attempt.status === "reviewing" ? "CoachAgent 正在复盘练习照片。" : "本次复盘结果为文本反馈，未包含完整结构化评分。")}
          </p>
          {!attempt.structuredPayload && attempt.status === "completed" ? (
            <p className="mt-1 text-amber-600">本次复盘未提供结构化评分，已使用文本反馈兜底展示。</p>
          ) : null}
        </div>
        <span className={`inline-flex shrink-0 items-center gap-1 rounded px-2 py-0.5 font-bold ${meta.className}`}>
          <Icon className="h-3.5 w-3.5" />
          {meta.label}
        </span>
      </div>
      {isProblem ? (
        <div className="mt-2 flex flex-wrap gap-2">
          {onRetry ? (
            <button
              type="button"
              onClick={() => onRetry(attempt)}
              className="rounded border border-blue-200 bg-blue-50 px-2 py-1 font-bold text-blue-600 hover:bg-blue-100"
            >
              重试复盘
            </button>
          ) : null}
          {onShowDemo ? (
            <button
              type="button"
              onClick={onShowDemo}
              className="rounded border border-slate-200 bg-slate-50 px-2 py-1 font-bold text-slate-600 hover:bg-slate-100"
            >
              查看示例复盘
            </button>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}
