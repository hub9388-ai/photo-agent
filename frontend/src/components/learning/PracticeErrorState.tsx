import { AlertTriangle, RotateCcw } from "lucide-react"
import type { LearningIssue } from "@/types/learning"

interface PracticeErrorStateProps {
  issue: LearningIssue
  onRetry?: () => void
  onDismiss?: () => void
}

export function PracticeErrorState({ issue, onRetry, onDismiss }: PracticeErrorStateProps) {
  return (
    <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
      <div className="flex items-start justify-between gap-3">
        <div className="flex gap-2">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <div>
            <p className="font-extrabold">{issue.title}</p>
            <p className="mt-1 leading-6">{issue.message}</p>
          </div>
        </div>
        <div className="flex shrink-0 gap-2">
          {onRetry ? (
            <button
              type="button"
              onClick={onRetry}
              className="inline-flex h-8 items-center gap-1.5 rounded-md border border-red-200 bg-white px-3 text-xs font-bold text-red-700 hover:bg-red-100"
            >
              <RotateCcw className="h-3.5 w-3.5" />
              {issue.retryLabel || "重试"}
            </button>
          ) : null}
          {onDismiss ? (
            <button
              type="button"
              onClick={onDismiss}
              className="h-8 rounded-md px-2 text-xs font-bold text-red-600 hover:bg-red-100"
            >
              关闭
            </button>
          ) : null}
        </div>
      </div>
    </div>
  )
}
