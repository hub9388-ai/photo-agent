import type { PracticeAttempt } from "@/types/learning"
import { PracticeResultCard } from "./PracticeResultCard"

interface PracticeAttemptListProps {
  attempts: PracticeAttempt[]
  onRetry?: (attempt: PracticeAttempt) => void
  onShowDemo?: () => void
}

export function PracticeAttemptList({ attempts, onRetry, onShowDemo }: PracticeAttemptListProps) {
  if (!attempts.length) {
    return (
      <div className="rounded-md border border-dashed border-slate-200 bg-slate-50 p-3 text-xs text-[#64748B]">
        还没有提交练习照片。点击“上传练习照片”后，学习教练会把复盘结果归档到这里。
      </div>
    )
  }

  return (
    <div className="space-y-2">
      {attempts.slice(0, 5).map((attempt, index) => (
        <PracticeResultCard
          key={attempt.attemptId}
          attempt={attempt}
          index={index}
          onRetry={onRetry}
          onShowDemo={onShowDemo}
        />
      ))}
    </div>
  )
}
