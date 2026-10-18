"use client"

import Image from "next/image"
import { useState } from "react"
import { Download, RotateCcw, Save, Sparkles } from "lucide-react"
import { adjustmentFilter, catCase, controls, neutral, suggested, type Adjustments } from "@/lib/demo/case"
import type { DemoSession, Snapshot } from "@/lib/demo/state"
import { buttonClass, DemoLink, panelClass, secondaryClass } from "./DemoUI"

export function DemoPhoto({ source, adjustments = neutral, className = "" }: { source: "original" | "rounded"; adjustments?: Adjustments; className?: string }) {
  return <Image unoptimized src={source === "rounded" ? catCase.rounded : catCase.original} width={768} height={1024} alt={source === "rounded" ? "三花猫圆润后的预置生成效果" : "街角三花猫原图"} className={className} style={{ filter: adjustmentFilter(adjustments) }} />
}

export function DemoRetouch({ session }: { session: DemoSession }) {
  const current = session.state.current
  const [draftState, setDraftState] = useState<{ base: Snapshot; values: Adjustments }>({ base: current, values: current.adjustments })
  const draft = draftState.base === current ? draftState.values : current.adjustments
  function setDraft(next: Adjustments | ((previous: Adjustments) => Adjustments)) {
    setDraftState(previous => ({ base: current, values: typeof next === "function" ? next(previous.base === current ? previous.values : current.adjustments) : next }))
  }
  const [compare, setCompare] = useState(false)
  const [message, setMessage] = useState("")
  const [exporting, setExporting] = useState(false)
  const dirty = controls.some(c => draft[c.key] !== current.adjustments[c.key])
  async function download() {
    setExporting(true)
    setMessage("")
    try {
      const image = new window.Image()
      image.src = current.rounded ? catCase.rounded : catCase.original
      await image.decode()
      const canvas = document.createElement("canvas")
      canvas.width = image.naturalWidth
      canvas.height = image.naturalHeight
      const context = canvas.getContext("2d")
      if (!context || !("filter" in context)) throw new Error("当前浏览器不支持调色导出，请使用新版 Chrome 或 Edge。")
      context.filter = adjustmentFilter(current.adjustments)
      context.drawImage(image, 0, 0)
      const blob = await new Promise<Blob>((resolve, reject) => canvas.toBlob(value => value ? resolve(value) : reject(new Error("图片导出失败，请重试。")), "image/png"))
      const url = URL.createObjectURL(blob)
      const link = document.createElement("a")
      link.href = url
      link.download = `photoai-cat-${current.rounded ? "rounded" : "original"}.png`
      link.click()
      window.setTimeout(() => URL.revokeObjectURL(url), 1000)
      setMessage("已导出当前应用的版本；未应用的滑杆修改不会写入图片。")
    } catch (error) { setMessage(error instanceof Error ? error.message : "图片导出失败，请重试。") }
    finally { setExporting(false) }
  }
  return <>
    <div className="flex flex-wrap items-center justify-between gap-3"><p className="text-sm text-slate-600">{catCase.title} · 768 × 1024 · 原图保留</p><div className="flex flex-wrap gap-2"><button className={secondaryClass} disabled={!session.state.undo.length} onClick={() => { const previous = session.state.undo.at(-1); if (previous) setDraft(previous.adjustments); session.undo(); setMessage("已撤销上一步，保存到素材库的快照不变。") }}><RotateCcw className="h-4 w-4" />撤销</button><button className={secondaryClass} disabled={dirty} onClick={() => { session.setState(previous => ({ ...previous, saved: previous.current })); setMessage("已保存独立版本，可在素材库查看。") }}><Save className="h-4 w-4" />保存到素材库</button><button className={buttonClass} disabled={dirty || exporting} onClick={download}><Download className="h-4 w-4" />{exporting ? "导出中…" : "导出 PNG"}</button></div></div>
    <div className="grid items-start gap-5 lg:grid-cols-[minmax(0,1fr)_330px]">
      <section className={`${panelClass} space-y-4`}>
        <div className="flex flex-wrap items-center justify-between gap-3"><h2 className="font-semibold">{compare ? "原图" : current.rounded ? "圆润效果" : dirty ? "调色预览" : "当前版本"}</h2><button className={secondaryClass} aria-pressed={compare} onClick={() => setCompare(value => !value)}>{compare ? "返回编辑效果" : "查看原图对比"}</button></div>
        <div className="flex min-h-80 items-center justify-center overflow-hidden rounded-xl bg-slate-100 p-3"><DemoPhoto source={compare || !current.rounded ? "original" : "rounded"} adjustments={compare ? neutral : draft} className="max-h-[580px] w-auto max-w-full object-contain" /></div>
        <div className="flex gap-3">{(["original", "rounded"] as const).map(source => <div key={source} className={`rounded-lg border p-1 ${current.rounded === (source === "rounded") ? "border-blue-400" : "border-slate-200"}`}><DemoPhoto source={source} className="h-20 w-16 rounded object-cover" /><p className="mt-1 text-center text-xs text-slate-500">{source === "original" ? "原图" : "预置效果"}</p></div>)}</div>
        {dirty && <p className="text-sm text-amber-800">当前是未应用的预览，请先应用调色再保存或导出。</p>}
        {message && <p role="status" className="rounded-lg bg-blue-50 p-3 text-sm leading-6 text-blue-900">{message}</p>}
      </section>
      <aside className="space-y-5">
        <section className={panelClass}><h2 className="mb-2 font-semibold">调色 · 浏览器实时预览</h2><p className="mb-4 text-xs leading-6 text-slate-500">支持亮度、对比度、饱和度。演示初值为近似建议；无摄影软件参数等价承诺。</p><button className={`${secondaryClass} mb-4 w-full`} onClick={() => { setDraft(suggested); setCompare(false); setMessage("已载入案例 Post 的演示初值，请预览、微调后应用。") }}>载入 Post 建议</button><div className="space-y-5">{controls.map(control => <label key={control.key} className="block text-sm"><span className="mb-3 flex justify-between text-slate-600"><span>{control.label}</span><output className="tabular-nums">{draft[control.key] > 0 ? "+" : ""}{draft[control.key]}</output></span><input aria-label={control.label} type="range" min={control.min} max={control.max} step="1" value={draft[control.key]} className="w-full accent-blue-600" onChange={event => { setDraft(previous => ({ ...previous, [control.key]: Number(event.target.value) })); setCompare(false) }} /></label>)}</div><div className="mt-6 flex gap-2"><button className={`${secondaryClass} flex-1`} onClick={() => { setDraft(neutral); setCompare(false) }}>重置滑杆</button><button className={`${buttonClass} flex-1`} disabled={!dirty} onClick={() => { session.apply({ ...current, adjustments: { ...draft } }); setMessage("调色已应用，写入新的浏览器编辑版本，可撤销。") }}>应用调色</button></div></section>
        <section className={panelClass}><h2 className="mb-3 flex items-center gap-2 font-semibold"><Sparkles className="h-4 w-4 text-violet-500" />让猫变得圆润</h2><p className="mb-4 text-sm leading-7 text-slate-600">{catCase.editPrompt}</p><p className="mb-4 text-xs leading-6 text-slate-500">此按钮展示已生成的固定结果，不向模型提交请求。它基于原图生成，载入时调色归零，便于观察原始前后差异。</p><button className={`${buttonClass} w-full`} disabled={current.rounded || dirty} onClick={() => { session.apply({ rounded: true, adjustments: { ...neutral } }); setDraft(neutral); setCompare(false); setMessage("已载入圆润预置结果。可对比原图，继续本地调色，或保存导出。") }}>{current.rounded ? "已载入圆润效果" : "查看圆润效果"}</button></section>
        <div className="flex flex-wrap gap-2"><DemoLink href="/assets" secondary>查看素材库</DemoLink><DemoLink href="/learning" secondary>查看学习反馈</DemoLink></div>
      </aside>
    </div>
  </>
}
