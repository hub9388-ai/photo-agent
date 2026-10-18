"use client"

import Link from "next/link"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { FileDown, Star } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"

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
  requirements?: string[]
  acceptance?: string[]
}

interface PostResult {
  summary: string
  suggestions: PostSuggestion[]
  params?: Record<string, string>
  parameters?: PostParameter[]
  originalText?: string
  sourceNote?: string
}

export interface PostParameter {
  key: string
  label: string
  value: string
  effect: string
}

interface CoachResult {
  sections: CoachSection[]
  practiceTask?: PracticeTask
  originalText?: string
}

interface AnalysisResultPanelProps {
  postResult: PostResult
  coachResult: CoachResult
  onExport?: () => void
  onSave?: () => void
  onRetry?: () => void
  onPlan?: () => void
  onSendToAssets?: () => void
  mediaId?: string
  jobId?: string | null
}

export function AnalysisResultPanel({
  postResult,
  coachResult,
  onExport,
  onSave,
  onRetry,
  onPlan,
  onSendToAssets,
  mediaId,
  jobId,
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
          <div className="min-w-0 text-sm text-amber-800">
            <p className="font-semibold leading-relaxed line-clamp-3">{postResult.summary}</p>
            {postResult.summary.length > 100 && (
              <details className="mt-1 text-xs">
                <summary className="cursor-pointer">展开摘要</summary>
                <p className="mt-2 leading-relaxed">{postResult.summary}</p>
              </details>
            )}
          </div>
        </div>

        <Tabs defaultValue="post" className="flex flex-1 min-h-0 flex-col gap-3">
          <TabsList aria-label="分析结果类型" className="grid w-full grid-cols-2 shrink-0 bg-slate-100">
            <TabsTrigger value="post" className="data-[state=active]:text-blue-700">后期建议</TabsTrigger>
            <TabsTrigger value="coach" className="data-[state=active]:text-green-700">学习反馈</TabsTrigger>
          </TabsList>
          {/* Post Result Card */}
          <TabsContent value="post" className="mt-0 min-h-0 flex-1 overflow-y-auto rounded-xl border border-blue-200 bg-white p-4 space-y-5">
            <div className="space-y-5 text-sm">
              {postResult.suggestions
                .filter((suggestion) => !(postResult.parameters?.length && suggestion.category === "模型参考参数"))
                .map((suggestion) => <SuggestionSection key={suggestion.category} suggestion={suggestion} />)}
              {!!postResult.parameters?.length && (
                <section aria-label="模型参考参数" className="space-y-2">
                  <h3 className="font-semibold text-slate-900">模型参考参数</h3>
                  <p className="text-xs leading-relaxed text-slate-500">Post Agent 原始建议 · 摄影软件参考值，尚未转换为修图工具参数。</p>
                  <table className="w-full table-fixed text-left text-xs">
                    <caption className="sr-only">参数、模型建议值与调整方向</caption>
                    <thead className="bg-slate-50 text-slate-500">
                      <tr><th scope="col" className="w-[27%] p-2 font-medium">参数</th><th scope="col" className="w-[23%] p-2 font-medium">建议值</th><th scope="col" className="p-2 font-medium">方向</th></tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {postResult.parameters.map((row) => (
                        <tr key={row.key}><th scope="row" className="p-2 font-medium text-slate-700">{row.label}</th><td className="p-2 tabular-nums text-blue-700 break-words">{row.value}</td><td className="p-2 text-slate-600">{row.effect}</td></tr>
                      ))}
                    </tbody>
                  </table>
                </section>
              )}
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
              {postResult.sourceNote && <p className="rounded-lg bg-slate-50 p-3 text-xs leading-relaxed text-slate-500">分析依据：{postResult.sourceNote}</p>}
              {postResult.originalText && (
                <details className="border-t border-slate-100 pt-3">
                  <summary className="cursor-pointer text-xs font-medium text-slate-500">查看 Post Agent 完整原文</summary>
                  <p className="mt-3 whitespace-pre-wrap text-sm leading-7 text-slate-600">{postResult.originalText}</p>
                </details>
              )}
            </div>
          </TabsContent>

          {/* Coach Result Card */}
          <TabsContent value="coach" className="mt-0 min-h-0 flex-1 overflow-y-auto rounded-xl border border-green-200 bg-white p-4 space-y-4">
            <div className="space-y-3 text-sm">
              {coachResult.sections.map((section, idx) => (
                <div key={idx}>
                  <p className={`font-bold ${idx === 0 ? "text-green-700" : "text-slate-700"}`}>
                    ◎ {section.title}
                  </p>
                  <ul className="mt-2 list-disc pl-5 space-y-2 leading-relaxed">
                    {section.items.map((item, i) => (
                      <li key={i} className="text-slate-600">
                        {item.replace(/^[\s•●·]+/, "")}
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
                  {!!coachResult.practiceTask.requirements?.length && (
                    <div className="mt-3">
                      <p className="text-xs font-semibold text-purple-800">练习要求</p>
                      <ul className="mt-2 list-disc pl-4 space-y-2 text-xs leading-relaxed text-slate-600">
                        {coachResult.practiceTask.requirements.map((item, index) => <li key={index}>{item}</li>)}
                      </ul>
                    </div>
                  )}
                  {!!coachResult.practiceTask.acceptance?.length && (
                    <div className="mt-3">
                      <p className="text-xs font-semibold text-purple-800">验收标准</p>
                      <ul className="mt-2 list-disc pl-4 space-y-2 text-xs leading-relaxed text-slate-600">
                        {coachResult.practiceTask.acceptance.map((item, index) => <li key={index}>{item}</li>)}
                      </ul>
                    </div>
                  )}
                </div>
              )}
              {coachResult.originalText && (
                <details className="border-t border-slate-100 pt-3">
                  <summary className="cursor-pointer text-xs font-medium text-slate-500">查看 Coach Agent 完整原文</summary>
                  <p className="mt-3 whitespace-pre-wrap text-sm leading-7 text-slate-600">{coachResult.originalText}</p>
                </details>
              )}
            </div>
          </TabsContent>
        </Tabs>

        {/* Action Buttons - always at bottom */}
        {mediaId && (
          <Link href={`/retouch?media_id=${encodeURIComponent(mediaId)}${jobId ? `&job_id=${encodeURIComponent(jobId)}` : ""}`}
            className="mb-2 rounded border border-violet-200 bg-violet-50 p-2 text-center text-sm font-bold text-violet-700">
            将当前照片送入修图工作台
          </Link>
        )}
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

function SuggestionSection({ suggestion }: { suggestion: PostSuggestion }) {
  const isActions = suggestion.category === "调整建议"
  const visible = isActions ? suggestion.items.slice(0, 3) : suggestion.items
  const renderItems = (items: string[]) => (
    <ul className="mt-2 list-disc pl-5 space-y-2 text-slate-600 leading-relaxed">
      {items.map((item, index) => (
        <li key={index}>
          {item.length > 100 ? (
            <details>
              <summary className="cursor-pointer list-none">
                {item.slice(0, 90)}… <span className="text-xs text-blue-600">展开</span>
              </summary>
              <p className="mt-2 whitespace-pre-wrap leading-7">{item}</p>
            </details>
          ) : item}
        </li>
      ))}
    </ul>
  )
  return (
    <section>
      <h3 className="font-semibold text-slate-900">{suggestion.category}</h3>
      {renderItems(visible)}
      {isActions && suggestion.items.length > 3 && (
        <details className="mt-3">
          <summary className="cursor-pointer text-xs font-medium text-blue-600">更多调整建议（{suggestion.items.length - 3}项）</summary>
          {renderItems(suggestion.items.slice(3))}
        </details>
      )}
    </section>
  )
}
