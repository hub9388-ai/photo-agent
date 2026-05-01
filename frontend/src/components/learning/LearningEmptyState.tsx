import Link from "next/link"
import { Camera, Sparkles } from "lucide-react"

interface LearningEmptyStateProps {
  onShowDemo?: () => void
}

export function LearningEmptyState({ onShowDemo }: LearningEmptyStateProps) {
  return (
    <div className="rounded-[10px] border border-dashed border-blue-300 bg-white p-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="space-y-2">
          <h2 className="text-xl font-extrabold text-[#0F172A]">还没有练习任务</h2>
          <p className="max-w-2xl text-sm leading-6 text-[#64748B]">
            完成一次照片分析后，学习教练会根据你的照片问题生成练习任务。
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link
            href="/analysis"
            className="inline-flex h-10 items-center gap-2 rounded-md bg-[#2563EB] px-4 text-sm font-bold text-white hover:bg-[#1D4ED8]"
          >
            <Camera className="h-4 w-4" />
            上传照片开始分析
          </Link>
          {onShowDemo ? (
            <button
              type="button"
              onClick={onShowDemo}
              className="inline-flex h-10 items-center gap-2 rounded-md border border-blue-200 bg-blue-50 px-4 text-sm font-bold text-blue-700 hover:bg-blue-100"
            >
              <Sparkles className="h-4 w-4" />
              查看示例练习
            </button>
          ) : null}
        </div>
      </div>
    </div>
  )
}
