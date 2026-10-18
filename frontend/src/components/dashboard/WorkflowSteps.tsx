import Link from "next/link"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { photographyWorkflow } from "@/lib/photography-workflow"

export function WorkflowSteps() {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">摄影工作流程</CardTitle>
        <p className="text-sm leading-6 text-slate-600">推荐按以下流程体验，也可以直接进入任一环节；分析后即可查看学习反馈，无需等待修图完成。</p>
      </CardHeader>
      <CardContent>
        <ol aria-label="摄影工作流程" className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-5">
          {photographyWorkflow.map((step, index) => (
            <li key={step.path}>
              <Link href={step.path} className="flex h-full items-start gap-3 rounded-lg border border-slate-200 p-3 hover:border-blue-400 focus-visible:outline-2 focus-visible:outline-blue-500">
                <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-blue-50 text-sm font-semibold text-blue-700">{index + 1}</span>
                <div><p className="font-medium text-slate-900">{step.title}</p><p className="mt-1 text-xs leading-5 text-slate-500">{step.step}</p></div>
              </Link>
            </li>
          ))}
        </ol>
      </CardContent>
    </Card>
  )
}
