import { AnalysisWorkspace } from "@/components/analysis"

// Static public demo exports only its fixed case; real mode retains dynamic jobs.
export function generateStaticParams() {
  return process.env.NEXT_PUBLIC_DEMO_MODE === "1" ? ["demo-cat", "demo-post", "demo-coach"].map(jobId => ({ jobId })) : []
}

export default async function AnalysisJobPage({
  params,
}: {
  params: Promise<{ jobId: string }>
}) {
  const { jobId } = await params
  return <AnalysisWorkspace initialJobId={jobId} />
}
