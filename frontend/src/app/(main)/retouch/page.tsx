import { RetouchWorkspace } from "@/components/retouch/RetouchWorkspace"
import { DEMO_MODE } from "@/lib/demo/config"

export default async function RetouchPage({
  searchParams,
}: {
  searchParams: Promise<{ media_id?: string; job_id?: string }>
}) {
  // The demo shell supplies the editor; don't read request-only data in a static build.
  if (DEMO_MODE) return <RetouchWorkspace mediaId="demo-cat-original" jobId="demo-cat" />
  const params = await searchParams
  return <RetouchWorkspace mediaId={typeof params.media_id === "string" ? params.media_id : undefined}
    jobId={typeof params.job_id === "string" ? params.job_id : undefined} />
}
