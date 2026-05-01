import { ChangeEvent, useState } from "react"
import { AlertTriangle, Upload, X } from "lucide-react"
import type { PracticeTask } from "@/types/learning"

interface PracticeUploadDialogProps {
  task: PracticeTask | null
  isOpen: boolean
  isSubmitting?: boolean
  errorMessage?: string | null
  onClose: () => void
  onSubmit: (task: PracticeTask, file: File) => void
}

export function PracticeUploadDialog({
  task,
  isOpen,
  isSubmitting = false,
  errorMessage,
  onClose,
  onSubmit,
}: PracticeUploadDialogProps) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null)

  if (!isOpen || !task) return null

  const handleFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    setSelectedFile(event.target.files?.[0] || null)
  }

  const submit = () => {
    if (selectedFile) onSubmit(task, selectedFile)
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/35 p-4">
      <div className="w-full max-w-lg rounded-xl bg-white p-5 shadow-xl">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h3 className="text-lg font-extrabold text-[#0F172A]">上传练习照片</h3>
            <p className="mt-1 text-sm leading-6 text-[#64748B]">{task.goal}</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={isSubmitting}
            className="rounded-md p-1 text-slate-500 hover:bg-slate-100"
            aria-label="关闭"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <label className="mt-4 flex min-h-[150px] cursor-pointer flex-col items-center justify-center rounded-lg border border-dashed border-blue-300 bg-blue-50/50 px-4 text-center hover:bg-blue-50">
          <Upload className="h-8 w-8 text-blue-600" />
          <span className="mt-2 text-sm font-bold text-[#0F172A]">
            {selectedFile ? selectedFile.name : "点击选择练习照片"}
          </span>
          <span className="mt-1 text-xs text-[#64748B]">支持 JPG / PNG / HEIC / RAW，上传后会创建学习复盘任务</span>
          <input
            type="file"
            accept="image/*,.heic,.heif,.raw,.dng,.arw,.cr2,.nef"
            className="hidden"
            disabled={isSubmitting}
            onChange={handleFileChange}
          />
        </label>

        {errorMessage ? (
          <div className="mt-3 flex gap-2 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
            <span>{errorMessage}</span>
          </div>
        ) : null}

        <div className="mt-5 flex justify-end gap-2">
          <button
            type="button"
            disabled={isSubmitting}
            onClick={onClose}
            className="h-10 rounded-md border border-slate-200 px-4 text-sm font-bold text-[#334155] hover:bg-slate-50 disabled:opacity-60"
          >
            取消
          </button>
          <button
            type="button"
            disabled={!selectedFile || isSubmitting}
            onClick={submit}
            className="h-10 rounded-md bg-[#2563EB] px-4 text-sm font-bold text-white hover:bg-[#1D4ED8] disabled:pointer-events-none disabled:opacity-60"
          >
            {isSubmitting ? "提交中..." : "提交复盘"}
          </button>
        </div>
      </div>
    </div>
  )
}
