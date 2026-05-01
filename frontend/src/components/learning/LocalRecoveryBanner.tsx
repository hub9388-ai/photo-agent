import { History } from "lucide-react"
import type { PracticeRecoveryRecord } from "@/types/learning"

interface LocalRecoveryBannerProps {
  record: PracticeRecoveryRecord
  onRestore: () => void
  onDiscard: () => void
}

export function LocalRecoveryBanner({ record, onRestore, onDiscard }: LocalRecoveryBannerProps) {
  return (
    <div className="flex items-center justify-between gap-4 rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-700">
      <div className="flex items-center gap-2">
        <History className="h-4 w-4 shrink-0" />
        <span className="font-medium">
          检测到一个未完成的练习提交
          {record.uploadedFileName ? `：${record.uploadedFileName}` : ""}，是否继续恢复？
        </span>
      </div>
      <div className="flex shrink-0 gap-2">
        <button
          type="button"
          onClick={onRestore}
          className="rounded-md bg-blue-600 px-3 py-1.5 text-xs font-bold text-white hover:bg-blue-700"
        >
          继续恢复
        </button>
        <button
          type="button"
          onClick={onDiscard}
          className="rounded-md border border-blue-200 bg-white px-3 py-1.5 text-xs font-bold text-blue-700 hover:bg-blue-100"
        >
          丢弃
        </button>
      </div>
    </div>
  )
}
