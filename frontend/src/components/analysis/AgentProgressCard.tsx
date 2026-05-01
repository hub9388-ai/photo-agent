"use client"

import { Check } from "lucide-react"

export interface AgentStep {
  name: string
  status: "completed" | "running" | "pending"
}

export interface AgentProgress {
  name: string
  progress: number
  status: "running" | "completed" | "pending" | "failed"
  currentStep: string
  steps: AgentStep[]
}

interface AgentProgressCardProps {
  agent: AgentProgress
  variant: "post" | "coach"
}

const variantStyles = {
  post: {
    border: "border-blue-300",
    bg: "bg-blue-50",
    dot: "bg-blue-600",
    text: "text-blue-600",
    progressTrack: "bg-blue-100",
    progressFill: "bg-blue-500",
  },
  coach: {
    border: "border-green-300",
    bg: "bg-green-50",
    dot: "bg-green-600",
    text: "text-green-600",
    progressTrack: "bg-green-100",
    progressFill: "bg-green-500",
  },
}

export function AgentProgressCard({ agent, variant }: AgentProgressCardProps) {
  const styles = variantStyles[variant]

  const getStatusText = () => {
    switch (agent.status) {
      case "running":
        return "运行中"
      case "completed":
        return "已完成"
      case "failed":
        return "失败"
      default:
        return "等待中"
    }
  }

  const formatStepStatus = (step: AgentStep, index: number) => {
    if (step.status === "completed") {
      return (
        <span key={index} className="flex items-center gap-1">
          <Check className="w-3.5 h-3.5 text-slate-600" />
          <span className="text-slate-600">{step.name} 完成</span>
        </span>
      )
    } else if (step.status === "running") {
      return (
        <span key={index} className="flex items-center gap-1">
          <span className={`w-2 h-2 rounded-full ${styles.dot}`} />
          <span className="text-slate-600">{step.name} 进行中</span>
        </span>
      )
    } else {
      return (
        <span key={index} className="flex items-center gap-1 text-slate-400">
          <span className="w-2 h-2 rounded-full border-2 border-slate-300" />
          {step.name} 等待中
        </span>
      )
    }
  }

  return (
    <div className={`p-3.5 rounded-xl border ${styles.border} ${styles.bg}`}>
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full ${styles.dot}`} />
          <span className="font-extrabold text-slate-900">{agent.name}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className={`text-sm font-bold ${styles.text}`}>{agent.progress}%</span>
          <span className={`text-sm font-bold ${styles.text}`}>{getStatusText()}</span>
        </div>
      </div>

      {/* Progress Bar */}
      <div className={`h-1.5 rounded-full ${styles.progressTrack} mb-3 overflow-hidden`}>
        <div
          className={`h-full rounded-full ${styles.progressFill} transition-all duration-300`}
          style={{ width: `${agent.progress}%` }}
        />
      </div>

      {/* Current Step Message */}
      <p className={`text-sm font-bold ${styles.text} mb-3`}>{agent.currentStep}</p>

      {/* Steps */}
      <div className="flex items-center gap-4 text-xs">
        {agent.steps.map((step, index) => formatStepStatus(step, index))}
      </div>
    </div>
  )
}
