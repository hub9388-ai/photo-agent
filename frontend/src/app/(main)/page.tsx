import {
  HeroSection,
  CapabilityCard,
  WorkflowSteps,
  RecentTaskList,
  DashboardStatsGrid,
} from "@/components/dashboard"
import { photographyWorkflow } from "@/lib/photography-workflow"

export default function DashboardPage() {
  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      {/* Hero Section */}
      <HeroSection />

      {/* Core Capabilities */}
      <section aria-labelledby="capability-heading">
        <h2 id="capability-heading" className="text-lg font-semibold text-slate-900 mb-4 flex items-center gap-2">
          <span className="text-yellow-500">✨</span>
          核心能力
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-5 gap-4">
          {photographyWorkflow.map((cap) => (
            <CapabilityCard key={cap.path} {...cap} href={cap.path} />
          ))}
        </div>
      </section>

      {/* Workflow Steps */}
      <WorkflowSteps />

      {/* Bottom Section */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Recent Tasks */}
        <RecentTaskList />

        {/* Statistics */}
        <DashboardStatsGrid />
      </div>
    </div>
  )
}
