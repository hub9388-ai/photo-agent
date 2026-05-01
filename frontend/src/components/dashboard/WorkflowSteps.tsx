import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { ArrowRight } from "lucide-react"

const steps = [
  {
    number: 1,
    color: "bg-blue-500",
    title: "上传媒体",
    description: "mediaId / previewUrl / metadata",
  },
  {
    number: 2,
    color: "bg-blue-500",
    title: "Post + Coach 并行分析",
    description: "多 Agent 同时运行，互不干扰",
  },
  {
    number: 3,
    color: "bg-green-500",
    title: "SSE 实时状态",
    description: "agent.started / progress / result",
  },
  {
    number: 4,
    color: "bg-orange-500",
    title: "结果持久化",
    description: "results API 保存与历史恢复",
  },
]

export function WorkflowSteps() {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base flex items-center gap-2">
          <span className="text-blue-500">实时协作链路</span>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4 flex-1">
            {steps.map((step, index) => (
              <div key={step.number} className="flex items-center gap-3">
                <div className="flex items-center gap-3">
                  <div className={`w-8 h-8 rounded-full ${step.color} text-white flex items-center justify-center text-sm font-medium`}>
                    {step.number}
                  </div>
                  <div>
                    <p className="font-medium text-slate-900">{step.title}</p>
                    <p className="text-xs text-slate-500">{step.description}</p>
                  </div>
                </div>
                {index < steps.length - 1 && (
                  <ArrowRight className="w-4 h-4 text-slate-300" />
                )}
              </div>
            ))}
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
