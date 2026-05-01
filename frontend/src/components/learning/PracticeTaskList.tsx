import { NotebookPen, ChevronRight } from "lucide-react"
import { PracticeTaskItem, type PracticeAttempt, type PracticeTask } from "./PracticeTaskItem"

interface PracticeTaskListProps {
  tasks: PracticeTask[]
  onTaskClick?: (taskId: string) => void
  onRequestUpload?: (task: PracticeTask) => void
  onRetryAttempt?: (task: PracticeTask, attempt: PracticeAttempt) => void
  onShowDemoAttempt?: () => void
  uploadingTaskId?: string | null
}

export function PracticeTaskList({
  tasks,
  onTaskClick,
  onRequestUpload,
  onRetryAttempt,
  onShowDemoAttempt,
  uploadingTaskId,
}: PracticeTaskListProps) {
  return (
    <div className="rounded-[10px] border border-[#E2E8F0] bg-white p-[18px] space-y-3 flex-1">
      <div className="grid grid-cols-[1fr_170px_150px_112px_132px_24px] items-center gap-4">
        <div className="flex items-center gap-2.5">
          <NotebookPen className="w-5 h-5 text-[#0F172A]" />
          <h2 className="text-lg font-extrabold text-[#0F172A]">练习任务</h2>
        </div>
        <span className="text-xs text-[#475569]">关联目标/问题</span>
        <span className="text-xs text-[#475569]">对应问题</span>
        <span className="text-xs text-[#475569]">进度</span>
        <span className="text-xs text-[#475569]">提交练习</span>
        <span />
      </div>

      <div className="max-h-[258px] space-y-2 overflow-y-auto pr-1">
        {tasks.map((task) => (
          <PracticeTaskItem
            key={task.id}
            task={task}
            onClick={() => onTaskClick?.(task.id)}
            onRequestUpload={onRequestUpload}
            onRetryAttempt={onRetryAttempt}
            onShowDemoAttempt={onShowDemoAttempt}
            isUploading={uploadingTaskId === task.id}
          />
        ))}
      </div>

      <div className="text-center pt-1">
        <span className="text-sm text-[#334155] cursor-pointer hover:text-[#0F172A] transition-colors">
          查看全部练习任务 <ChevronRight className="w-4 h-4 inline" />
        </span>
      </div>
    </div>
  )
}
