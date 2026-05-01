"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { FileDown, Star } from "lucide-react"
import { Button } from "@/components/ui/button"

interface PostSuggestion {
  category: string
  items: string[]
}

interface CoachSection {
  title: string
  icon?: string
  items: string[]
}

interface PracticeTask {
  title: string
  description: string
  isChallenge?: boolean
}

interface PostResult {
  summary: string
  suggestions: PostSuggestion[]
  params?: Record<string, string>
}

interface CoachResult {
  sections: CoachSection[]
  practiceTask?: PracticeTask
}

interface AnalysisResultPanelProps {
  postResult: PostResult
  coachResult: CoachResult
  onExport?: () => void
  onSave?: () => void
  onRetry?: () => void
  onPlan?: () => void
  onSendToAssets?: () => void
}

export function AnalysisResultPanel({
  postResult,
  coachResult,
  onExport,
  onSave,
  onRetry,
  onPlan,
  onSendToAssets,
}: AnalysisResultPanelProps) {
  return (
    <Card className="h-full min-h-0 flex flex-col flex-1 w-full overflow-hidden">
      <CardHeader className="pb-3 flex flex-row items-center justify-between shrink-0">
        <CardTitle className="text-lg font-bold text-slate-900">分析结果</CardTitle>
        <Button
          variant="outline"
          size="sm"
          className="h-7.5 px-3 text-xs font-bold border-slate-300"
          onClick={onExport}
        >
          <FileDown className="w-3.5 h-3.5 mr-1.5" />
          导出报告
        </Button>
      </CardHeader>
      <CardContent className="space-y-4 flex-1 flex flex-col min-h-0">
        {/* Summary Banner */}
        <div className="flex shrink-0 items-center gap-2 p-3 rounded-lg bg-amber-50 border border-amber-200">
          <Star className="w-4 h-4 text-amber-500 fill-amber-500" />
          <p className="text-sm font-bold text-amber-700">{postResult.summary}</p>
        </div>

        {/* Two Column Results */}
        <div className="grid grid-cols-2 gap-3 flex-1 min-h-0 overflow-hidden">
          {/* Post Result Card */}
          <div className="min-h-0 overflow-y-auto rounded-xl border border-blue-300 bg-white p-3.5 space-y-3">
            <h3 className="sticky top-0 z-10 text-sm font-extrabold text-blue-600 text-center py-2 bg-blue-50 rounded-lg border border-blue-200">
              后期建议
            </h3>
            <div className="space-y-3 text-sm">
              {postResult.suggestions.map((suggestion, idx) => (
                <div key={idx}>
                  <p className={`font-bold ${idx === 0 ? "text-blue-700" : "text-slate-700"}`}>
                    ◎ {suggestion.category}
                  </p>
                  <ul className="mt-1 space-y-0.5">
                    {suggestion.items.map((item, i) => (
                      <li key={i} className="text-slate-600 pl-2">
                        • {item}
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
              {postResult.params && (
                <div>
                  <p className="font-bold text-slate-700">◎ 参数建议</p>
                  <div className="mt-1 text-slate-600 pl-2 space-y-0.5">
                    {Object.entries(postResult.params).map(([key, value]) => (
                      <p key={key}>
                        {key} {value}
                      </p>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Coach Result Card */}
          <div className="min-h-0 overflow-y-auto rounded-xl border border-green-300 bg-white p-3.5 space-y-3">
            <h3 className="sticky top-0 z-10 text-sm font-extrabold text-green-600 text-center py-2 bg-green-50 rounded-lg border border-green-200">
              学习反馈
            </h3>
            <div className="space-y-3 text-sm">
              {coachResult.sections.map((section, idx) => (
                <div key={idx}>
                  <p className={`font-bold ${idx === 0 ? "text-green-700" : "text-slate-700"}`}>
                    ◎ {section.title}
                  </p>
                  <ul className="mt-1 space-y-0.5">
                    {section.items.map((item, i) => (
                      <li key={i} className="text-slate-600 pl-2">
                        {item.startsWith("✓") ? item : `• ${item}`}
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
              {coachResult.practiceTask && (
                <div className="p-3 rounded-lg bg-purple-50 border border-purple-200">
                  <div className="flex items-center gap-2 mb-1">
                    <Star className="w-3.5 h-3.5 text-purple-500 fill-purple-500" />
                    <p className="font-extrabold text-purple-700">
                      {coachResult.practiceTask.title}
                    </p>
                    {coachResult.practiceTask.isChallenge && (
                      <span className="text-xs px-2 py-0.5 rounded bg-purple-200 text-purple-700 font-bold">
                        挑战
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-slate-600 leading-relaxed">
                    {coachResult.practiceTask.description}
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Action Buttons - always at bottom */}
        <div className="grid grid-cols-4 gap-2.5 pt-2 shrink-0">
          <Button
            className="h-10 bg-slate-900 hover:bg-slate-800 text-white font-bold text-sm"
            onClick={onSave}
          >
            保存结果
          </Button>
          <Button
            variant="outline"
            className="h-10 border-slate-300 text-slate-700 font-bold text-sm bg-slate-50 hover:bg-slate-100"
            onClick={onRetry}
          >
            重新分析
          </Button>
          <Button
            variant="outline"
            className="h-10 border-orange-300 text-orange-600 font-bold text-sm bg-orange-50 hover:bg-orange-100"
            onClick={onPlan}
          >
            拍摄规划
          </Button>
          <Button
            variant="outline"
            className="h-10 border-blue-300 text-blue-600 font-bold text-sm bg-blue-50 hover:bg-blue-100"
            onClick={onSendToAssets}
          >
            送去素材库
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
