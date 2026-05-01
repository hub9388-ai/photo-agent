"use client"

import { useState } from "react"
import { Card, CardContent } from "@/components/ui/card"
import { ChevronDown, ChevronRight, FolderOpen, Trash2 } from "lucide-react"

export interface Folder {
  id: string
  name: string
  count: number
  isExpanded?: boolean
  canRename?: boolean
  canDelete?: boolean
  children?: Folder[]
}

interface AssetSidebarProps {
  folders: Folder[]
  stats: {
    gradeA: number
    gradeB: number
    gradeC: number
    rejected: number
    duplicate: number
  }
  selectedFolder?: string | null
  onSelectFolder?: (id: string) => void
  onToggleFolder?: (id: string) => void
  onRenameFolder?: (id: string, name: string) => void
  onDeleteFolder?: (id: string) => void
  onCreateFolder?: () => void
}

export function AssetSidebar({
  folders,
  stats,
  selectedFolder,
  onSelectFolder,
  onToggleFolder,
  onRenameFolder,
  onDeleteFolder,
  onCreateFolder,
}: AssetSidebarProps) {
  const [editingFolderId, setEditingFolderId] = useState<string | null>(null)
  const [folderNameDraft, setFolderNameDraft] = useState("")

  const startRename = (folder: Folder) => {
    setEditingFolderId(folder.id)
    setFolderNameDraft(folder.name)
  }

  const saveRename = () => {
    if (editingFolderId) {
      onRenameFolder?.(editingFolderId, folderNameDraft.trim())
    }
    setEditingFolderId(null)
  }

  const renderFolder = (folder: Folder, depth = 0) => {
    const isSelected = selectedFolder === folder.id
    const hasChildren = Boolean(folder.children?.length)
    const isEditing = editingFolderId === folder.id

    return (
      <div key={folder.id}>
        <div
          className={`group flex items-center gap-2 text-sm py-1 cursor-pointer rounded px-1 ${
            isSelected ? "text-slate-900 font-extrabold bg-slate-50" : depth ? "text-slate-500" : "text-slate-700"
          }`}
          style={{ paddingLeft: depth ? `${depth * 14 + 4}px` : undefined }}
          onClick={() => onSelectFolder?.(folder.id)}
        >
          {hasChildren ? (
            <button
              type="button"
              className="rounded p-0.5 hover:bg-slate-100"
              aria-label={folder.isExpanded ? "收起文件夹" : "展开文件夹"}
              onClick={(event) => {
                event.stopPropagation()
                onToggleFolder?.(folder.id)
              }}
            >
              {folder.isExpanded ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
            </button>
          ) : (
            <FolderOpen className="w-3.5 h-3.5" />
          )}
          {isEditing ? (
            <input
              value={folderNameDraft}
              autoFocus
              maxLength={28}
              className="min-w-0 flex-1 rounded border border-blue-300 px-1 text-sm font-bold outline-none"
              onChange={(event) => setFolderNameDraft(event.target.value)}
              onBlur={saveRename}
              onClick={(event) => event.stopPropagation()}
              onKeyDown={(event) => {
                if (event.key === "Enter") saveRename()
                if (event.key === "Escape") setEditingFolderId(null)
              }}
            />
          ) : (
            <>
              <span className="flex-1 truncate">
                {folder.name} ({folder.count})
              </span>
              {folder.canRename ? (
                <button
                  type="button"
                  className="opacity-0 group-hover:opacity-100 text-slate-400 hover:text-blue-600"
                  aria-label={`重命名 ${folder.name}`}
                  onClick={(event) => {
                    event.stopPropagation()
                    startRename(folder)
                  }}
                >
                  ✎
                </button>
              ) : null}
              {folder.canDelete ? (
                <button
                  type="button"
                  className="opacity-0 group-hover:opacity-100 text-slate-400 hover:text-red-600"
                  aria-label={`删除 ${folder.name}`}
                  onClick={(event) => {
                    event.stopPropagation()
                    onDeleteFolder?.(folder.id)
                  }}
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              ) : null}
            </>
          )}
        </div>
        {folder.isExpanded && folder.children?.length ? (
          <div className="mt-1 space-y-1">{folder.children.map((child) => renderFolder(child, depth + 1))}</div>
        ) : null}
      </div>
    )
  }

  return (
    <Card className="h-full">
      <CardContent className="p-4 space-y-3">
        {folders.map((folder) => renderFolder(folder))}

        <button
          type="button"
          className="w-full rounded-md border border-dashed border-slate-300 px-3 py-2 text-sm font-bold text-slate-600 hover:border-blue-300 hover:bg-blue-50 hover:text-blue-700"
          onClick={onCreateFolder}
        >
          + 新建文件夹
        </button>

        {/* Smart Groups */}
        <div className="pt-2 border-t border-slate-100 space-y-2"
        >
          <p className="text-sm font-extrabold text-slate-900"
          >智能分组</p>
          <div className="space-y-1.5"
          >
            <div className="flex items-center gap-2 text-sm text-green-600 font-extrabold py-0.5 cursor-pointer hover:bg-green-50 rounded px-1"
            >
              <span>☆</span>
              <span>A 精选 ({stats.gradeA})</span>
            </div>
            <div className="flex items-center gap-2 text-sm text-blue-600 font-extrabold py-0.5 cursor-pointer hover:bg-blue-50 rounded px-1"
            >
              <span>◎</span>
              <span>B 可用 ({stats.gradeB})</span>
            </div>
            <div className="flex items-center gap-2 text-sm text-orange-600 font-extrabold py-0.5 cursor-pointer hover:bg-orange-50 rounded px-1"
            >
              <span>○</span>
              <span>C 待定 ({stats.gradeC})</span>
            </div>
            <div className="flex items-center gap-2 text-sm text-red-600 font-extrabold py-0.5 cursor-pointer hover:bg-red-50 rounded px-1"
            >
              <span>×</span>
              <span>淘汰 ({stats.rejected})</span>
            </div>
            <div className="flex items-center gap-2 text-sm text-purple-600 font-extrabold py-0.5 cursor-pointer hover:bg-purple-50 rounded px-1"
            >
              <span>◇</span>
              <span>重复组 ({stats.duplicate})</span>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
