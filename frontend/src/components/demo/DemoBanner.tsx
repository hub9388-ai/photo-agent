"use client"

import { useEffect } from "react"
import { seedDemoAssets } from "@/lib/demo/api"

export function DemoBanner() {
  useEffect(() => { try { seedDemoAssets() } catch { /* Private mode can still browse the case. */ } }, [])
  return <div className="flex flex-wrap items-center justify-between gap-2 border-b border-blue-100 bg-blue-50 px-5 py-2 text-xs leading-6 text-blue-800">
    <span>演示模式 · 保留产品操作流程，分析与生成使用预置案例；调色、保存和导出可实际体验。</span>
    <button className="shrink-0 rounded border border-blue-200 bg-white px-3" onClick={async () => {
      if (!window.confirm("重置此浏览器的演示记录、素材与编辑版本？")) return
      for (const key of Object.keys(localStorage)) if (key.startsWith("photoai.demo.")) localStorage.removeItem(key)
      for (const key of Object.keys(sessionStorage)) if (key.startsWith("photoai.demo.") || key === "photoai:post-advice:demo-editor-cat") sessionStorage.removeItem(key)
      await new Promise<void>(resolve => { const request = indexedDB.deleteDatabase("photoai.demo.editor.v2"); request.onsuccess = () => resolve(); request.onerror = () => resolve(); request.onblocked = () => resolve() })
      window.location.href = "/"
    }}>重置体验</button>
  </div>
}
