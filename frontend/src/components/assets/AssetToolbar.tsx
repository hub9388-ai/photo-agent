"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import {
  Sparkles,
  Grid3X3,
  List,
  Search,
  Calendar,
} from "lucide-react"
import type { AssetFilter } from "@/types/assets"

export interface AssetStats {
  total: number
  gradeA: number
  gradeB: number
  gradeC: number
  rejected: number
  duplicate: number
}

interface AssetToolbarProps {
  stats: AssetStats
  projectTitle?: string
  projectDescription?: string
  onProjectTitleChange?: (title: string) => void
  onImportProject?: () => void
  searchQuery?: string
  onSearchChange?: (query: string) => void
  selectedGrade?: AssetFilter["grade"]
  onSelectGrade?: (grade: AssetFilter["grade"]) => void
  gridFilter?: string
  onGridFilterChange?: (filter: string) => void
  dateFilter?: string
  dateOptions?: Array<{ key: string; label: string; count: number }>
  onDateFilterChange?: (filter: string) => void
  sortBy?: AssetFilter["sort_by"]
  onSortChange?: (sortBy: AssetFilter["sort_by"]) => void
  viewMode?: "grid" | "list"
  onViewModeChange?: (mode: "grid" | "list") => void
}

const gradeOptions = [
  { key: "all", label: "全部" },
  { key: "A", label: "A 档", countKey: "gradeA", color: "text-green-600" },
  { key: "B", label: "B 档", countKey: "gradeB", color: "text-blue-600" },
  { key: "C", label: "C 档", countKey: "gradeC", color: "text-orange-600" },
  { key: "reject", label: "淘汰", countKey: "rejected", color: "text-red-600" },
  { key: "duplicate", label: "重复", countKey: "duplicate", color: "text-purple-600" },
] satisfies Array<{ key: AssetFilter["grade"]; label: string; countKey?: keyof AssetStats; color?: string }>

const sortOptions: Array<{ key: AssetFilter["sort_by"]; label: string }> = [
  { key: "created_at", label: "上传时间" },
  { key: "score", label: "评分" },
  { key: "file_name", label: "文件名" },
]

const gridFilterOptions = [
  { key: "all", label: "全部网格" },
  { key: "landscape", label: "横图" },
  { key: "portrait", label: "竖图" },
  { key: "warm", label: "暖色" },
  { key: "cool", label: "冷色" },
  { key: "has_exif", label: "EXIF 完整" },
  { key: "missing_exif", label: "EXIF 缺失" },
  { key: "duplicate", label: "重复组" },
]

