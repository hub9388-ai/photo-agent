"use client"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Upload, List, Cloud, Radio, Database } from "lucide-react"
import Link from "next/link"
import { mockSystemStatus } from "@/lib/mocks"
import { DEMO_MODE } from "@/lib/demo/config"

const statusConfig: Record<string, { color: string; text: string }> = {
  healthy: { color: "bg-green-500", text: "正常" },
  ready: { color: "bg-green-500", text: "就绪" },
  degraded: { color: "bg-yellow-500", text: "降级" },
  down: { color: "bg-red-500", text: "故障" },
  connecting: { color: "bg-yellow-500", text: "连接中" },
  disconnected: { color: "bg-red-500", text: "断开" },
  full: { color: "bg-yellow-500", text: "已满" },
  error: { color: "bg-red-500", text: "错误" },
}

export function HeroSection() {
  const apiStatus = statusConfig[mockSystemStatus.api] || statusConfig.healthy
  const sseStatus = statusConfig[mockSystemStatus.sse] || statusConfig.ready
  const storageStatus = statusConfig[mockSystemStatus.storage] || statusConfig.healthy

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <div className="lg:col-span-2 space-y-4">
        <h1 className="text-4xl font-bold text-slate-900">
          摄影多 Agent 工作台
        </h1>
        <p className="text-lg text-slate-600">
          上传照片、并行分析、素材整理、学习成长、拍摄规划
        </p>
        <div className="flex gap-3 pt-2">
          <Button size="lg" className="gap-2" asChild>
            <Link href="/analysis">
              <Upload className="w-5 h-5" />
              上传照片开始分析
            </Link>
          </Button>
          <Button variant="outline" size="lg" className="gap-2" asChild>
            <Link href="/history">
              <List className="w-5 h-5" />
              查看最近任务
            </Link>
          </Button>
        </div>
      </div>

      {/* System Status Card */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-base">系统状态</CardTitle>
            <Badge variant="outline" className="bg-green-50 text-green-700 border-green-200">
              <span className="w-1.5 h-1.5 rounded-full bg-green-500 mr-1" />
              {DEMO_MODE ? "演示就绪" : "运行中"}
            </Badge>
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex items-center gap-3">
            <Cloud className="w-4 h-4 text-slate-500" />
            <span className="text-sm text-slate-600 flex-1">API 服务</span>
            <div className="flex items-center gap-1.5">
              <span className={`w-1.5 h-1.5 rounded-full ${apiStatus.color}`} />
              <Badge variant="outline" className="text-xs bg-green-50 text-green-700">{DEMO_MODE ? "预置数据" : apiStatus.text}</Badge>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <Radio className="w-4 h-4 text-slate-500" />
            <span className="text-sm text-slate-600 flex-1">EventBus / SSE</span>
            <div className="flex items-center gap-1.5">
              <span className={`w-1.5 h-1.5 rounded-full ${sseStatus.color}`} />
              <Badge variant="outline" className="text-xs bg-green-50 text-green-700">{DEMO_MODE ? "案例回放" : sseStatus.text}</Badge>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <Database className="w-4 h-4 text-slate-500" />
            <span className="text-sm text-slate-600 flex-1">存储服务</span>
            <div className="flex items-center gap-1.5">
              <span className={`w-1.5 h-1.5 rounded-full ${storageStatus.color}`} />
              <Badge variant="outline" className="text-xs bg-green-50 text-green-700">{DEMO_MODE ? "浏览器本地" : storageStatus.text}</Badge>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
