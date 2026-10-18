import { RetouchWorkspace } from "@/components/retouch/RetouchWorkspace"

export default async function RetouchPage({
  searchParams,
}: {
  searchParams: Promise<{ media_id?: string; job_id?: string }>
}) {
  const params = await searchParams
  return <RetouchWorkspace mediaId={typeof params.media_id === "string" ? params.media_id : undefined}
    jobId={typeof params.job_id === "string" ? params.job_id : undefined} />
}
