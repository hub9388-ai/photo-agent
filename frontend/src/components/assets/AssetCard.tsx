"use client"

import { useState } from "react"
import { Check, ImageOff, Star } from "lucide-react"
import { Card, CardContent } from "@/components/ui/card"
import { formatExif, gradeLabel } from "@/lib/assets"
import type { AssetGrade, AssetItem } from "@/types/assets"

interface AssetCardProps {
  asset: AssetItem
  isActive?: boolean
  isChecked?: boolean
  onClick?: () => void
  onToggleSelect?: () => void
}

const gradeBadgeMap: Record<AssetGrade, { bg: string; label: string }> = {
  A: { bg: "bg-green-500", label: "A档" },
  B: { bg: "bg-blue-500", label: "B档" },
  C: { bg: "bg-orange-400", label: "C档" },
  reject: { bg: "bg-red-500", label: "淘汰" },
  duplicate: { bg: "bg-purple-500", label: "重复" },
  unscored: { bg: "bg-slate-500", label: "未评分" },
}

export function AssetCard({
  asset,
  isActive = false,
  isChecked = false,
  onClick,
  onToggleSelect,
}: AssetCardProps) {
  const [imageFailed, setImageFailed] = useState(false)
  const badge = gradeBadgeMap[asset.grade]
  const borderClass = isActive ? "border-2 border-blue-500" : "border border-slate-200"
  const showImage = asset.preview_url && !imageFailed

  return (
    <Card
      data-asset-id={asset.asset_id}
      className={`cursor-pointer transition-shadow hover:shadow-md overflow-hidden ${borderClass}`}
      onClick={onClick}
    >
      <div className="aspect-[4/3] relative overflow-hidden bg-slate-100">
        {showImage ? (
          <img
            src={asset.preview_url || ""}
            alt={asset.file_name}
            className="w-full h-full object-cover"
            onError={() => setImageFailed(true)}
          />
        ) : (
          <div className="flex h-full w-full flex-col items-center justify-center gap-2 bg-slate-100 text-xs font-bold text-slate-400">
            <ImageOff className="h-8 w-8" />
            预览图不可用
          </div>
        )}

        <div className="absolute top-2 left-2 flex items-center gap-1">
          <button
            type="button"
            aria-label={`选择 ${asset.file_name}`}
            className={`w-4 h-4 rounded-sm flex items-center justify-center border ${
              isChecked ? "bg-blue-500 border-blue-500" : "bg-white/90 border-white"
            }`}
            onClick={(event) => {
              event.stopPropagation()
              onToggleSelect?.()
            }}
          >
            {isChecked ? <Check className="w-3 h-3 text-white" strokeWidth={3} /> : null}
          </button>
          <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold text-white ${badge.bg}`}>
            {badge.label}
          </span>
        </div>

        <button
          type="button"
          className="absolute top-2 right-2 p-0.5 rounded hover:bg-black/20 transition-colors"
          onClick={(event) => event.stopPropagation()}
        >
          <Star className={`w-3.5 h-3.5 ${asset.grade === "A" ? "text-yellow-400 fill-yellow-400" : "text-white drop-shadow-sm"}`} />
        </button>

        {typeof asset.score === "number" ? (
          <span className="absolute bottom-2 right-2 rounded bg-black/60 px-1.5 py-0.5 text-[10px] font-bold text-white">
            {asset.score}
          </span>
        ) : null}
      </div>

      <CardContent className="p-3 space-y-1.5">
        <div className="flex items-center gap-2">
          <p className="text-sm font-bold text-slate-900 truncate">{asset.file_name}</p>
          {asset.upload_status === "failed" ? (
            <span className="shrink-0 rounded bg-red-50 px-1.5 py-0.5 text-[10px] font-bold text-red-600">失败</span>
          ) : null}
        </div>
        <p className="text-xs text-slate-500 truncate">{formatExif(asset.metadata)}</p>
        <p className="text-xs font-bold truncate">
          {asset.tags.slice(0, 3).map((tag, index) => (
            <span key={`${asset.asset_id}_${tag}`} className={asset.grade === "reject" ? "text-red-600" : "text-green-600"}>
              {tag}
              {index < Math.min(asset.tags.length, 3) - 1 ? <span className="text-slate-300 font-normal mx-1.5">·</span> : null}
            </span>
          ))}
          {asset.duplicate_group_id ? (
            <span className="ml-1 text-purple-600">{gradeLabel("duplicate")}</span>
          ) : null}
        </p>
      </CardContent>
    </Card>
  )
}
