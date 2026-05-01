"use client"

import { ChevronDown, FolderOpen } from "lucide-react"
import { AssetCard } from "./AssetCard"
import type { AssetItem } from "@/types/assets"

export interface AssetGroup {
  id: string
  name: string
  assets: AssetItem[]
  isSimilarGroup?: boolean
}

interface AssetGridProps {
  groups: AssetGroup[]
  activeAssetId?: string | null
  selectedAssetIds?: string[]
  onSelectAsset?: (id: string) => void
  onToggleAsset?: (id: string) => void
  columns?: 3 | 4
}

export function AssetGrid({
  groups,
  activeAssetId,
  selectedAssetIds = [],
  onSelectAsset,
  onToggleAsset,
  columns = 3,
}: AssetGridProps) {
  const gridCols = columns === 4 ? "grid-cols-2 xl:grid-cols-4" : "grid-cols-2 xl:grid-cols-3"

  if (!groups.length || groups.every((group) => group.assets.length === 0)) {
    return (
      <div className="flex h-full min-h-[420px] flex-col items-center justify-center rounded-xl border border-dashed border-slate-300 bg-white text-center">
        <FolderOpen className="h-10 w-10 text-slate-300" />
        <h3 className="mt-3 text-lg font-extrabold text-slate-900">还没有素材</h3>
        <p className="mt-1 text-sm text-slate-500">上传一组照片，开始 AI 筛片与素材管理。</p>
      </div>
    )
  }

  return (
    <div className="space-y-5 h-full">
      {groups.map((group) => (
        <div key={group.id}>
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-base font-extrabold text-slate-900">
              {group.name} ({group.assets.length}张)
              {group.isSimilarGroup && <span className="text-slate-400 ml-1 text-sm font-normal">ⓘ</span>}
            </h3>
            {group.isSimilarGroup && (
              <button className="text-xs text-slate-500 hover:text-slate-700 flex items-center gap-1">
                展开全部
                <ChevronDown className="w-3 h-3" />
              </button>
            )}
          </div>
          <div className={`grid ${gridCols} gap-3.5`}>
            {group.assets.map((asset) => (
              <AssetCard
                key={asset.asset_id}
                asset={asset}
                isActive={activeAssetId === asset.asset_id}
                isChecked={selectedAssetIds.includes(asset.asset_id)}
                onClick={() => onSelectAsset?.(asset.asset_id)}
                onToggleSelect={() => onToggleAsset?.(asset.asset_id)}
              />
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}
