"use client"

import { useEffect, useRef, useState } from "react"
import { buildApiUrl, isMockMode } from "@/lib/api/client"

const EDITOR_URL = process.env.NEXT_PUBLIC_RETOUCH_URL || "http://localhost:7301"
const MAX_BYTES = 20 * 1024 * 1024
const ACCEPTED = ["image/jpeg", "image/png", "image/webp"]

export function RetouchWorkspace({ mediaId, jobId }: { mediaId?: string; jobId?: string }) {
  const frame = useRef<HTMLIFrameElement>(null)
  const activeRequest = useRef<string | null>(null)
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const [ready, setReady] = useState(false)
  const [busy, setBusy] = useState(false)
  const [pending, setPending] = useState(false)
  const [sourceNote, setSourceNote] = useState("")
  const [file, setFile] = useState<File | null>(null)
  const [status, setStatus] = useState("请先启动修图服务，并在下方登录或注册修图账号。")
  const [attempt, setAttempt] = useState(0)
  const editor = new URL(EDITOR_URL)
  const editorOrigin = editor.origin
  const importUrl = new URL("/photoai-import", editorOrigin).href

  useEffect(() => {
    function receive(event: MessageEvent) {
      if (event.origin !== editorOrigin || event.source !== frame.current?.contentWindow) return
      const data = event.data
      if (!data || data.version !== 1) return
      if (data.type === "photoai:ready") {
        setReady(true)
        setStatus("修图工作台已就绪，请选择照片并点击发送。")
      } else if (data.requestId === activeRequest.current &&
        (data.type === "photoai:imported" || data.type === "photoai:error")) {
        if (timer.current) clearTimeout(timer.current)
        activeRequest.current = null
        setPending(false)
        setBusy(false)
        if (data.type === "photoai:imported") {
          setReady(false)
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
    }
  }, [editorOrigin])

  async function send() {
    if (!ready || activeRequest.current) return
    const requestId = crypto.randomUUID()
    activeRequest.current = requestId
    setPending(true)
    setBusy(true)
    setSourceNote("")
    try {
      let source = file
      let advice: unknown = undefined
      // Advice belongs to the analysed media, never to a locally overridden file.
      if (!file && mediaId && jobId) {
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
      frame.current?.contentWindow?.postMessage({
        type: "photoai:import", version: 1, requestId, file: source, advice,
      }, editorOrigin)
      setStatus("正在上传照片并创建修图会话…")
      timer.current = setTimeout(() => {
        setBusy(false)
        // Retain the request ID: a slow response can still complete, but must not trigger a duplicate import.
        setStatus("导入耗时较长，请检查修图服务。若需重新发送，请先重新连接；已创建的会话可在修图历史中查看。")
      }, 60000)
    } catch (error) {
      activeRequest.current = null
      setPending(false)
      setBusy(false)
      setStatus(error instanceof Error ? error.message : "导入失败。")
    }
  }

  return (
    <div className="space-y-4 p-5">
      <div>
        <h1 className="text-xl font-bold">照片修图工作台</h1>
        <p className="mt-1 text-sm text-slate-600">选择照片，进入画布调整与编辑。自然语言修图是否可用取决于修图服务的模型配置。</p>
      </div>
      <div className="flex flex-wrap items-center gap-3 rounded-lg border bg-white p-4">
        <input type="file" accept="image/jpeg,image/png,image/webp" aria-label="选择修图照片"
          disabled={busy} onChange={(event) => setFile(event.target.files?.[0] || null)} />
        <button className="rounded bg-violet-700 px-4 py-2 text-sm text-white disabled:opacity-40"
          disabled={!ready || pending || (!file && !mediaId)} onClick={send}>
          {busy ? "正在导入…" : file ? "发送所选照片" : "发送素材库照片"}
        </button>
        <button className="rounded border px-3 py-2 text-sm" disabled={busy} onClick={() => {
          if (timer.current) clearTimeout(timer.current)
          activeRequest.current = null
          setPending(false)
          setReady(false)
          setAttempt((value) => value + 1)
          setStatus("正在重新连接；请检查下方账号状态。")
        }}>重新连接</button>
        <a href={importUrl} target="_blank" rel="noreferrer" className="text-sm text-violet-700 underline">独立打开修图服务</a>
      </div>
      {mediaId && <p className="text-sm text-slate-600">已选择素材库照片；若另选本地文件，将优先发送本地文件。RAW 等格式使用 JPEG 预览图。</p>}
      {jobId && <p className="text-sm text-violet-700">随素材照片载入 Post 调色建议，可在调色面板预览、微调，再点击应用。另选本地文件不会携带这些建议。</p>}
      <p role="status" className="rounded bg-slate-100 p-3 text-sm">{status}</p>
      {sourceNote && <p className="text-sm text-amber-700">{sourceNote}</p>}
      <iframe key={attempt} ref={frame} src={importUrl} title="AI 修图编辑器"
        className="h-[78vh] min-h-[600px] w-full rounded-lg border bg-white" />
      <p className="text-xs text-slate-500">修图能力来源：yuyuanweb/ai-picture-editor，独立服务接入。默认 mock 模式不代表真实 AI 修图效果。</p>
    </div>
  )
}