export function AssetToolbar({
  stats,
  projectTitle = "素材库",
  projectDescription = "当前分档由 AssetAgent 图像理解评分生成，完整项目索引后续可接入后台素材库。",
  onProjectTitleChange,
  onImportProject,
  searchQuery = "",
  onSearchChange,
  selectedGrade = "all",
  onSelectGrade,
  gridFilter = "all",
  onGridFilterChange,
  dateFilter = "all",
  dateOptions = [],
  onDateFilterChange,
  sortBy = "created_at",
  onSortChange,
  viewMode = "grid",
  onViewModeChange,
}: AssetToolbarProps) {
  const sortLabel = sortOptions.find((option) => option.key === sortBy)?.label || "上传时间"
  const [isEditingTitle, setIsEditingTitle] = useState(false)
  const [titleDraft, setTitleDraft] = useState(projectTitle)
  const visibleDateOptions = dateOptions.length ? dateOptions : [{ key: "all", label: "全部日期", count: stats.total }]

  const startTitleEdit = () => {
    setTitleDraft(projectTitle)
    setIsEditingTitle(true)
  }

  const saveTitle = () => {
    const nextTitle = titleDraft.trim()
    onProjectTitleChange?.(nextTitle)
    setIsEditingTitle(false)
  }

  return (
    <>
      {/* Project Summary Card */}
      <div className="rounded-xl border border-slate-200 bg-white p-5 flex items-center justify-between">
        <div>
          {isEditingTitle ? (
            <div className="flex items-center gap-2">
              <input
                value={titleDraft}
                autoFocus
                maxLength={40}
                className="h-9 w-80 rounded-md border border-blue-300 px-3 text-xl font-extrabold text-slate-900 outline-none ring-2 ring-blue-100"
                onChange={(event) => setTitleDraft(event.target.value)}
                onBlur={saveTitle}
                onKeyDown={(event) => {
                  if (event.key === "Enter") saveTitle()
                  if (event.key === "Escape") setIsEditingTitle(false)
                }}
              />
              <span className="text-xs text-slate-400">Enter 保存 / Esc 取消</span>
            </div>
          ) : (
            <h1 className="text-xl font-extrabold text-slate-900 flex items-center gap-2">
              {projectTitle}
              <button
                type="button"
                className="text-slate-400 hover:text-blue-600"
                aria-label="修改素材库名称"
                onClick={startTitleEdit}
              >
                ✎
              </button>
            </h1>
          )}
          <p className="text-xs text-slate-500 mt-1">
            {projectDescription} ⓘ
          </p>
        </div>
        <div className="flex gap-10 text-center">
          <div>
            <p className="text-xl font-extrabold text-slate-900">{stats.total}</p>
            <p className="text-xs text-slate-500">总素材</p>
          </div>
          <div>
            <p className="text-xl font-extrabold text-green-700">{stats.gradeA}</p>
            <p className="text-xs text-slate-500">A 精选</p>
          </div>
          <div>
            <p className="text-xl font-extrabold text-slate-700">{stats.gradeB}</p>
            <p className="text-xs text-slate-500">B 可用</p>
          </div>
          <div>
            <p className="text-xl font-extrabold text-slate-600">{stats.gradeC}</p>
            <p className="text-xs text-slate-500">C 待定</p>
          </div>
          <div>
            <p className="text-xl font-extrabold text-red-600">{stats.rejected}</p>
            <p className="text-xs text-slate-500">淘汰</p>
          </div>
          <div>
            <p className="text-xl font-extrabold text-purple-600">{stats.duplicate}</p>
            <p className="text-xs text-slate-500">重复组</p>
          </div>
        </div>
      </div>

      {/* Toolbar */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Button className="h-9 gap-2 bg-slate-900 hover:bg-slate-800 text-white" onClick={onImportProject}>
            <Sparkles className="w-4 h-4" />
            导入项目
          </Button>
          <select
            value={gridFilter}
            onChange={(event) => onGridFilterChange?.(event.target.value)}
            className="h-9 rounded-md border border-slate-300 bg-white px-3 text-sm font-bold text-slate-700 shadow-sm"
            aria-label="网格筛选"
          >
            {gridFilterOptions.map((option) => (
              <option key={option.key} value={option.key}>
                网格：{option.label}
              </option>
            ))}
          </select>
          <div className="relative">
            <Calendar className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-500" />
            <select
              value={dateFilter}
              onChange={(event) => onDateFilterChange?.(event.target.value)}
              className="h-9 rounded-md border border-slate-300 bg-white pl-9 pr-3 text-sm font-bold text-slate-700 shadow-sm"
              aria-label="日期筛选"
            >
              {visibleDateOptions.map((option) => (
                <option key={option.key} value={option.key}>
                  {option.label}（{option.count}）
                </option>
              ))}
            </select>
          </div>
        </div>
        <div className="relative w-80">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <input
            type="text"
            placeholder="搜索文件名 / 拍摄地点 / 备注..."
            className="w-full pl-10 pr-4 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            value={searchQuery}
            onChange={(e) => onSearchChange?.(e.target.value)}
          />
        </div>
      </div>

      {/* Filter Tabs + Sort/View */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-5">
          {gradeOptions.map((option) => (
            <button
              key={option.key ?? "all"}
              onClick={() => onSelectGrade?.(option.key)}
              className={`text-sm font-extrabold transition-colors ${
                selectedGrade === option.key
                  ? "text-slate-900"
                  : option.color || "text-slate-500"
              } ${selectedGrade === option.key && option.key === "all" ? "px-4 py-1.5 bg-slate-900 text-white rounded-full" : ""}`}
            >
              {option.label}
              {option.countKey && (
                <span className="ml-2 text-slate-400 font-normal">
                  {stats[option.countKey]}
                </span>
              )}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2">
          <select
            value={sortBy}
            onChange={(event) => onSortChange?.(event.target.value as AssetFilter["sort_by"])}
            className="h-8 rounded-md border border-slate-300 bg-white px-3 text-sm font-bold text-slate-700"
          >
            {sortOptions.map((option) => (
              <option key={option.key} value={option.key}>
                排序：{option.label}
              </option>
            ))}
          </select>
          <span className="sr-only">当前排序：{sortLabel}</span>
          <button
            onClick={() => onViewModeChange?.("grid")}
            className={`w-8 h-8 rounded-md flex items-center justify-center transition-colors ${
              viewMode === "grid" ? "bg-slate-900 text-white" : "bg-white border border-slate-300 text-slate-500"
            }`}
          >
            <Grid3X3 className="w-4 h-4" />
          </button>
          <button
            onClick={() => onViewModeChange?.("list")}
            className={`w-8 h-8 rounded-md flex items-center justify-center transition-colors ${
              viewMode === "list" ? "bg-slate-900 text-white" : "bg-white border border-slate-300 text-slate-500"
            }`}
          >
            <List className="w-4 h-4" />
          </button>
        </div>
      </div>
    </>
  )
}
