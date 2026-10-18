"use client"

import { useState } from "react"
import { MapPin } from "lucide-react"
import { westLakePlan } from "@/lib/demo/case"
import type { DemoSession } from "@/lib/demo/state"
import { buttonClass, DemoLink, panelClass } from "./DemoUI"

export function DemoPlanning({ session }: { session: DemoSession }) {
  const [request, setRequest] = useState("去杭州西湖游玩一天，以摄影为主，步行适中，想拍湖景和有生活感的人物。")
  const [error, setError] = useState("")
  return <>
    <section className={panelClass}><div className="grid gap-5 md:grid-cols-[1fr_auto] md:items-end"><div><label htmlFor="demo-trip" className="mb-3 block font-medium">这次想去哪里拍？</label><textarea id="demo-trip" value={request} onChange={event => { setRequest(event.target.value); setError("") }} className="min-h-24 w-full rounded-lg border border-slate-200 p-3 text-sm leading-7" /><p className="mt-2 text-xs leading-6 text-slate-500">本演示只提供“杭州西湖一日摄影游”固定案例；输入内容不会触发实时生成。</p></div><button className={buttonClass} onClick={() => { if (!request.includes("西湖") || !request.includes("一天") && !request.includes("一日")) { setError("当前仅支持西湖一日游案例，请输入“杭州西湖游玩一天”。其他目的地需运行完整后端。" ); return }; session.setState(previous => ({ ...previous, planned: true })); setError("") }}>展示示例规划</button></div>{error && <p role="alert" className="mt-3 text-sm text-amber-800">{error}</p>}</section>
    {session.state.planned ? <>
      <section className={`${panelClass} space-y-3`}><span className="text-xs font-medium text-orange-700">Plan Agent · 固定路线示例</span><h2 className="text-xl font-semibold">把西湖一日游，变成一组有主题的照片</h2><p className="text-sm leading-7 text-slate-600">北岸起步 → 西侧湖岸。以慢行拍摄为主，午间休息，后半段按体力缩短。重点是机位、光线和拍摄任务，不追求赶完所有景点。</p><p className="rounded-lg bg-amber-50 p-3 text-xs leading-6 text-amber-900">时段为示意安排，未查询实时天气、客流、交通或日落。门票与开放时间以景区当天公告为准；本例不安排必须购票的登塔行程。</p></section>
      <div className="grid gap-4 md:grid-cols-2">{westLakePlan.map((stop, index) => <section key={stop.time} className={panelClass}><div className="mb-3 flex items-center gap-3"><span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-orange-50 text-sm font-semibold text-orange-700">{index + 1}</span><span className="text-sm font-medium text-orange-700">{stop.time}</span></div><h3 className="mb-3 flex items-center gap-2 text-lg font-semibold"><MapPin className="h-4 w-4 text-slate-400" />{stop.place}</h3><p className="mb-3 text-sm leading-7 text-slate-600">{stop.task}</p><p className="rounded-lg bg-slate-50 p-3 text-xs leading-6 text-slate-500">{stop.equipment}</p></section>)}</div>
      <section className={panelClass}><h3 className="mb-3 font-semibold">出发前准备</h3><p className="text-sm leading-7 text-slate-600">充电、清理存储卡，带舒适的鞋和饮水。雨天选择就近可避雨的公共空间，不坚持长距离环湖。返程前选出一张环境、一张人物、一张细节，组成三图故事。</p><p className="mt-3 text-xs leading-6 text-slate-500">地理背景参考：<a className="text-blue-600 underline" href="https://whc.unesco.org/en/list/1334/" target="_blank" rel="noreferrer">UNESCO 西湖文化景观</a>。路线与时间为演示策划，不是官方推荐行程。</p></section><DemoLink href="/learning">查看摄影练习</DemoLink>
    </> : <section className={`${panelClass} py-12 text-center`}><MapPin className="mx-auto mb-4 h-10 w-10 text-orange-400" /><h2 className="mb-3 text-lg font-semibold">从出游需求，到拍摄行动</h2><p className="text-sm text-slate-500">展示路线、时段、焦段与拍摄任务，提前为出行建立拍摄目标。</p></section>}
  </>
}
