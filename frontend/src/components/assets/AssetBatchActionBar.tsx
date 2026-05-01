"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"

export type MoveTarget = {
  id: string
  name: string
  count: number
}

interface AssetBatchActionBarProps {
  selectedCount: number
  isSubmitting?: boolean
  statusMessage?: string | null
  errorMessage?: string | null
  lastJobId?: string | null
  moveTargets?: MoveTarget[]
  onClearSelection?: () => void
  onSendToPost?: () => void
  onSendToCoach?: () => void
  onMarkFavorite?: () => void
  onMarkIgnore?: () => void
  onMoveToFolder?: (folderId: string) => void
  onDeleteSelected?: () => void
  onViewJob?: () => void
}

export function AssetBatchActionBar({
  selectedCount,
  isSubmitting = false,
  statusMessage,
  errorMessage,
  lastJobId,
  moveTargets = [],
  onClearSelection,
  onSendToPost,
  onSendToCoach,
  onMarkFavorite,
  onMarkIgnore,
  onMoveToFolder,
  onDeleteSelected,
  onViewJob,
}: AssetBatchActionBarProps) {
  const [isMoreOpen, setIsMoreOpen] = useState(false)

  if (selectedCount === 0) {
    return (<div className="h-14" />)
  }

  return (
    <>
      <div className="fixed bottom-0 left-0 right-0 bg-white border-t border-slate-200 p-3 flex items-center justify-between z-40">
        <div className="flex items-center gap-4">
          <span className="text-sm font-extrabold text-slate-900">
            已选择 {selectedCount} 张
          </span>
          {isSubmitting ? <span className="text-xs font-bold text-blue-600">正在发送 Agent...</span> : null}
          {statusMessage ? <span className="text-xs font-bold text-green-600">{statusMessage}</span> : null}
          {errorMessage ? <span className="text-xs font-bold text-red-600">{errorMessage}</span> : null}
          {lastJobId ? (
            <button className="text-xs font-bold text-blue-600 hover:text-blue-700" onClick={onViewJob}>
              查看任务
            </button>
          ) : null}
          <button
            className="text-sm text-slate-500 hover:text-slate-700"
            onClick={onClearSelection}
          >
            清空选择
          </button>
        </div>
        <div className="flex items-center gap-3">
          <Button
            variant="outline"
            className="h-9 px-4 text-xs font-extrabold text-blue-600 bg-blue-50 border-blue-200 hover:bg-blue-100 leading-tight"
            onClick={onSendToPost}
            disabled={isSubmitting}
          >
            送去后期
            <br />
            PostAgent
          </Button>
          <Button
            variant="outline"
            className="h-9 px-4 text-xs font-extrabold text-green-600 bg-green-50 border-green-200 hover:bg-green-100 leading-tight"
            onClick={onSendToCoach}
            disabled={isSubmitting}
          >
            送去学习
            <br />
            CoachAgent
          </Button>
          <Button
            variant="outline"
            className="h-9 px-4 text-sm font-extrabold text-orange-600 bg-orange-50 border-orange-200 hover:bg-orange-100"
            onClick={onMarkFavorite}
            disabled={isSubmitting}
          >
            标记精选
          </Button>
          <Button
            variant="outline"
            className="h-9 px-4 text-sm font-bold text-slate-600 bg-slate-50 border-slate-300 hover:bg-slate-100"
            onClick={onMarkIgnore}
            disabled={isSubmitting}
          >
            忽略清理
          </Button>
          <div className="relative">
            <Button
              variant="outline"
              className="h-9 px-4 text-sm font-bold text-slate-700 border-slate-300"
              onClick={() => setIsMoreOpen((current) => !current)}
            >
              更多操作 ▼
            </Button>
            {isMoreOpen ? (
              <div className="absolute bottom-11 right-0 z-50 w-64 rounded-lg border border-slate-200 bg-white p-2 shadow-xl">
                <p className="px-2 pb-2 text-xs font-extrabold text-slate-500">移动照片到</p>
                <div className="max-h-56 overflow-y-auto">
                  {moveTargets.map((target) => (
                    <button
                      key={target.id}
                      type="button"
                      className="flex w-full items-center justify-between rounded-md px-2 py-2 text-left text-sm font-bold text-slate-700 hover:bg-blue-50 hover:text-blue-700"
                      onClick={() => {
                        onMoveToFolder?.(target.id)
                        setIsMoreOpen(false)
                      }}
                    >
                      <span className="truncate">{target.name}</span>
                      <span className="ml-3 shrink-0 text-xs text-slate-400">{target.count}</span>
                    </button>
                  ))}
                  {!moveTargets.length ? (
                    <p className="px-2 py-2 text-xs text-slate-500">暂无可移动的文件夹，请先新建文件夹。</p>
                  ) : null}
                </div>
                <div className="mt-2 border-t border-slate-100 pt-2">
                  <button
                    type="button"
                    className="flex w-full items-center justify-between rounded-md px-2 py-2 text-left text-sm font-extrabold text-red-600 hover:bg-red-50"
                    onClick={() => {
                      onDeleteSelected?.()
                      setIsMoreOpen(false)
                    }}
                  >
                    <span>删除所选照片</span>
                    <span className="text-xs font-bold text-red-400">{selectedCount}</span>
                  </button>
                </div>
              </div>
            ) : null}
          </div>
        </div>
      </div>

      {/* Spacer for fixed bottom bar */}
      <div className="h-14" />
    </>
  )
}
