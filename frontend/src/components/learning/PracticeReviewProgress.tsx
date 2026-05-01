import { Loader2 } from "lucide-react"

interface PracticeReviewProgressProps {
  message: string
}

export function PracticeReviewProgress({ message }: PracticeReviewProgressProps) {
  return (
    <div className="flex items-center gap-2 rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm font-medium text-blue-700">
      <Loader2 className="h-4 w-4 animate-spin" />
      <span>{message}</span>
    </div>
  )
}
