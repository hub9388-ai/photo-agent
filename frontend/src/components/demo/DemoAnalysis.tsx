"use client"

import { useEffect, useState } from "react"
import { CheckCircle2, Play } from "lucide-react"
import { catCase } from "@/lib/demo/case"
import type { DemoSession } from "@/lib/demo/state"
import { buttonClass, DemoLink, DemoList, panelClass } from "./DemoUI"
import { DemoPhoto } from "./DemoRetouch"

const stages = ["载入街角三花猫原图", "Post：回放曝光、色彩与后期方向分析", "Coach：回放构图观察与拍摄练习建议", "分析完成 · 可进入修图预览"]
export function DemoAnalysis({ session }: { session: DemoSession }) {
  const [step, setStep] = useState(-1)
  const [tab, setTab] = useState<"post" | "coach">("post")
  const { setState } = session
  const running = step >= 0 && step < stages.length - 1
  useEffect(() => {
    if (!running) return
    const timer = window.setTimeout(() => {
      if (step === stages.length - 2) setState(previous => ({ ...previous, analyzed: true }))
      setStep(previous => previous + 1)
    }, 650)
    return () => window.clearTimeout(timer)
  }, [step, running, setState])
  const complete = session.state.analyzed && !running
  return <>
    <p className="text-sm leading-7 text-slate-600">选择案例原图，回放两个 Agent 的分工；建议内容为针对本案例整理的固定示例。</p>
    <div className="grid items-start gap-6 lg:grid-cols-[0.85fr_1.4fr]">
      <section className={`${panelClass} space-y-4`}><h2 className="font-semibold">{catCase.title}</h2><DemoPhoto source="original" className="max-h-[410px] w-full rounded-xl bg-slate-100 object-contain" /><label className="block text-sm font-medium text-slate-700" htmlFor="demo-preference">案例分析偏好</label><textarea id="demo-preference" readOnly value={catCase.preference} className="min-h-20 w-full resize-none rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm leading-7 text-slate-600" /><p className="text-xs leading-6 text-slate-500">此版本仅提供该预置案例，不上传个人照片。未读取或虚构照片 EXIF。</p><button className={`${buttonClass} w-full`} disabled={running} onClick={() => setStep(0)}><Play className="h-4 w-4" />{running ? "正在回放分析过程…" : complete ? "重新回放分析" : "开始分析演示"}</button></section>
      <div className="space-y-5">
        <section className={panelClass}><h2 className="mb-4 font-semibold">分析过程 · 示例回放</h2><ol aria-live="polite" className="space-y-3">{stages.map((stage, index) => <li key={stage} className={`flex items-center gap-3 text-sm ${index <= step || complete ? "text-blue-700" : "text-slate-400"}`}><CheckCircle2 className="h-4 w-4 shrink-0" />{stage}</li>)}</ol></section>
        {complete ? <section className={panelClass}>
          <p className="mb-5 rounded-lg bg-amber-50 p-4 text-sm leading-7 text-amber-900">保留自然街头感，稍提亮主体、轻微增加反差；若想更可爱，可另外体验圆润生成效果。</p>
          <div role="tablist" aria-label="分析结果" className="mb-5 flex rounded-lg bg-slate-100 p-1">{([ ["post", "Post · 后期建议"], ["coach", "Coach · 学习反馈"] ] as const).map(([value, label]) => <button key={value} id={`tab-${value}`} role="tab" aria-controls="demo-analysis-result" aria-selected={tab === value} className={`flex-1 rounded-md px-3 py-2 text-sm ${tab === value ? "bg-white font-medium text-blue-700 shadow-sm" : "text-slate-600"}`} onClick={() => setTab(value)}>{label}</button>)}</div>
          <div role="tabpanel" id="demo-analysis-result" aria-labelledby={`tab-${tab}`} className="space-y-5">
            {tab === "post" ? <><h3 className="font-semibold">先关注三个问题</h3><DemoList items={catCase.issues} /><h3 className="font-semibold">自然、可爱的后期方向</h3><p className="text-sm leading-8 text-slate-600">避免一味全局提亮；先少量增加亮度与对比度，让猫脸更易读，稍降整体饱和度，减少车牌和背景抢眼的感觉。毛色和白毛细节优先保留。</p><div className="overflow-x-auto"><table className="w-full text-left text-sm"><caption className="mb-2 text-left text-xs text-slate-500">浏览器演示初值 · 近似效果，不等同 Lightroom 参数</caption><thead className="bg-slate-50 text-slate-500"><tr><th className="p-3">项目</th><th className="p-3">滑杆初值</th><th className="p-3">目的</th></tr></thead><tbody className="divide-y divide-slate-100">{[["亮度", "+4", "小幅提亮"], ["对比度", "+8", "增加层次"], ["饱和度", "−5", "减少背景干扰"]].map(row => <tr key={row[0]}>{row.map(cell => <td key={cell} className="p-3">{cell}</td>)}</tr>)}</tbody></table></div><p className="text-xs leading-6 text-slate-500">眼部局部提亮、黑色色阶、去朦胧不在本演示滑杆支持范围内，明确跳过，不用亮度或锐化替代。猫的圆润程度由单独的预置生成结果展示。</p></> : <><h3 className="font-semibold text-green-700">照片的优点</h3><DemoList items={catCase.strengths} /><h3 className="font-semibold">下次可以改进</h3><DemoList items={catCase.improvements} /><div className="rounded-lg bg-green-50 p-4"><h3 className="mb-2 font-semibold text-green-800">练习：用机位做减法</h3><p className="text-sm leading-7 text-green-900">{catCase.practice}</p></div></>}
          </div><div className="mt-6 flex flex-wrap gap-3"><DemoLink href="/retouch">带建议进入修图</DemoLink><DemoLink href="/learning" secondary>领取练习</DemoLink></div>
        </section> : <section className={`${panelClass} text-sm leading-8 text-slate-500`}>点击“开始分析演示”，回放 Post 与 Coach 的工作过程。完整反馈会在这里展开。</section>}
      </div>
    </div>
  </>
}
