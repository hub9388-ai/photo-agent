import { AnalysisWorkspace } from "@/components/analysis"

export default async function AnalysisJobPage({
  params,
}: {
  params: Promise<{ jobId: string }>
}) {
  const { jobId } = await params
  return <AnalysisWorkspace initialJobId={jobId} />
}
