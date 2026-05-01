"use client"

import { ChangeEvent, DragEvent, useRef, useState } from "react"
import { CloudUpload, Loader2 } from "lucide-react"

interface AssetUploadZoneProps {
  onUpload?: (files: File[]) => void
  isUploading?: boolean
  uploadSummary?: string | null
}

export function AssetUploadZone({ onUpload, isUploading = false, uploadSummary }: AssetUploadZoneProps) {
  const inputRef = useRef<HTMLInputElement | null>(null)
  const [isDragging, setIsDragging] = useState(false)

  const submitFiles = (files: FileList | File[]) => {
    const nextFiles = Array.from(files).filter((file) => file.type.startsWith("image/") || /\.(heic|heif|raw|dng|arw|cr2|cr3|nef)$/i.test(file.name))
    if (nextFiles.length) onUpload?.(nextFiles)
  }

  const handleFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    if (event.target.files) submitFiles(event.target.files)
    event.target.value = ""
  }

  const handleDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault()
    setIsDragging(false)
    submitFiles(event.dataTransfer.files)
  }

  return (
    <div
      className={`rounded-xl border p-5 text-center transition-colors cursor-pointer bg-white ${
        isDragging ? "border-blue-500 bg-blue-50" : "border-slate-300 hover:border-slate-400"
      }`}
      onClick={() => inputRef.current?.click()}
      onDragOver={(event) => {
        event.preventDefault()
        setIsDragging(true)
      }}
      onDragLeave={() => setIsDragging(false)}
      onDrop={handleDrop}
    >
      <div className="flex items-center justify-center gap-2.5 mb-1"
      >
        {isUploading ? (
          <Loader2 className="w-5 h-5 text-blue-600 animate-spin" />
        ) : (
          <CloudUpload className="w-5 h-5 text-slate-700" />
        )}
        <h3 className="text-lg font-extrabold text-slate-900">
          {isUploading ? "正在上传素材..." : "点击上传照片"}
        </h3>
      </div>
      <p className="text-xs text-slate-500">
        支持 JPG、PNG、HEIC、RAW 格式，单次最多 50 张；当前以文件选择上传为主
      </p>
      {uploadSummary ? <p className="mt-2 text-xs font-bold text-blue-600">{uploadSummary}</p> : null}
      <input
        ref={inputRef}
        type="file"
        multiple
        accept="image/*,.heic,.heif,.raw,.dng,.arw,.cr2,.cr3,.nef"
        className="hidden"
        onChange={handleFileChange}
      />
    </div>
  )
}
