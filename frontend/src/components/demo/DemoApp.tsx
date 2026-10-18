"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { Camera, Check, ChevronRight, FolderOpen, GraduationCap, Paintbrush, RotateCcw } from "lucide-react"
import { TopNav } from "@/components/layout/TopNav"
import { catCase, westLakePlan } from "@/lib/demo/case"
import { useDemoState, type DemoSession } from "@/lib/demo/state"
import { DemoAnalysis } from "./DemoAnalysis"
import { DemoRetouch, DemoPhoto } from "./DemoRetouch"
import { DemoPlanning } from "./DemoPlanning"
import { DemoLink, DemoList, panelClass, secondaryClass } from "./DemoUI"

export function DemoApp() {
  const pathname = usePathname()
  const session = useDemoState()
  const section = pathname.split("/")[1] || "home"
  const titles: Record<string, string> = { home: "从一张照片开始，把建议变成作品", analysis: "照片分析", retouch: "照片修图工作台", assets: "素材库", learning: "学习与练习", planning: "拍摄规划", history: "体验记录" }
  return <div className="min-h-screen bg-slate-50">
    <TopNav />
    <div className="border-b border-blue-100 bg-blue-50 px-4 py-2 text-center text-xs leading-6 text-blue-800">演示模式 · 使用预置案例，不实时调用模型 · 调色与图片下载在浏览器本地完成</div>
    <main className="mx-auto max-w-7xl space-y-6 px-4 py-6 md:px-8 md:py-8">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div><p className="mb-2 text-xs font-semibold uppercase tracking-widest text-blue-600">PhotoAI / {section === "home" ? "摄影工作流" : "交互演示"}</p><h1 className="text-2xl font-semibold tracking-tight text-slate-900 md:text-3xl">{titles[section] ?? "照片分析"}</h1></div>
        <button className={secondaryClass} onClick={() => { if (window.confirm("清空此浏览器中的演示进度、调色和已保存版本？")) session.reset() }}><RotateCcw className="h-4 w-4" />重置体验</button>
      </div>
      {!session.persistent && <p role="status" className="text-sm text-amber-700">浏览器存储不可用，本次操作可继续，但刷新后可能无法恢复。</p>}
      {!session.ready ? <p role="status">正在载入演示案例…</p> : section === "home" ? <DemoHome session={session} /> : section === "analysis" ? <DemoAnalysis session={session} /> : section === "retouch" ? <DemoRetouch session={session} /> : section === "assets" ? <DemoAssets session={session} /> : section === "learning" ? <DemoLearning session={session} /> : section === "planning" ? <DemoPlanning session={session} /> : section === "history" ? <DemoHistory session={session} /> : <DemoAnalysis session={session} />}
    </main>
  </div>
}

function DemoHome({ session }: { session: DemoSession }) {
  return <>
    <section className={`${panelClass} grid gap-8 md:grid-cols-[1.2fr_1fr] md:items-center`}>
      <div className="space-y-5"><span className="inline-flex rounded-full bg-amber-50 px-3 py-1 text-xs font-medium text-amber-800">案例 01 · 街头宠物摄影</span><h2 className="text-3xl font-semibold leading-tight text-slate-900 md:text-4xl">读懂照片，<br />也保留你的审美。</h2><p className="max-w-lg text-base leading-8 text-slate-600">从三花猫的照片出发，看 Post 与 Coach 如何分别给出后期建议和拍摄反馈，再进入修图预览、微调与保存。</p><div className="flex flex-wrap gap-3"><DemoLink href="/analysis">开始照片分析</DemoLink><DemoLink href="/planning" secondary>体验西湖摄影规划</DemoLink></div><p className="text-xs leading-6 text-slate-500">约 3 分钟走完主要流程。分析为预置内容，圆润修改为已生成结果；可实际拖动滑杆、应用、撤销与下载。</p></div>
      <div className="relative mx-auto w-full max-w-sm overflow-hidden rounded-xl bg-slate-100"><DemoPhoto source="original" className="max-h-[430px] w-full object-cover" /><span className="absolute bottom-3 left-3 rounded bg-slate-900/75 px-3 py-1 text-xs text-white">{catCase.title} · 原图</span></div>
    </section>
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">{[
      { icon: Camera, label: "01 分析", desc: "Post 后期建议 + Coach 学习反馈", href: "/analysis", done: session.state.analyzed },
      { icon: Paintbrush, label: "02 修图", desc: "调色微调 + 圆润效果前后对比", href: "/retouch", done: session.state.current.rounded },
      { icon: FolderOpen, label: "03 保存", desc: "保留原图与编辑版本，整理到素材库", href: "/assets", done: !!session.state.saved },
      { icon: GraduationCap, label: "04 学习", desc: "把本次反馈变成下一次拍摄任务", href: "/learning", done: session.state.practiced },
    ].map(item => <Link href={item.href} key={item.label} className={`${panelClass} transition hover:border-blue-300 hover:shadow-sm`}><item.icon className="mb-4 h-6 w-6 text-blue-600" /><h3 className="mb-2 flex items-center gap-2 font-semibold">{item.label}{item.done && <Check className="h-4 w-4 text-green-600" />}</h3><p className="text-sm leading-6 text-slate-500">{item.desc}</p></Link>)}</div>
  </>
}

