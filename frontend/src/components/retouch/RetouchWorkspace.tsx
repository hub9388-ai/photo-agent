"use client"

import { useEffect, useEffectEvent, useRef, useState } from "react"
import { buildApiUrl, isMockMode } from "@/lib/api/client"
import { DEMO_MODE } from "@/lib/demo/config"
import { catCase } from "@/lib/demo/case"
import { demoAdvice, demoAsset } from "@/lib/demo/fixtures"
import { DEMO_ASSETS_KEY } from "@/lib/demo/api"

const EDITOR_URL = process.env.NEXT_PUBLIC_RETOUCH_URL || "http://localhost:7301"
const MAX_BYTES = 20 * 1024 * 1024
const ACCEPTED = ["image/jpeg", "image/png", "image/webp"]

export function RetouchWorkspace({ mediaId, jobId }: { mediaId?: string; jobId?: string }) {
  const frame = useRef<HTMLIFrameElement>(null)
  const activeRequest = useRef<string | null>(null)
  const attempted = useRef(false)
  const fileInput = useRef<HTMLInputElement>(null)
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const [busy, setBusy] = useState(false)
  const [pending, setPending] = useState(false)
  const [sourceNote, setSourceNote] = useState("")
  const [file, setFile] = useState<File | null>(null)
  const [status, setStatus] = useState(DEMO_MODE ? "正在加载编辑器，示例照片将自动载入。" : "请先启动修图服务，并在下方登录或注册修图账号；就绪后将自动载入所选照片。")
  const [attempt, setAttempt] = useState(0)
  const editor = new URL(EDITOR_URL)
  const editorOrigin = DEMO_MODE ? "" : editor.origin
  const importUrl = DEMO_MODE ? "/demo-editor/photoai-import" : new URL("/photoai-import", editorOrigin).href

  const send = useEffectEvent(async () => {
    if (activeRequest.current || attempted.current || (!file && !mediaId)) return
    attempted.current = true
    const requestId = crypto.randomUUID()
    activeRequest.current = requestId
    setPending(true)
    setBusy(true)
    setSourceNote("")
    try {
      let source = file
      let advice: unknown = undefined
      if (DEMO_MODE) {
        if (file) throw new Error("演示仅编辑预置猫图；自己的照片需启动完整服务。")
        const response = await fetch(catCase.original)
        source = new File([await response.blob()], "街角三花猫.png", { type: "image/png" })
        advice = demoAdvice()
        setSourceNote("已选择案例原图；自然语言圆润修改展示固定结果，本地调色可以实际操作。")
      }
      // Advice belongs to the analysed media, never to a locally overridden file.
      if (!DEMO_MODE && !file && mediaId && jobId) {
        const response = await fetch(buildApiUrl(`/api/jobs/${encodeURIComponent(jobId)}/retouch-advice?media_id=${encodeURIComponent(mediaId)}`), {
          signal: AbortSignal.timeout(15000),
        })
        if (!response.ok) throw new Error(`读取后期建议失败（${response.status}）。请确认该照片的 Post 分析已完成。`)
        advice = await response.json()
      }
      if (!source && mediaId) {
        if (isMockMode()) throw new Error("当前为演示模式，不能读取真实素材。请直接选择本地照片，或启用真实 API 模式。")
        const response = await fetch(buildApiUrl(`/api/media/${encodeURIComponent(mediaId)}/retouch-source`), {
          signal: AbortSignal.timeout(30000),
        })
        if (!response.ok) throw new Error(`读取素材失败（${response.status}），请重新选择本地照片。`)
        const blob = await response.blob()
        source = new File([blob], response.headers.get("X-Retouch-Filename") || "photoai-photo.jpg", { type: blob.type })
        if (response.headers.get("X-Retouch-Source") === "preview") {
          setSourceNote("本次导入的是 JPEG 预览图，不是 RAW 原文件。")
        } else {
          setSourceNote("本次导入使用原始图片文件。")
        }
      }
      if (!source) throw new Error("请选择一张照片。")
      if (!ACCEPTED.includes(source.type) || source.size > MAX_BYTES || source.size === 0) {
        throw new Error("请选择非空且不超过 20 MB 的 JPG、PNG 或 WebP 图片。")
      }
      // Navigation/unmount can finish while a source request is still in flight.
      if (activeRequest.current !== requestId) return
      frame.current?.contentWindow?.postMessage({
        type: "photoai:import", version: 1, requestId, file: source, advice,
      }, editorOrigin || window.location.origin)
      setStatus("正在上传照片并创建修图会话…")
      timer.current = setTimeout(() => {
        setBusy(false)
        // Retain the request ID: a slow response can still complete, but must not trigger a duplicate import.
        setStatus("导入耗时较长，请检查修图服务。若需重新发送，请先重新连接；已创建的会话可在修图历史中查看。")
      }, 60000)
    } catch (error) {
      if (activeRequest.current !== requestId) return
      activeRequest.current = null
      setPending(false)
      setBusy(false)
      setStatus(error instanceof Error ? error.message : "导入失败。")
    }
  })

  useEffect(() => {
    function receive(event: MessageEvent) {
      if (event.origin !== (editorOrigin || window.location.origin) || event.source !== frame.current?.contentWindow) return
      const data = event.data
      if (DEMO_MODE && data?.type === "photoai:demo-saved") {
        try {
          if (typeof data.dataUrl !== "string" || !data.dataUrl.startsWith("data:image/png;base64,") || data.dataUrl.length > 4_000_000) throw new Error("保存图片过大，请先导出下载。")
          const assets = JSON.parse(localStorage.getItem(DEMO_ASSETS_KEY) ?? "[]")
          localStorage.setItem(DEMO_ASSETS_KEY, JSON.stringify([{ ...demoAsset, asset_id: "demo-cat-edit", media_id: "demo-cat-edit", file_name: "三花猫-编辑版本.png", preview_url: data.dataUrl, metadata: { width: data.width, height: data.height }, ai_reasons: ["浏览器编辑版本，原图保留"], created_at: new Date().toISOString() }, ...assets.filter((asset: { asset_id: string }) => asset.asset_id !== "demo-cat-edit")]))
          setStatus("当前已应用的图片已保存到素材库，原图未覆盖。")
        } catch { setStatus("保存未完成，浏览器存储可能已满；请通过编辑器导出下载。") }
        return
      }
      if (DEMO_MODE && data?.type === "photoai:demo-save-error") { setStatus(data.message || "请先应用或取消调色预览，再保存当前版本。"); return }
      if (!data || data.version !== 1) return
      if (data.type === "photoai:ready") {
        if (!attempted.current) setStatus("修图工作台已就绪；所选照片将自动载入，也可上传照片直接修图。")
        void send()
      } else if (data.requestId === activeRequest.current &&
        (data.type === "photoai:imported" || data.type === "photoai:error")) {
        if (timer.current) clearTimeout(timer.current)
        activeRequest.current = null
        setPending(false)
        setBusy(false)
        if (data.type === "photoai:imported") {
          setStatus("照片已导入，下方可开始编辑。完成后可在编辑器导出图片。")
        } else {
          setStatus(typeof data.message === "string" ? data.message : "导入失败，请重试。")
        }
      }
    }
    window.addEventListener("message", receive)
    return () => {
      window.removeEventListener("message", receive)
      if (timer.current) clearTimeout(timer.current)
      activeRequest.current = null
    }
  }, [editorOrigin])

  function reconnect() {
    if (timer.current) clearTimeout(timer.current)
    activeRequest.current = null
    attempted.current = false
    setPending(false)
    setAttempt((value) => value + 1)
    setStatus(DEMO_MODE ? "正在重新载入示例照片。" : "正在连接编辑器；登录就绪后自动载入照片。")
  }

  return (
    <div className="space-y-4 p-5">
      <div>
        <h1 className="text-xl font-bold">照片修图工作台</h1>
        <p className="mt-1 text-sm text-slate-600">{DEMO_MODE ? "使用猫图案例体验原编辑器：调色、对比、撤销和导出；圆润修改展示预置生成结果。" : "选择照片，进入画布调整与编辑。自然语言修图是否可用取决于修图服务的模型配置。"}</p>
      </div>
      <div className="flex flex-wrap items-center gap-3 rounded-lg border bg-white p-4">
        <input ref={fileInput} className="hidden" type="file" accept="image/jpeg,image/png,image/webp" aria-label="选择修图照片"
          disabled={DEMO_MODE || pending} onChange={(event) => {
            const selected = event.target.files?.[0]
            event.target.value = ""
            if (!selected) return
            if (!ACCEPTED.includes(selected.type) || !selected.size || selected.size > MAX_BYTES) {
              setStatus("请选择非空且不超过 20 MB 的 JPG、PNG 或 WebP 图片。")
              return
            }
            setFile(selected)
            setSourceNote("")
            reconnect()
          }} />
        <button className="rounded bg-violet-700 px-4 py-2 text-sm text-white disabled:opacity-40"
          disabled={DEMO_MODE || pending} onClick={() => fileInput.current?.click()}>
          上传照片
        </button>
        {file && <span className="text-sm text-slate-600">{file.name}</span>}
        <button className="rounded border px-3 py-2 text-sm" disabled={busy} onClick={reconnect}>重新连接</button>
        <a href={importUrl} target="_blank" rel="noreferrer" className="text-sm text-violet-700 underline">独立打开修图服务</a>
        {DEMO_MODE && <><button className="rounded border px-3 py-2 text-sm text-violet-700" onClick={() => frame.current?.contentWindow?.postMessage({ type: "photoai:demo-save" }, window.location.origin)}>保存当前版本到素材库</button><a href="/assets/" className="text-sm text-violet-700 underline">查看素材库</a></>}
      </div>
      {DEMO_MODE ? <p className="text-sm text-slate-600">演示模式自动载入预置猫图；上传自己的照片需启动本地完整服务。</p> : mediaId && !file && <p className="text-sm text-slate-600">照片已从上一环节带入，编辑器就绪后自动载入，无需再次发送。RAW 等格式使用 JPEG 预览图。</p>}
      {jobId && <p className="text-sm text-violet-700">随素材照片载入 Post 调色建议，可在调色面板预览、微调，再点击应用。另选本地文件不会携带这些建议。</p>}
      <p role="status" className="rounded bg-slate-100 p-3 text-sm">{status}</p>
      {sourceNote && <p className="text-sm text-amber-700">{sourceNote}</p>}
      <iframe key={attempt} ref={frame} src={importUrl} title="AI 修图编辑器"
        className="h-[78vh] min-h-[600px] w-full rounded-lg border bg-white" />
      <p className="text-xs text-slate-500">{DEMO_MODE ? "演示复用原编辑器，图片和编辑记录保存在本浏览器。未准备的生成操作会明确提示，不修改当前图片。" : "修图能力来源：yuyuanweb/ai-picture-editor，独立服务接入。默认 mock 模式不代表真实 AI 修图效果。"}</p>
    </div>
  )
}
