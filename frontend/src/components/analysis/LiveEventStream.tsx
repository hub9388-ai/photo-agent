"use client"

import { Pause, Play } from "lucide-react"
import { useState } from "react"

export interface SSEEvent {
  time: string
  agent: "job" | "post" | "coach" | "plan" | "asset"
  message: string
}

interface LiveEventStreamProps {
  events: SSEEvent[]
  onClear?: () => void
  maxHeight?: string
}

const agentStyles = {
  job: "text-slate-600 font-bold",
  post: "text-blue-600 font-bold",
  coach: "text-green-600 font-bold",
  plan: "text-orange-600 font-bold",
  asset: "text-purple-600 font-bold",
}

const agentLabels = {
  job: "[Job]",
  post: "[Post]",
  coach: "[Coach]",
  plan: "[Plan]",
  asset: "[Asset]",
}

export function LiveEventStream({
  events,
  onClear,
}: LiveEventStreamProps) {
  const [frozen, setFrozen] = useState<SSEEvent[] | null>(null)
  const displayed = frozen ?? events
  return (
    <div className="rounded-xl border border-slate-200 bg-white overflow-hidden h-full flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between px-3.5 py-2.5 border-b border-slate-100">
        <span className="text-sm font-extrabold text-slate-900">💬 实时输出流</span>
        <div className="flex items-center gap-3">
          <button
            onClick={onClear}
            className="text-xs text-slate-400 hover:text-slate-600"
          >
            清空
          </button>
          <button aria-label={frozen ? "继续显示消息" : "暂停显示消息"} aria-pressed={frozen !== null} onClick={() => setFrozen(current => current ? null : events)} className="w-7 h-7 rounded-md border border-slate-300 bg-white flex items-center justify-center hover:bg-slate-50">
            {frozen ? <Play className="w-3.5 h-3.5 text-slate-500" /> : <Pause className="w-3.5 h-3.5 text-slate-500" />}
          </button>
        </div>
      </div>

      {/* Event List */}
      <div className="flex-1 min-h-0 overflow-y-auto">
        {displayed.length === 0 ? (
          <div className="flex h-full min-h-[180px] items-center justify-center">
            <p className="text-slate-400 text-center">暂无实时消息</p>
          </div>
        ) : (
          <div className="divide-y divide-slate-100">
            {displayed.map((event, index) => (
              <div
                key={index}
                className={`px-3 py-2.5 flex items-start gap-3 text-sm ${
                  index % 2 === 0 ? "bg-slate-50" : "bg-white"
                }`}
              >
                <span className="text-slate-400 whitespace-nowrap">{event.time}</span>
                <span className={agentStyles[event.agent]}>
                  {agentLabels[event.agent]}
                </span>
                <span className="text-slate-600">{event.message}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="px-3.5 py-2 border-t border-slate-100">
        <p className="text-xs text-slate-500">
          任务创建后，将在此接收 Agent 进度消息
        </p>
      </div>
    </div>
  )
}
