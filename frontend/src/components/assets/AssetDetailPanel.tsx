"use client"

import { useState } from "react"
import Link from "next/link"
import { ChevronLeft, ChevronRight, ImageOff, Pin, Send, Star, X } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { formatExif, gradeLabel } from "@/lib/assets"
import type { AssetItem } from "@/types/assets"

interface AssetDetailPanelProps {
  asset?: AssetItem | null
  currentIndex?: number
  totalCount?: number
  onPrev?: () => void
  onNext?: () => void
  onFavorite?: () => void
  onClose?: () => void
  onSendToPost?: () => void
  onSendToCoach?: () => void
}

export function AssetDetailPanel({
  asset,
  currentIndex = 0,
  totalCount = 0,
  onPrev,
  onNext,
  onFavorite,
  onClose,
  onSendToPost,
  onSendToCoach,
}: AssetDetailPanelProps) {
  const [failedAssetId, setFailedAssetId] = useState<string | null>(null)

  if (!asset) {
    return (
      <Card className="h-full min-h-[420px] flex items-center justify-center">
        <div className="text-center">
          <ImageOff className="mx-auto h-10 w-10 text-slate-300" />
          <p className="mt-3 text-sm font-bold text-slate-700">请选择一张素材查看详情。</p>
          <p className="mt-1 text-xs text-slate-500">选中素材后会展示 EXIF、评分、问题标签和 handoff 上下文。</p>
        </div>
      </Card>
    )
  }

  const metadata = asset.metadata || {}
  const showImage = asset.preview_url && failedAssetId !== asset.asset_id
  const hasExposureExif = Boolean(metadata.iso || metadata.aperture || metadata.shutter || metadata.focal_length)
  const cameraText = metadata.camera || "相机型号未读取"
  const exifStatusText = hasExposureExif
    ? metadata.camera
      ? "已读取曝光参数和相机型号"
      : "已读取曝光参数；相机型号未读取"
    : metadata.camera
      ? "已读取相机型号；曝光参数缺失"
      : "未读取到 EXIF 曝光参数"

  return (
    <Card className="h-full flex flex-col">
      <CardHeader className="pb-3 flex flex-row items-center justify-between shrink-0">
        <CardTitle className="text-base font-extrabold">选中素材详情</CardTitle>
        <div className="flex items-center gap-1 text-sm text-slate-500">
          <button
            type="button"
            onClick={onPrev}
            disabled={!onPrev || totalCount <= 1}
            className="p-1 hover:bg-slate-100 rounded disabled:cursor-not-allowed disabled:opacity-40"
            aria-label="上一张素材"
          >
            <ChevronLeft className="w-4 h-4" />
          </button>
          <span>{Math.max(1, currentIndex)} / {Math.max(totalCount, 1)}</span>
          <button
            type="button"
            onClick={onNext}
            disabled={!onNext || totalCount <= 1}
            className="p-1 hover:bg-slate-100 rounded disabled:cursor-not-allowed disabled:opacity-40"
            aria-label="下一张素材"
          >
            <ChevronRight className="w-4 h-4" />
          </button>
          <button onClick={onFavorite} className="p-1 hover:bg-slate-100 rounded">
            <Pin className="w-4 h-4" />
          </button>
          <button onClick={onClose} className="p-1 hover:bg-slate-100 rounded">
            <X className="w-4 h-4" />
          </button>
        </div>
      </CardHeader>

      <CardContent className="space-y-3 flex-1 overflow-y-auto">
        <div className="flex gap-3">
          {showImage ? (
            <img
              src={asset.preview_url || ""}
              alt={asset.file_name}
              className="w-32 h-24 rounded-lg object-cover flex-shrink-0 bg-slate-100"
              onError={() => setFailedAssetId(asset.asset_id)}
            />
          ) : (
            <div className="flex w-32 h-24 shrink-0 flex-col items-center justify-center rounded-lg bg-slate-100 text-[11px] font-bold text-slate-400">
              <ImageOff className="mb-1 h-5 w-5" />
              预览图不可用
            </div>
          )}

          <div className="flex-1 space-y-1.5 text-sm min-w-0">
            <p className="font-extrabold text-slate-900 truncate">
              {gradeLabel(asset.grade)}   {asset.file_name}  <Star className="w-3.5 h-3.5 inline text-slate-400" />
            </p>
            <p className="text-xs text-slate-500 truncate">media_id：{asset.media_id || "未生成"}</p>
            <p className="text-xs text-slate-500">{metadata.captured_at || asset.created_at || "拍摄时间未知"}</p>
            <p className="text-xs text-slate-500">{metadata.location || "地点未知"}</p>
            <p className="text-xs text-slate-500">
              {metadata.width && metadata.height ? `${metadata.width} × ${metadata.height}` : "分辨率未知"}
            </p>
            <p className="text-xs text-slate-500 font-bold">{asset.tags.slice(0, 3).join("  ")}</p>
          </div>
        </div>

        <div className="p-3 bg-slate-50 rounded-lg space-y-1">
          <p className="text-sm font-extrabold text-slate-900">EXIF</p>
          <p className="text-xs text-slate-500">{formatExif(metadata)}</p>
          <p className="text-xs text-slate-500">{cameraText}</p>
          <p className="text-xs text-slate-500">{exifStatusText}</p>
          {!hasExposureExif ? (
            <p className="text-xs text-amber-600">该素材仍可用于后期分析和学习反馈。</p>
          ) : null}
        </div>

        {typeof asset.score === "number" && (
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-sm font-extrabold text-slate-900">质量评分</span>
              <span className="text-sm font-extrabold text-slate-900">{asset.score} / 100</span>
            </div>
            <div className="h-1.5 bg-slate-200 rounded-full overflow-hidden">
              <div
                className="h-full bg-green-500 rounded-full"
                style={{ width: `${asset.score}%` }}
              />
            </div>
          </div>
        )}

        <div className="space-y-1">
          <p className="text-sm font-bold text-slate-900">AI 判断标签</p>
          <div className="flex flex-wrap gap-1.5">
            {asset.tags.map((tag) => (
              <span key={tag} className="rounded bg-green-50 px-2 py-1 text-xs font-bold text-green-600">
                {tag}
              </span>
            ))}
          </div>
        </div>

        {asset.issues?.length ? (
          <div className="space-y-1">
            <p className="text-sm font-bold text-slate-900">问题标签</p>
            <div className="flex flex-wrap gap-1.5">
              {asset.issues.map((issue) => (
                <span key={issue} className="rounded bg-amber-50 px-2 py-1 text-xs font-bold text-amber-600">
                  {issue}
                </span>
              ))}
            </div>
          </div>
        ) : null}

        <div className="space-y-1">
          <p className="text-sm font-bold text-slate-900">AI 筛选说明</p>
          <p className="text-xs text-slate-600 leading-relaxed">
            {asset.ai_reasons.join("；") || "当前分档基于轻量规则，完整 AssetAgent 索引后续接入。"}
          </p>
        </div>

        <div className="p-3 bg-slate-50 rounded-lg border border-slate-200 space-y-2">
          <p className="text-sm font-extrabold text-slate-900">Handoff 上下文</p>
          <p className="text-xs text-slate-500 leading-relaxed">
            当前素材可发送至 PostAgent 或 CoachAgent；上下文会携带分档、评分和筛选理由。
          </p>
          <div className="flex flex-wrap gap-2">
            {asset.media_id && asset.upload_status !== "failed" && (
              <Link href={`/retouch?media_id=${encodeURIComponent(asset.media_id)}`}
                className="inline-flex h-8 items-center rounded border border-violet-200 bg-violet-50 px-3 text-xs font-bold text-violet-700">
                进入修图
              </Link>
            )}
            <button
              type="button"
              onClick={onSendToPost}
              className="inline-flex h-8 items-center gap-1 rounded border border-blue-200 bg-blue-50 px-3 text-xs font-bold text-blue-600 hover:bg-blue-100"
            >
              <Send className="h-3.5 w-3.5" />
              送去后期
            </button>
            <button
              type="button"
              onClick={onSendToCoach}
              className="inline-flex h-8 items-center gap-1 rounded border border-green-200 bg-green-50 px-3 text-xs font-bold text-green-600 hover:bg-green-100"
            >
              <Send className="h-3.5 w-3.5" />
              送去学习
            </button>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