function DemoAssets({ session }: { session: DemoSession }) {
  const saved = session.state.saved
  return <>
    <div className="flex flex-wrap justify-between gap-3"><p className="text-sm leading-7 text-slate-600">街头宠物摄影 / {saved ? "2" : "1"} 张 · 原图始终保留，编辑版本另存。</p><DemoLink href="/retouch">继续编辑</DemoLink></div>
    <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
      <article className={panelClass}><DemoPhoto source="original" className="mb-4 h-72 w-full rounded-lg object-contain bg-slate-100" /><h2 className="font-semibold">{catCase.title} · 原图</h2><p className="my-2 text-sm text-slate-500">标签：宠物 / 街头 / 三花猫</p><DemoLink href="/analysis" secondary>查看分析</DemoLink></article>
      {saved ? <article className={panelClass}><DemoPhoto source={saved.rounded ? "rounded" : "original"} adjustments={saved.adjustments} className="mb-4 h-72 w-full rounded-lg object-contain bg-slate-100" /><h2 className="font-semibold">{saved.rounded ? "圆润版本" : "调色版本"} · 已保存</h2><p className="my-2 text-sm text-slate-500">本浏览器保存的编辑快照；原图未覆盖。</p><DemoLink href="/retouch" secondary>前后对比与导出</DemoLink></article> : <article className={`${panelClass} flex min-h-72 flex-col items-start justify-center gap-4 border-dashed`}><FolderOpen className="h-8 w-8 text-slate-400" /><p className="text-sm text-slate-500">还没有保存编辑版本。</p><DemoLink href="/retouch">去修图并保存</DemoLink></article>}
    </div>
    <section className={panelClass}><h2 className="mb-3 font-semibold">Asset Agent · 预置整理建议</h2><p className="text-sm leading-7 text-slate-600">将原图与圆润版本关联到同一作品，按“宠物 / 街头 / 三花猫”组织。保留生成式版本标识，避免把编辑结果与原始拍摄混淆。</p></section>
    <DemoLink href="/learning">把反馈变成下一次练习</DemoLink>
  </>
}

function DemoLearning({ session }: { session: DemoSession }) {
  return <div className="grid gap-6 lg:grid-cols-[1fr_1.3fr]">
    <section className={panelClass}><h2 className="mb-4 text-lg font-semibold">本次 Coach 反馈</h2><DemoPhoto source="original" className="mb-5 max-h-64 w-full rounded-lg object-contain bg-slate-100" /><DemoList items={catCase.improvements} /><p className="mt-4 text-xs leading-6 text-slate-500">反馈针对原图；生成式圆润效果不计为摄影能力提升。</p></section>
    <div className="space-y-5"><section className={panelClass}><span className="text-xs font-medium text-green-700">拍摄练习 · 主体与背景</span><h2 className="my-3 text-xl font-semibold">用机位做减法</h2><p className="mb-5 text-sm leading-8 text-slate-600">{catCase.practice}</p><DemoList items={["先观察：找出主体轮廓附近的文字、车轮和线条。", "再行动：平移或降低机位，保留眼神与完整肢体。", "复盘：对比三张图，写下哪一个背景最干净以及原因。"]} /><label className="mt-5 flex cursor-pointer items-start gap-3 rounded-lg bg-green-50 p-4 text-sm text-green-900"><input type="checkbox" className="mt-1" checked={session.state.practiced} onChange={event => session.setState(previous => ({ ...previous, practiced: event.target.checked }))} />{session.state.practiced ? "已加入我的练习清单" : "加入我的练习清单"}</label><p className="mt-3 text-xs text-slate-500">这里记录练习意向，不代表已完成拍摄或 AI 复评。</p></section><DemoLink href="/planning">规划下一次摄影出行</DemoLink></div>
  </div>
}

function DemoHistory({ session }: { session: DemoSession }) {
  const entries = [
    { label: "照片分析 · Post + Coach", done: session.state.analyzed, href: "/analysis" },
    { label: "修图 · 已应用的调色或圆润版本", done: session.state.undo.length > 0, href: "/retouch" },
    { label: "素材库 · 保存作品", done: !!session.state.saved, href: "/assets" },
    { label: "学习 · 领取练习", done: session.state.practiced, href: "/learning" },
    { label: "规划 · 西湖摄影一日游", done: session.state.planned, href: "/planning" },
  ]
  return <section className={panelClass}><p className="mb-5 text-sm text-slate-500">仅记录此浏览器的演示进度。</p><div className="divide-y divide-slate-100">{entries.map(entry => <Link href={entry.href} key={entry.href} className="flex items-center justify-between gap-4 py-5"><span className="font-medium text-slate-700">{entry.label}</span><span className="flex items-center gap-2 text-sm text-slate-500">{entry.done ? "已体验" : "去体验"}<ChevronRight className="h-4 w-4" /></span></Link>)}</div><p className="mt-5 text-sm text-slate-500">规划案例包含 {westLakePlan.length} 个时段，所有分析与规划结果均为固定示例。</p></section>
}
