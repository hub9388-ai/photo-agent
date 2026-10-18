"use client"

import { useState } from "react"
import Image from "next/image"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Upload, Trash2 } from "lucide-react"

interface ExifData {
  iso?: string
  aperture?: string
  shutterSpeed?: string
  focalLength?: string
  cameraModel?: string
}

interface UploadPreviewPanelProps {
  images?: string[]
  fileName?: string
  currentIndex?: number
  onSelectImage?: (index: number) => void
  exif?: ExifData
  preference?: string
  onPreferenceChange?: (value: string) => void
  onRetake?: () => void
  onCancel?: () => void
}

export function UploadPreviewPanel({
  images = [],
  fileName,
  currentIndex = 0,
  onSelectImage,
  exif,
  preference: controlledPreference,
  onPreferenceChange,
  onRetake,
  onCancel,
}: UploadPreviewPanelProps) {
  const [localPreference, setLocalPreference] = useState("")
  const preference = controlledPreference ?? localPreference
  const maxChars = 200
  const previewImage = images[currentIndex] || images[0]

  const handlePreferenceChange = (value: string) => {
    const nextValue = value.slice(0, maxChars)
    if (controlledPreference === undefined) {
      setLocalPreference(nextValue)
    }
    onPreferenceChange?.(nextValue)
  }

  return (
    <Card className="h-full min-h-0 overflow-hidden flex flex-col">
      <CardHeader className="pb-3 shrink-0">
        <CardTitle className="text-lg font-bold text-slate-900">上传与预览</CardTitle>
      </CardHeader>
      <CardContent className="flex-1 min-h-0 space-y-4 overflow-y-auto">
        <div className="aspect-[4/3] rounded-lg overflow-hidden relative">
          {previewImage ? (
            <Image
              src={previewImage}
              alt={fileName || "上传照片预览"}
              fill
              unoptimized
              className="object-cover"
            />
          ) : (
            <div className="absolute inset-0 flex items-center justify-center bg-slate-100 text-sm text-slate-500">
              暂无照片预览
            </div>
          )}
        </div>

        {/* Thumbnails */}
        <div className="grid grid-cols-3 gap-2">
          {images.slice(0, 3).map((image, index) => (
            <div
              key={image || index}
              onClick={() => onSelectImage?.(index)}
              className={`relative aspect-square rounded-lg flex items-end justify-center p-2 cursor-pointer transition-all overflow-hidden ${
                index === currentIndex
                  ? "bg-blue-100 border-2 border-blue-500"
                  : "bg-slate-100 border-2 border-transparent"
              }`}
            >
              {image ? (
                <Image
                  src={image}
                  alt={`${fileName || "preview"} ${index + 1}`}
                  fill
                  unoptimized
                  className="object-cover"
                />
              ) : (
                <span className={`text-sm font-bold ${index === currentIndex ? "text-blue-600" : "text-slate-600"}`}>
                  {index + 1}
                </span>
              )}
            </div>
          ))}
        </div>

        {/* EXIF Info */}
        <div className="rounded-lg bg-slate-50 p-3.5 space-y-2">
          <p className="text-sm font-bold text-slate-900">EXIF 信息 ⓘ</p>
          <p className="text-sm text-slate-500">
            ISO {exif?.iso ?? "未知"} / {exif?.aperture ?? "未知"} / {exif?.shutterSpeed ?? "未知"} / {exif?.focalLength ?? "未知"}
          </p>
        </div>

        {/* Preferences */}
        <div className="rounded-lg bg-slate-50 p-3.5 space-y-2.5">
          <p className="text-sm font-bold text-slate-700">分析偏好（可选）</p>
          <div className="rounded-md border border-slate-300 bg-white p-3">
            <textarea
              className="w-full h-14 text-sm bg-transparent resize-none focus:outline-none text-slate-400 placeholder:text-slate-400"
              placeholder="例如：偏好风光片的色彩增强，保留天空细节"
              value={preference}
              onChange={(e) => handlePreferenceChange(e.target.value)}
            />
          </div>
        </div>

        {/* Actions */}
        <div className="grid grid-cols-2 gap-2.5">
          <Button
            variant="outline"
            className="h-9.5 bg-slate-50 border-slate-300 text-slate-700 hover:bg-slate-100"
            onClick={onRetake}
          >
            <Upload className="w-4 h-4 mr-1.5" />
            重新上传
          </Button>
          <Button
            variant="outline"
            className="h-9.5 bg-red-50 border-red-300 text-red-600 hover:bg-red-100 hover:text-red-700"
            onClick={onCancel}
          >
            <Trash2 className="w-4 h-4 mr-1.5" />
            取消任务
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}

export function UploadPlaceholder({
  onUpload,
  onFileSelect,
  isUploading = false,
}: {
  onUpload?: () => void
  onFileSelect?: (file: File) => void
  isUploading?: boolean
}) {
  const inputId = "photo-upload-input"

  return (
    <div className="max-w-2xl mx-auto">
      <label
        htmlFor={inputId}
        className="block border-2 border-dashed border-slate-300 rounded-xl p-12 text-center hover:border-slate-400 transition-colors cursor-pointer"
        onClick={onUpload}
      >
        <input
          id={inputId}
          type="file"
          accept="image/*,.heic,.heif,.raw,.dng,.arw,.cr2,.nef"
          className="hidden"
          disabled={isUploading}
          onChange={(event) => {
            const file = event.target.files?.[0]
            if (file) {
              onFileSelect?.(file)
            }
          }}
        />
        <div className="w-16 h-16 rounded-full bg-slate-100 flex items-center justify-center mx-auto mb-4">
          <Upload className="w-8 h-8 text-slate-400" />
        </div>
        <h3 className="text-lg font-medium text-slate-900 mb-2">
          {isUploading ? "正在上传并生成预览..." : "点击选择照片上传"}
        </h3>
        <p className="text-sm text-slate-500">
          支持 JPG、PNG、HEIC、RAW 格式，上传后自动生成预览和 EXIF 信息
        </p>
      </label>
    </div>
  )
}
