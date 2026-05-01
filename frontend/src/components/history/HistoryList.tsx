import Link from "next/link"
import { Button } from "@/components/ui/button"
import { HistoryTaskItem, type HistoryTask } from "./HistoryTaskItem"
import { Camera, ChevronRight, Info, Loader2 } from "lucide-react"

interface PaginationInfo {
  currentPage: number
  totalPages: number
  pageSize: number
  totalItems: number
}

interface HistoryListProps {
  tasks: HistoryTask[]
  pagination: PaginationInfo
  onPageChange?: (page: number) => void
  onPageSizeChange?: (size: number) => void
  onTaskView?: (taskId: string) => void
  onTaskRetry?: (taskId: string) => void
  onTaskReanalyze?: (taskId: string) => void
  isLoading?: boolean
  emptyTitle?: string
  emptyDescription?: string
}

export function HistoryList({
  tasks,
  pagination,
  onPageChange,
  onPageSizeChange,
  onTaskView,
  onTaskRetry,
  onTaskReanalyze,
  isLoading = false,
  emptyTitle = "还没有历史任务",
  emptyDescription = "上传一张照片，开始第一次 Post + Coach 智能分析。",
}: HistoryListProps) {
  const { currentPage, totalPages, pageSize } = pagination

  // Generate page numbers to display
  const getPageNumbers = () => {
    const pages: (number | string)[] = []
    if (totalPages <= 7) {
      for (let i = 1; i <= totalPages; i++) pages.push(i)
    } else {
      if (currentPage <= 3) {
        pages.push(1, 2, 3, 4, "...", totalPages)
      } else if (currentPage >= totalPages - 2) {
        pages.push(1, "...", totalPages - 3, totalPages - 2, totalPages - 1, totalPages)
      } else {
        pages.push(1, "...", currentPage - 1, currentPage, currentPage + 1, "...", totalPages)
      }
    }
    return pages
  }

  return (
    <div className="space-y-6">
      <div className="space-y-2.5">
        {isLoading && (
          <div className="flex h-[180px] items-center justify-center rounded-[9px] border border-[#E2E8F0] bg-white text-[#64748B]">
            <Loader2 className="mr-2 h-5 w-5 animate-spin" />
            正在加载历史任务...
          </div>
        )}

        {!isLoading && tasks.map((task) => (
          <HistoryTaskItem
            key={task.id}
            task={task}
            onView={() => onTaskView?.(task.id)}
            onRetry={() => onTaskRetry?.(task.id)}
            onRerun={() => onTaskReanalyze?.(task.id)}
          />
        ))}
        {!isLoading && tasks.length === 0 && (
          <div className="flex h-[220px] flex-col items-center justify-center rounded-[9px] border border-dashed border-[#CBD5E1] bg-white text-center">
            <h3 className="text-xl font-extrabold text-[#0F172A]">{emptyTitle}</h3>
            <p className="mt-2 text-sm text-[#64748B]">{emptyDescription}</p>
            <Link
              href="/analysis"
              className="mt-5 inline-flex h-10 items-center gap-2 rounded-md bg-[#2563EB] px-4 text-sm font-bold text-white hover:bg-[#1D4ED8]"
            >
              <Camera className="h-4 w-4" />
              上传照片开始分析
            </Link>
          </div>
        )}
      </div>

      <div className="relative flex h-10 items-center">
        <div className="absolute left-1 flex items-center gap-2 text-sm text-[#64748B]">
          <Info className="h-4 w-4" />
          <span>任务历史由 Job + Result 持久化存储，安全可靠，永不丢失</span>
        </div>

        <div className="mx-auto flex items-center gap-2.5">
          <Button
            variant="outline"
            className="h-10 w-[84px] rounded-[7px] border-[#CBD5E1] bg-white text-sm font-normal text-[#334155] shadow-none"
            disabled={currentPage <= 1}
            onClick={() => onPageChange?.(currentPage - 1)}
          >
            上一页
          </Button>

          {getPageNumbers().map((page, index) =>
            page === "..." ? (
              <span key={`ellipsis-${index}`} className="px-1 text-sm text-[#64748B]">
                ...
              </span>
            ) : (
              <Button
                key={page}
                variant="outline"
                className={
                  currentPage === page
                    ? "h-10 w-[46px] rounded-[7px] border-[#0F172A] bg-[#0F172A] text-sm font-extrabold text-white shadow-none hover:bg-[#0F172A]"
                    : "h-10 w-[46px] rounded-[7px] border-[#CBD5E1] bg-white text-sm text-[#334155] shadow-none"
                }
                onClick={() => onPageChange?.(page as number)}
              >
                {page}
              </Button>
            )
          )}

          <Button
            variant="outline"
            className="h-10 w-[84px] rounded-[7px] border-[#CBD5E1] bg-white text-sm font-normal text-[#334155] shadow-none"
            disabled={currentPage >= totalPages}
            onClick={() => onPageChange?.(currentPage + 1)}
          >
            下一页
          </Button>
        </div>

        <Button
          variant="outline"
          className="absolute right-0 h-10 w-[110px] justify-center gap-2 rounded-[7px] border-[#CBD5E1] bg-white text-sm font-normal text-[#334155] shadow-none"
          onClick={() => onPageSizeChange?.(pageSize === 10 ? 20 : 10)}
        >
          {pageSize} 条/页
          <ChevronRight className="h-4 w-4 rotate-90" />
        </Button>
      </div>
    </div>
  )
}

export type { HistoryTask, PaginationInfo }
