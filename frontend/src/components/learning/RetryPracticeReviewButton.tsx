import { RotateCcw } from "lucide-react"

interface RetryPracticeReviewButtonProps {
  disabled?: boolean
  onClick: () => void
}

export function RetryPracticeReviewButton({ disabled = false, onClick }: RetryPracticeReviewButtonProps) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className="inline-flex h-8 items-center gap-1.5 rounded-md border border-blue-200 bg-blue-50 px-3 text-xs font-bold text-blue-600 hover:bg-blue-100 disabled:pointer-events-none disabled:opacity-50"
    >
      <RotateCcw className="h-3.5 w-3.5" />
      重试 CoachAgent
    </button>
  )
}
